import json
import logging
import os
import re
import shlex
import subprocess
import time

from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import RawMediaFile, MediaStream, AssetVariant

logger = logging.getLogger(__name__)


@shared_task
def analyze_raw_file(file_id):
    try:
        raw_file = RawMediaFile.objects.get(id=file_id)
    except RawMediaFile.DoesNotExist:
        logger.error(f"RawMediaFile {file_id} not found")
        return

    raw_file.status = RawMediaFile.Status.ANALYZING
    raw_file.save(update_fields=['status'])

    file_path = raw_file.file.path
    logger.info(f"Analyzing file: {file_path}")

    try:
        result = subprocess.run([
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ],
            capture_output=True,
            text=True,
            check=True
        )

        probe_data = json.loads(result.stdout)
        raw_file.metadata = probe_data

        with transaction.atomic():
            raw_file.streams.all().delete()
            for stream in probe_data.get('streams', []):
                codec_type_raw = stream.get('codec_type', '')
                if codec_type_raw == 'video':
                    stream_type = MediaStream.StreamType.VIDEO
                elif codec_type_raw == 'audio':
                    stream_type = MediaStream.StreamType.AUDIO
                elif codec_type_raw == 'subtitle':
                    stream_type = MediaStream.StreamType.SUBTITLE
                else:
                    stream_type = MediaStream.StreamType.OTHER

                MediaStream.objects.create(
                    raw_file=raw_file,
                    index=stream.get('index', 0),
                    codec_type=stream_type,
                    codec_name=stream.get('codec_name', ''),
                    language=stream.get('tags', {}).get('language', '')[:10],
                    extra_info=stream
                )

        raw_file.status = RawMediaFile.Status.READY
        raw_file.save(update_fields=['status', 'metadata'])
        logger.info(f"Analysis complete for {raw_file.original_name}")

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raw_file.status = RawMediaFile.Status.ERROR
        raw_file.metadata = {'error': str(e)}
        raw_file.save(update_fields=['status', 'metadata'])


TIME_RE = re.compile(r'out_time_ms=(\d+)')


@shared_task
def extract_stream_task(variant_id):
    """
    Выполняет экстракцию и транскодирование дорожки на основе выбранного пресета.
    Поддерживает динамические настройки качества и кастомные флаги FFmpeg.
    """
    logger.info(f"--- Starting extraction for Variant: {variant_id} ---")

    try:
        # Загружаем вариант и все связанные данные
        variant = AssetVariant.objects.select_related('asset__source_stream__raw_file', 'preset').get(id=variant_id)
        asset = variant.asset
        stream = asset.source_stream
        raw_file = stream.raw_file
        preset = variant.preset
    except AssetVariant.DoesNotExist:
        logger.error(f"Variant {variant_id} not found in database.")
        return

    # 1. Подготовка путей
    base_out_dir = os.path.join(settings.MEDIA_ROOT, 'assets', str(asset.id), str(variant.id))
    os.makedirs(base_out_dir, exist_ok=True)
    input_path = raw_file.file.path

    try:
        total_duration = float(raw_file.metadata.get('format', {}).get('duration', 0))
    except (TypeError, ValueError):
        total_duration = 0
    total_micros = int(total_duration * 1000000)

    # 2. Формирование команды FFmpeg
    cmd = ['ffmpeg', '-y']
    if preset and preset.custom_pre_args:
        cmd.extend(shlex.split(preset.custom_pre_args))

    cmd.extend(['-progress', '-', '-i', input_path, '-map', f'0:{stream.index}'])

    container = preset.container if (preset and preset.container) else (
        'm3u8' if stream.codec_type == 'VIDEO' else 'm4a')
    rel_path = ""
    out_file = ""

    if stream.codec_type == MediaStream.StreamType.VIDEO:
        out_file = os.path.join(base_out_dir, f'master.{container}')
        rel_path = f'assets/{asset.id}/{variant.id}/master.{container}'

        v_codec = preset.codec if preset and preset.codec else 'libx264'
        v_bitrate = preset.bitrate if preset and preset.bitrate else '2M'

        cmd.extend(['-c:v', v_codec, '-b:v', v_bitrate])

        if preset and preset.width:
            cmd.extend(['-vf', f'scale={preset.width}:-2'])

        if preset and preset.video_preset:
            cmd.extend(['-preset', preset.video_preset])
        elif not preset:
            cmd.extend(['-preset', 'veryfast'])

        if container == 'm3u8':
            cmd.extend(['-hls_time', '10', '-hls_playlist_type', 'vod'])
            if not (preset and preset.custom_post_args and '-hls_segment_filename' in preset.custom_post_args):
                if v_codec in ['libaom-av1', 'libx265', 'hevc']:
                    cmd.extend([
                        '-hls_segment_type', 'fmp4',
                        '-hls_segment_filename', os.path.join(base_out_dir, 'segment_%03d.m4s')
                    ])
                else:
                    cmd.extend([
                        '-hls_segment_filename', os.path.join(base_out_dir, 'segment_%03d.ts')
                    ])

    elif stream.codec_type == MediaStream.StreamType.AUDIO:
        out_file = os.path.join(base_out_dir, f'audio.{container}')
        rel_path = f'assets/{asset.id}/{variant.id}/audio.{container}'

        a_codec = preset.codec if preset and preset.codec else 'aac'
        a_bitrate = preset.bitrate if preset and preset.bitrate else '128k'
        cmd.extend(['-c:a', a_codec, '-b:a', a_bitrate])

    elif stream.codec_type == MediaStream.StreamType.SUBTITLE:
        out_file = os.path.join(base_out_dir, 'sub.vtt')
        rel_path = f'assets/{asset.id}/{variant.id}/sub.vtt'
        cmd.extend(['-c:s', 'webvtt'])

    if preset and preset.custom_post_args:
        cmd.extend(shlex.split(preset.custom_post_args))

    cmd.append(out_file)

    logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")

    # 3. Запуск и прогресс
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace'
    )

    last_db_update = time.time()

    try:
        for line in process.stdout:
            match = TIME_RE.search(line)
            if match and total_micros > 0:
                current_micros = int(match.group(1))
                percent = min(max(int((current_micros / total_micros) * 100), 0), 99)

                if percent > variant.progress and (time.time() - last_db_update > 2):
                    variant.progress = percent
                    variant.save(update_fields=['progress'])
                    last_db_update = time.time()
                    logger.info(f"Variant {variant_id} Progress: {percent}%")

        process.wait()

        if process.returncode == 0:
            variant.storage_path = rel_path
            variant.status = AssetVariant.Status.READY
            variant.progress = 100
            variant.save()
            logger.info(f"SUCCESS: Variant {variant_id} is READY at {rel_path}")
        else:
            logger.error(f"FFmpeg process exited with code {process.returncode}")
            variant.status = AssetVariant.Status.ERROR
            variant.save(update_fields=['status'])

    except Exception as e:
        logger.error(f"Extraction CRITICAL FAILURE: {str(e)}")
        variant.status = AssetVariant.Status.ERROR
        variant.save(update_fields=['status'])
        if process.poll() is None:
            process.kill()

    return f"Done: {variant.status}"
