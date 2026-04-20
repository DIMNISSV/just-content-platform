import subprocess
import json
from celery import shared_task
from django.db import transaction
from .models import RawMediaFile, MediaStream


@shared_task
def analyze_raw_file(file_id):
    try:
        raw_file = RawMediaFile.objects.get(id=file_id)
    except RawMediaFile.DoesNotExist:
        return

    # Update status to ANALYZING
    raw_file.status = RawMediaFile.Status.ANALYZING
    raw_file.save(update_fields=['status'])

    file_path = raw_file.file.path

    try:
        # Run ffprobe to get media streams in JSON format
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
            # Clear old streams if re-analyzing
            raw_file.streams.all().delete()

            # Iterate over ffprobe streams and create MediaStream objects
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
                    extra_info=stream  # Save full stream metadata (bitrate, resolution, etc.)
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