import uuid

from django.db import models


class RawMediaFile(models.fields.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Analysis'
        ANALYZING = 'ANALYZING', 'Analyzing via FFprobe'
        READY = 'READY', 'Ready for Extraction'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_form='raw_uploads/')
    original_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(blank=True, null=True, help_text="FFprobe output")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class MediaStream(models.fields.Model):
    class StreamType(models.TextChoices):
        VIDEO = 'VIDEO', 'Video'
        AUDIO = 'AUDIO', 'Audio'
        SUBTITLE = 'SUBTITLE', 'Subtitle'
        OTHER = 'OTHER', 'Other'

    raw_file = models.ForeignKey(RawMediaFile, on_delete=models.CASCADE, related_name='streams')
    index = models.IntegerField(help_text="Stream index in the original file")
    codec_type = models.CharField(max_length=20, choices=StreamType.choices)
    codec_name = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=10, blank=True, null=True)

    # Extra info like bitrate, resolution for video, or channel layout for audio
    extra_info = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ['raw_file', 'index']
        unique_together = ('raw_file', 'index')

    def __str__(self):
        lang = f"[{self.language}]" if self.language else ""
        return f"Stream #{self.index} - {self.codec_type} {self.codec_name} {lang}"


class Asset(models.fields.Model):
    class Type(models.TextChoices):
        VIDEO = 'VIDEO', 'Video (HLS/MP4)'
        AUDIO = 'AUDIO', 'Audio (AAC/M4A)'
        SUBTITLE = 'SUBTITLE', 'Subtitle (VTT/SRT)'

    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        READY = 'READY', 'Ready'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_stream = models.ForeignKey(MediaStream, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='extracted_assets')

    type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)

    # Storage path relative to MEDIA_ROOT or S3 bucket
    storage_path = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Asset {self.id} [{self.type}] - {self.status}"
