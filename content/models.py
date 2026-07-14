import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Title(models.Model):
    class Type(models.TextChoices):
        MOVIE = 'MOVIE', 'Movie'
        SERIES = 'SERIES', 'Series'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.MOVIE)
    name = models.CharField(max_length=500)
    original_name = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    genres = models.ManyToManyField('Genre', blank=True)
    taxonomy_items = models.ManyToManyField('taxonomy.TaxonomyItem', blank=True)
    imdb_id = models.CharField(max_length=100, blank=True)
    tmdb_id = models.CharField(max_length=100, blank=True)
    kp_id = models.CharField(max_length=100, blank=True)
    shiki_id = models.CharField(max_length=100, blank=True)
    mal_id = models.CharField(max_length=100, blank=True)
    mdl_id = models.CharField(max_length=100, blank=True)
    wa_id = models.CharField(max_length=100, blank=True)
    poster = models.ImageField(upload_to='posters/', null=True, blank=True)
    poster_url = models.URLField(max_length=512, blank=True, null=True,
                                 help_text="Предыдущий успешно загруженный URL постера")
    rating_score = models.FloatField(default=0.0, db_index=True)
    votes_count = models.IntegerField(default=0)
    metadata_priority_level = models.IntegerField(default=0, help_text="Приоритет последнего обновившего источника")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Episode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='episodes')
    season_number = models.IntegerField(default=1)
    episode_number = models.IntegerField(default=1)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    metadata_priority_level = models.IntegerField(default=0, help_text="Приоритет последнего обновившего источника")

    class Meta:
        ordering = ['season_number', 'episode_number']
        unique_together = ('title', 'season_number', 'episode_number')

    def __str__(self):
        return f"{self.title.name} - S{self.season_number:02d}E{self.episode_number:02d}"


class TrackGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default='Default Version',
                            help_text="Например: Театральная версия, Director's Cut")
    author = models.CharField(max_length=100, blank=True,
                              help_text="Релиз-группа или автор видео-сборки (напр. YIFY, HQCLUB)")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36, db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    video_asset = models.ForeignKey(
        'media.Asset',
        on_delete=models.RESTRICT,
        limit_choices_to={'type': 'VIDEO'},
        related_name='track_groups'
    )

    rating_score = models.FloatField(default=0.0)
    votes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.content_object})"


class AdditionalTrack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track_group = models.ForeignKey(TrackGroup, on_delete=models.CASCADE, related_name='additional_tracks')
    asset = models.ForeignKey(
        'media.Asset',
        on_delete=models.RESTRICT,
    )
    language = models.CharField(max_length=50, default='Unknown', help_text="Например: rus, eng, jpn")
    author = models.CharField(max_length=100, blank=True,
                              help_text="Студия озвучки или переводчик (напр. LostFilm, HDrezka)")
    offset_ms = models.IntegerField(default=0, help_text="Сдвиг для синхронизации в миллисекундах")

    def __str__(self):
        return f"{self.author} ({self.language}) for {self.track_group.name}"


class TitleRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='title_ratings')
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'title')

    def __str__(self):
        return f"{self.user} rated {self.title} - {self.score}"


class TrackGroupRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='track_ratings')
    track_group = models.ForeignKey(TrackGroup, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'track_group')

    def __str__(self):
        return f"{self.user} rated {self.track_group} - {self.score}"


class WatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watch_history')
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='watch_history')
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, null=True, blank=True)
    track_group = models.ForeignKey(TrackGroup, on_delete=models.SET_NULL, null=True, blank=True)
    last_audio_asset_id = models.UUIDField(null=True, blank=True, help_text="ID конкретного Asset аудио")
    last_audio_track_name = models.CharField(max_length=255, blank=True, null=True,
                                             help_text="Точная строка названия дорожки")
    last_quality_label = models.CharField(max_length=50, blank=True, null=True, help_text="Напр: 1080p")
    progress_ms = models.PositiveIntegerField(default=0, help_text="Current playback position in milliseconds")
    is_completed = models.BooleanField(default=False, help_text="True if watched till the end credits")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'title')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user} watching {self.title} ({self.progress_ms}ms)"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    title = models.ForeignKey('Title', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'title')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} favorited {self.title}"
