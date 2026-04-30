import json
import logging
import os
import re
import shlex
import subprocess
import time

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import RawMediaFile, MediaStream, AssetVariant, Asset

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

    out_file_name = f'master.{container}'
    rel_path = f'assets/{asset.id}/{variant.id}/{out_file_name}'

    if stream.codec_type == MediaStream.StreamType.VIDEO:
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

            m4s_f = ['av1', '265', 'hevc']
            if any(target in v_codec.lower() for target in m4s_f):
                cmd.extend([
                    '-hls_segment_type', 'fmp4',
                    '-hls_fmp4_init_filename', 'init.mp4',
                    '-hls_segment_filename', 'segment_%03d.m4s'
                ])
            else:
                cmd.extend([
                    '-hls_segment_filename', 'segment_%03d.ts'
                ])

    elif stream.codec_type == MediaStream.StreamType.AUDIO:
        out_file_name = f'audio.{container}'
        rel_path = f'assets/{asset.id}/{variant.id}/{out_file_name}'

        a_codec = preset.codec if preset and preset.codec else 'aac'
        a_bitrate = preset.bitrate if preset and preset.bitrate else '128k'
        cmd.extend(['-c:a', a_codec, '-b:a', a_bitrate])

    elif stream.codec_type == MediaStream.StreamType.SUBTITLE:
        out_file_name = 'sub.vtt'
        rel_path = f'assets/{asset.id}/{variant.id}/sub.vtt'
        cmd.extend(['-c:s', 'webvtt'])

    if preset and preset.custom_post_args:
        cmd.extend(shlex.split(preset.custom_post_args))

    cmd.append(out_file_name)

    logger.info(f"Executing FFmpeg command in {base_out_dir}: {' '.join(cmd)}")

    # 3. Запуск процесса с указанием cwd
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',
        cwd=base_out_dir
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
            if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'NODE':
                push_asset_to_hub.delay(asset.id)
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


@shared_task
def push_asset_to_hub(asset_id):
    """
    Собирает данные о готовом Ассете и отправляет их на Основной сайт (HUB).
    """

    hub_url = getattr(settings, 'HUB_URL', '')
    hub_token = getattr(settings, 'HUB_API_TOKEN', '')
    if not hub_url or getattr(settings, 'PLATFORM_ROLE', 'NODE') != 'NODE':
        return "Push aborted: Not a NODE or HUB_URL is missing."
    try:
        asset = Asset.objects.get(id=asset_id)
    except Asset.DoesNotExist:
        logger.error(f"Asset {asset_id} not found for sync.")
        return
    variants = asset.variants.filter(status=AssetVariant.Status.READY)
    if not variants.exists():
        return "No ready variants to sync"
    payload = {
        "asset_id": str(asset.id),
        "type": asset.type,
        "variants": [
            {
                "variant_id": str(v.id),
                "quality_label": v.quality_label,
                "storage_path": v.storage_path
            } for v in variants
        ]
    }
    sync_url = f"{hub_url.rstrip('/')}/api/v1/aggregator/sync/asset/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {hub_token}"
    }
    try:
        response = requests.post(sync_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info(f"Successfully synced Asset {asset_id} to HUB.")
            return f"Synced {asset_id}"
        else:
            logger.error(f"Failed to sync Asset {asset_id} to HUB. HTTP {response.status_code}: {response.text}")
            return f"Sync failed: {response.status_code}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error syncing Asset {asset_id} to HUB: {e}")
        return f"Sync network error"


@shared_task
def trigger_lifeboat(asset_id):
    """Отправляет на HUB запрос на запуск миграции для ассета."""
    hub_url = getattr(settings, 'HUB_URL', '').rstrip('/')
    hub_token = getattr(settings, 'HUB_API_TOKEN', '')

    if not hub_url: return

    try:
        resp = requests.post(
            f"{hub_url}/api/v1/aggregator/sync/trigger-migration/{asset_id}/",
            headers={"Authorization": f"Bearer {hub_token}"},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to trigger lifeboat on HUB: {e}")
