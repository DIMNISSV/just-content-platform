from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
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

    type = models.CharField(max_length=10, choices=Type.choices, default=Type.MOVIE)
    name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    genres = models.ManyToManyField('Genre', blank=True)
    imdb_id = models.CharField(max_length=20, blank=True)
    tmdb_id = models.CharField(max_length=20, blank=True)
    kp_id = models.CharField(max_length=20, blank=True)
    shiki_id = models.CharField(max_length=20, blank=True)
    mal_id = models.CharField(max_length=20, blank=True)
    mdl_id = models.CharField(max_length=20, blank=True)
    wa_id = models.CharField(max_length=20, blank=True)
    poster = models.ImageField(upload_to='posters/', null=True, blank=True)
    rating_score = models.FloatField(default=0.0, db_index=True)
    votes_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    track_groups = GenericRelation('TrackGroup')

    def __str__(self):
        return self.name


class Episode(models.Model):
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='episodes')
    season_number = models.IntegerField(default=1)
    episode_number = models.IntegerField(default=1)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Прямая связь для получения сборок дорожек (Для эпизодов)
    track_groups = GenericRelation('TrackGroup')

    class Meta:
        ordering = ['season_number', 'episode_number']
        unique_together = ('title', 'season_number', 'episode_number')

    def __str__(self):
        return f"{self.title.name} - S{self.season_number:02d}E{self.episode_number:02d}"


class TrackGroup(models.Model):
    """
    Аналог SyncGroup. Объединяет базовое ВИДЕО (Asset) и привязывает его к контенту.
    """
    name = models.CharField(max_length=100, default='Default Version',
                            help_text="Например: Театральная версия, Director's Cut")

    # GenericForeignKey позволяет привязать TrackGroup либо к Title (Фильм), либо к Episode (Серия)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
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
    """
    Связывает Аудио или Субтитры (Asset) с конкретной сборкой (TrackGroup).
    Здесь задается offset_ms для синхронизации в плеере.
    """
    track_group = models.ForeignKey(TrackGroup, on_delete=models.CASCADE, related_name='additional_tracks')
    asset = models.ForeignKey(
        'media.Asset',
        on_delete=models.RESTRICT,
        # Запрещаем выбирать VIDEO, только AUDIO или SUBTITLE
    )
    language = models.CharField(max_length=50, default='Unknown', help_text="Например: RUS (Dub), ENG (Original)")
    offset_ms = models.IntegerField(default=0, help_text="Сдвиг для синхронизации в миллисекундах")

    def __str__(self):
        return f"{self.language} track for {self.track_group.name}"


class TitleRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='title_ratings')
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'title')  # Один юзер - одна оценка на фильм

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

    # Optional: If watching a series, we store the specific episode
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, null=True, blank=True)

    # Optional: Remember user's preferred voiceover/track group
    track_group = models.ForeignKey(TrackGroup, on_delete=models.SET_NULL, null=True, blank=True)
    last_audio_asset_id = models.UUIDField(null=True, blank=True, help_text="ID конкретного Asset аудио")
    last_audio_track_name = models.CharField(max_length=255, blank=True, null=True, help_text="Точная строка названия дорожки")
    last_quality_label = models.CharField(max_length=50, blank=True, null=True, help_text="Напр: 1080p")

    progress_ms = models.PositiveIntegerField(default=0, help_text="Current playback position in milliseconds")
    is_completed = models.BooleanField(default=False, help_text="True if watched till the end credits")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'title')  # We keep only the latest progress per Title
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
