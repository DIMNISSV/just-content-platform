import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class RawMediaFile(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Analysis'
        ANALYZING = 'ANALYZING', 'Analyzing via FFprobe'
        READY = 'READY', 'Ready for Extraction'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='raw_uploads/')
    original_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(blank=True, null=True, help_text="FFprobe output")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class MediaStream(models.Model):
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


class TranscodingPreset(models.Model):
    class Type(models.TextChoices):
        VIDEO = 'VIDEO', 'Video'
        AUDIO = 'AUDIO', 'Audio'

    name = models.CharField(max_length=100, unique=True, help_text="Напр: 4K AV1 5M")
    type = models.CharField(max_length=10, choices=Type.choices)

    # FFmpeg settings
    codec = models.CharField(max_length=50, help_text="libx264, libaom-av1, libopus, aac...")
    video_preset = models.CharField(max_length=50, blank=True,
                                    help_text="veryfast, fast, medium... (оставьте пустым для AV1)")
    container = models.CharField(max_length=20, default='m3u8', help_text="m3u8, mp4, m4a, webm, ogg...")

    bitrate = models.CharField(max_length=20, help_text="5M, 2M, 128k...")
    width = models.IntegerField(null=True, blank=True, help_text="Для видео (напр. 3840)")
    is_default = models.BooleanField(default=False, help_text="Применять ли этот пресет автоматически в Визарде")

    custom_pre_args = models.TextField(blank=True, help_text="Аргументы ДО -i (input)")
    custom_post_args = models.TextField(blank=True, help_text="Аргументы ПОСЛЕ кодеков")

    def __str__(self):
        return self.name


class Asset(models.Model):
    """
    Логический контейнер. Олицетворяет, например, "Оригинальную русскую озвучку",
    независимо от того, в скольких качествах (вариантах) она закодирована.
    """

    class Type(models.TextChoices):
        VIDEO = 'VIDEO', 'Video'
        AUDIO = 'AUDIO', 'Audio'
        SUBTITLE = 'SUBTITLE', 'Subtitle'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        'aggregator.PluginProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
        help_text="Provider owning this asset. Null means local (Node) asset."
    )
    source_stream = models.ForeignKey(MediaStream, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='extracted_assets')
    type = models.CharField(max_length=20, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        orig_name = self.source_stream.raw_file.original_name if self.source_stream and self.source_stream.raw_file else "Unknown Source"
        return f"Asset {self.id.hex[:8]} [{self.type}] - {orig_name}"


class AssetVariant(models.Model):
    """
    Физический файл (или HLS-плейлист) на диске.
    Представляет конкретное качество (1080p, 720p, 128k audio) логического ассета.
    """

    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        READY = 'READY', 'Ready'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='variants')
    preset = models.ForeignKey(TranscodingPreset, on_delete=models.SET_NULL, null=True, blank=True)

    quality_label = models.CharField(max_length=50, blank=True, help_text="Напр: FHD x264 4M")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    progress = models.IntegerField(default=0, help_text="Progress in percent")
    storage_path = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        from django.conf import settings
        from urllib.parse import urlparse, urlunparse

        path = self.storage_path.lstrip('/')

        # If the asset belongs to a provider, construct the remote URL
        if self.asset.provider and self.asset.provider.endpoint_url:
            parsed = urlparse(self.asset.provider.endpoint_url)
            # Extract just the origin (scheme + domain)
            base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))

            # Note: We assume the remote node uses standard settings.MEDIA_URL prefix
            # Alternatively, remote nodes should supply the full path in storage_path
            if path.startswith('http://') or path.startswith('https://'):
                return path
            return f"{base_url}/{settings.MEDIA_URL.lstrip('/')}{path}"

        # Local asset
        return f"/{settings.MEDIA_URL.lstrip('/')}{path}"

    def __str__(self):
        label = self.quality_label or "Original"
        return f"Variant: {label} ({self.status}) for Asset {self.asset.id.hex[:8]}"
