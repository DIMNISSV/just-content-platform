import json
import logging
import os
import re
import subprocess
import time

from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import RawMediaFile, MediaStream, Asset

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
def extract_stream_task(asset_id):
    """
    Extracts a specific stream from RawMediaFile and transcodes it
    into a web-friendly format based on its type.
    """
    logger.info(f"Starting extraction for Asset: {asset_id}")
    try:
        asset = Asset.objects.select_related('source_stream__raw_file').get(id=asset_id)
        stream = asset.source_stream
        raw_file = stream.raw_file
    except Asset.DoesNotExist:
        logger.error(f"Asset {asset_id} not found")
        return

    # Получаем общую длительность файла из метаданных (нужна для % прогресса)
    total_duration = float(raw_file.metadata.get('format', {}).get('duration', 0))
    total_ms = int(total_duration * 1000000)  # FFmpeg progress работает в микросекундах

    base_out_dir = os.path.join(settings.MEDIA_ROOT, 'assets', str(asset.id))
    os.makedirs(base_out_dir, exist_ok=True)

    input_path = raw_file.file.path
    stream_index = stream.index
    codec_type = stream.codec_type

    # Базовые аргументы
    cmd = ['ffmpeg', '-y', '-progress', '-', '-i', input_path, '-map', f'0:{stream_index}']

    if codec_type == MediaStream.StreamType.VIDEO:
        out_file = os.path.join(base_out_dir, 'master.m3u8')
        rel_path = f'assets/{asset.id}/master.m3u8'
        cmd += [
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
            '-hls_time', '10', '-hls_playlist_type', 'vod',
            '-hls_segment_filename', os.path.join(base_out_dir, 'segment_%03d.ts'),
            out_file
        ]
    elif codec_type == MediaStream.StreamType.AUDIO:
        out_file = os.path.join(base_out_dir, 'audio.m4a')
        rel_path = f'assets/{asset.id}/audio.m4a'
        cmd += ['-c:a', 'aac', '-b:a', '128k', out_file]
    else:
        # Для субтитров прогресс не критичен, они извлекаются мгновенно
        subprocess.run(
            ['ffmpeg', '-y', '-i', input_path, '-map', f'0:{stream_index}', os.path.join(base_out_dir, 'sub.vtt')],
            check=True)
        asset.status = Asset.Status.READY
        asset.progress = 100
        asset.storage_path = f'assets/{asset.id}/sub.vtt'
        asset.save()
        return

    logger.info(f"Executing FFmpeg with real-time progress tracking...")

    # Запускаем Popen без PIPE для stderr (чтобы не было deadlock),
    # читаем только stdout куда идет -progress
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Сливаем stderr в stdout для логов
        universal_newlines=True,
        encoding='utf-8'
    )

    last_update_time = time.time()

    try:
        for line in process.stdout:
            # Ищем время текущего кадра в микросекундах
            match = TIME_RE.search(line)
            if match and total_ms > 0:
                current_ms = int(match.group(1))
                percent = min(int((current_ms / total_ms) * 100), 99)

                # Обновляем БД не слишком часто (раз в 2 сек), чтобы не спамить
                if percent > asset.progress and (time.time() - last_update_time > 2):
                    asset.progress = percent
                    asset.save(update_fields=['progress'])
                    last_update_time = time.time()
                    logger.info(f"Asset {asset_id} progress: {percent}%")

        process.wait()

        if process.returncode == 0:
            asset.storage_path = rel_path
            asset.status = Asset.Status.READY
            asset.progress = 100
            asset.save()
            logger.info(f"Asset {asset_id} is READY")
        else:
            raise subprocess.CalledProcessError(process.returncode, cmd)

    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        asset.status = Asset.Status.ERROR
        asset.save(update_fields=['status'])
    finally:
        if process.poll() is None:
            process.kill()
