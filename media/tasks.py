import os
import subprocess
import json
from celery import shared_task
from django.db import transaction
from django.conf import settings
from .models import RawMediaFile, MediaStream, Asset


@shared_task
def analyze_raw_file(file_id):
    try:
        raw_file = RawMediaFile.objects.get(id=file_id)
    except RawMediaFile.DoesNotExist:
        return

    raw_file.status = RawMediaFile.Status.ANALYZING
    raw_file.save(update_fields=['status'])

    file_path = raw_file.file.path

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

                language = stream.get('tags', {}).get('language', '')[:10]
                codec_name = stream.get('codec_name', '')

                MediaStream.objects.create(
                    raw_file=raw_file,
                    index=stream.get('index', 0),
                    codec_type=stream_type,
                    codec_name=codec_name,
                    language=language,
                    extra_info=stream
                )

        raw_file.status = RawMediaFile.Status.READY
        raw_file.save(update_fields=['status', 'metadata'])

    except subprocess.CalledProcessError as e:
        raw_file.status = RawMediaFile.Status.ERROR
        raw_file.metadata = {'error': 'ffprobe execution failed', 'stderr': e.stderr}
        raw_file.save(update_fields=['status', 'metadata'])
    except Exception as e:
        raw_file.status = RawMediaFile.Status.ERROR
        raw_file.metadata = {'error': str(e)}
        raw_file.save(update_fields=['status', 'metadata'])


@shared_task
def extract_stream_task(asset_id):
    """
    Extracts a specific stream from RawMediaFile and transcodes it
    into a web-friendly format based on its type.
    """
    try:
        asset = Asset.objects.get(id=asset_id)
        stream = asset.source_stream
        raw_file = stream.raw_file
    except Asset.DoesNotExist:
        return

    # Create an output directory specific to this Asset
    base_out_dir = os.path.join(settings.MEDIA_ROOT, 'assets', str(asset.id))
    os.makedirs(base_out_dir, exist_ok=True)

    input_path = raw_file.file.path
    # The global index of the stream in the container
    stream_index = stream.index
    codec_type = stream.codec_type

    try:
        if codec_type == MediaStream.StreamType.VIDEO:
            out_file = os.path.join(base_out_dir, 'master.m3u8')
            rel_path = f'assets/{asset.id}/master.m3u8'
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-map', f'0:{stream_index}',  # Map only this specific stream
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
            raise ValueError(f"Unsupported extraction for codec type: {codec_type}")

        # Execute FFmpeg
        process = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Update Asset on success
        asset.storage_path = rel_path
        asset.status = Asset.Status.READY
        asset.save(update_fields=['storage_path', 'status'])

    except subprocess.CalledProcessError as e:
        asset.status = Asset.Status.ERROR
        # In a real project, we should log e.stderr here
        asset.save(update_fields=['status'])
    except Exception as e:
        asset.status = Asset.Status.ERROR
        asset.save(update_fields=['status'])