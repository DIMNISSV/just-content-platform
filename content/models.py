import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Слаг')

    class Meta:
        verbose_name = 'Жанр'
        verbose_name_plural = 'Жанры'

    def __str__(self):
        return self.name


class Title(models.Model):
    class Type(models.TextChoices):
        MOVIE = 'MOVIE', 'Фильм'
        SERIES = 'SERIES', 'Сериал'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.MOVIE, verbose_name='Тип')
    name = models.CharField(max_length=500, verbose_name='Название')
    original_name = models.CharField(max_length=500, blank=True, verbose_name='Оригинальное название')
    description = models.TextField(blank=True, verbose_name='Описание')
    release_year = models.IntegerField(null=True, blank=True, verbose_name='Год выпуска')
    genres = models.ManyToManyField('Genre', blank=True, verbose_name='Жанры')
    taxonomy_items = models.ManyToManyField('taxonomy.TaxonomyItem', blank=True, verbose_name='Элементы таксономии')
    raw_terms = models.ManyToManyField('taxonomy.RawTerm', blank=True, help_text="Сырые термины от доноров",
                                       verbose_name='Сырые термины')
    imdb_id = models.CharField(max_length=100, blank=True, verbose_name='IMDb ID')
    tmdb_id = models.CharField(max_length=100, blank=True, verbose_name='TMDb ID')
    kp_id = models.CharField(max_length=100, blank=True, verbose_name='Кинопоиск ID')
    shiki_id = models.CharField(max_length=100, blank=True, verbose_name='Shikimori ID')
    mal_id = models.CharField(max_length=100, blank=True, verbose_name='MAL ID')
    mdl_id = models.CharField(max_length=100, blank=True, verbose_name='MDL ID')
    wa_id = models.CharField(max_length=100, blank=True, verbose_name='WorldArt ID')
    poster = models.ImageField(upload_to='posters/', null=True, blank=True, verbose_name='Постер')
    poster_url = models.URLField(max_length=512, blank=True, null=True,
                                 help_text="Предыдущий успешно загруженный URL постера", verbose_name='URL постера')
    rating_score = models.FloatField(default=0.0, db_index=True, verbose_name='Рейтинг')
    votes_count = models.IntegerField(default=0, verbose_name='Количество голосов')
    metadata_priority_level = models.IntegerField(default=0, help_text="Приоритет последнего обновившего источника",
                                                  verbose_name='Уровень приоритета метаданных')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Произведение'
        verbose_name_plural = 'Произведения'

    def __str__(self):
        return self.name


class Episode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='episodes', verbose_name='Произведение')
    season_number = models.IntegerField(default=1, verbose_name='Номер сезона')
    episode_number = models.IntegerField(default=1, verbose_name='Номер серии')
    name = models.CharField(max_length=255, blank=True, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    metadata_priority_level = models.IntegerField(default=0, help_text="Приоритет последнего обновившего источника",
                                                  verbose_name='Приоритет метаданных')

    class Meta:
        ordering = ['season_number', 'episode_number']
        unique_together = ('title', 'season_number', 'episode_number')
        verbose_name = 'Серия'
        verbose_name_plural = 'Серии'

    def __str__(self):
        return f"{self.title.name} - S{self.season_number:02d}E{self.episode_number:02d}"


class TrackGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default='Default Version',
                            help_text="Например: Театральная версия, Director's Cut", verbose_name='Название версии')
    author = models.CharField(max_length=100, blank=True,
                              help_text="Релиз-группа или автор видео-сборки (например, YIFY, HQCLUB)",
                              verbose_name='Автор/Релиз-группа')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='Тип контента')
    object_id = models.CharField(max_length=36, db_index=True, verbose_name='ID объекта')
    content_object = GenericForeignKey('content_type', 'object_id')

    video_asset = models.ForeignKey(
        'media.Asset',
        on_delete=models.RESTRICT,
        limit_choices_to={'type': 'VIDEO'},
        related_name='track_groups',
        verbose_name='Видео ресурс'
    )

    rating_score = models.FloatField(default=0.0, verbose_name='Рейтинг')
    votes_count = models.IntegerField(default=0, verbose_name='Количество голосов')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Группа дорожек'
        verbose_name_plural = 'Группы дорожек'

    def __str__(self):
        return f"{self.name} ({self.content_object})"


class AdditionalTrack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track_group = models.ForeignKey(TrackGroup, on_delete=models.CASCADE, related_name='additional_tracks',
                                    verbose_name='Группа дорожек')
    asset = models.ForeignKey(
        'media.Asset',
        on_delete=models.RESTRICT,
        verbose_name='Ресурс'
    )
    language = models.CharField(max_length=50, default='Unknown', help_text="Например: rus, eng, jpn",
                                verbose_name='Язык')
    author = models.CharField(max_length=100, blank=True,
                              help_text="Студия озвучки или переводчик (например, LostFilm, HDrezka)",
                              verbose_name='Студия озвучки')
    offset_ms = models.IntegerField(default=0, help_text="Сдвиг для синхронизации в миллисекундах",
                                    verbose_name='Смещение (мс)')

    class Meta:
        verbose_name = 'Дополнительная дорожка'
        verbose_name_plural = 'Дополнительные дорожки'

    def __str__(self):
        return f"{self.author} ({self.language}) for {self.track_group.name}"


class TitleRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='title_ratings',
                             verbose_name='Пользователь')
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='ratings', verbose_name='Произведение')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)],
                                             verbose_name='Оценка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        unique_together = ('user', 'title')
        verbose_name = 'Оценка произведения'
        verbose_name_plural = 'Оценки произведений'

    def __str__(self):
        return f"{self.user} rated {self.title} - {self.score}"


class TrackGroupRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='track_ratings',
                             verbose_name='Пользователь')
    track_group = models.ForeignKey(TrackGroup, on_delete=models.CASCADE, related_name='ratings',
                                    verbose_name='Группа дорожек')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)],
                                             verbose_name='Оценка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        unique_together = ('user', 'track_group')
        verbose_name = 'Оценка группы дорожек'
        verbose_name_plural = 'Оценки групп дорожек'

    def __str__(self):
        return f"{self.user} rated {self.track_group} - {self.score}"


class WatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watch_history',
                             verbose_name='Пользователь')
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name='watch_history',
                              verbose_name='Произведение')
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Серия')
    track_group = models.ForeignKey(TrackGroup, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name='Группа дорожек')
    last_audio_asset_id = models.UUIDField(null=True, blank=True, help_text="ID конкретного Asset аудио",
                                           verbose_name='ID аудиоресурса')
    last_audio_track_name = models.CharField(max_length=255, blank=True, null=True,
                                             help_text="Точная строка названия дорожки",
                                             verbose_name='Название аудиодорожки')
    last_quality_label = models.CharField(max_length=50, blank=True, null=True, help_text="Например: 1080p",
                                          verbose_name='Качество')
    progress_ms = models.PositiveIntegerField(default=0, help_text="Текущая позиция воспроизведения в миллисекундах",
                                              verbose_name='Прогресс (мс)')
    is_completed = models.BooleanField(default=False, help_text="Установите в True, если просмотр завершен",
                                       verbose_name='Просмотр завершен')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        unique_together = ('user', 'title')
        ordering = ['-updated_at']
        verbose_name = 'История просмотра'
        verbose_name_plural = 'История просмотров'

    def __str__(self):
        return f"{self.user} watching {self.title} ({self.progress_ms}ms)"


class EpisodeWatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='episode_watch_history',
                             verbose_name='Пользователь')
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name='watch_history',
                                verbose_name='Серия')
    progress_ms = models.PositiveIntegerField(default=0, help_text="Текущая позиция воспроизведения в миллисекундах",
                                              verbose_name='Прогресс (мс)')
    is_completed = models.BooleanField(default=False, help_text="Установите в True, если просмотр завершен",
                                       verbose_name='Просмотр завершен')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        unique_together = ('user', 'episode')
        verbose_name = 'История просмотра серии'
        verbose_name_plural = 'Истории просмотра серий'

    def __str__(self):
        return f"{self.user} - {self.episode} ({self.progress_ms}ms)"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites',
                             verbose_name='Пользователь')
    title = models.ForeignKey('Title', on_delete=models.CASCADE, related_name='favorited_by',
                              verbose_name='Произведение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        unique_together = ('user', 'title')
        ordering = ['-created_at']
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self):
        return f"{self.user} favorited {self.title}"
