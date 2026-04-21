import os
import subprocess
import json
import logging
from celery import shared_task
from django.db import transaction
from django.conf import settings
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
        logger.error(f"Asset {asset_id} not found in DB")
        return

    base_out_dir = os.path.join(settings.MEDIA_ROOT, 'assets', str(asset.id))
    os.makedirs(base_out_dir, exist_ok=True)

    input_path = raw_file.file.path
    stream_index = stream.index
    codec_type = stream.codec_type

    logger.info(f"Processing {codec_type} stream #{stream_index} from {raw_file.original_name}")

    try:
        if codec_type == MediaStream.StreamType.VIDEO:
            out_file = os.path.join(base_out_dir, 'master.m3u8')
            rel_path = f'assets/{asset.id}/master.m3u8'
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-map', f'0:{stream_index}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                '-hls_time', '10', '-hls_playlist_type', 'vod',
                '-hls_segment_filename', os.path.join(base_out_dir, 'segment_%03d.ts'),
                out_file
            ]
        elif codec_type == MediaStream.StreamType.AUDIO:
            out_file = os.path.join(base_out_dir, 'audio.m4a')
            rel_path = f'assets/{asset.id}/audio.m4a'
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-map', f'0:{stream_index}',
                '-c:a', 'aac', '-b:a', '128k',
                out_file
            ]
        elif codec_type == MediaStream.StreamType.SUBTITLE:
            out_file = os.path.join(base_out_dir, 'sub.vtt')
            rel_path = f'assets/{asset.id}/sub.vtt'
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-map', f'0:{stream_index}',
                out_file
            ]
        else:
            raise ValueError(f"Unknown codec type: {codec_type}")

        logger.info(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        asset.storage_path = rel_path
        asset.status = Asset.Status.READY
        asset.save(update_fields=['storage_path', 'status'])
        logger.info(f"Asset {asset_id} is READY")

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error for {asset_id}: {e.stderr}")
        asset.status = Asset.Status.ERROR
        asset.save(update_fields=['status'])
    except Exception as e:
        logger.error(f"Extraction failed for {asset_id}: {str(e)}")
        asset.status = Asset.Status.ERROR
        asset.save(update_fields=['status'])
