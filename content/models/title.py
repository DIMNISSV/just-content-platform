import uuid

from django.db import models


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
    genres = models.ManyToManyField('content.Genre', blank=True, verbose_name='Жанры')
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
