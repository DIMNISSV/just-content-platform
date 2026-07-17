import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


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
    video_asset = models.ForeignKey('media.Asset', on_delete=models.RESTRICT, limit_choices_to={'type': 'VIDEO'},
                                    related_name='track_groups', verbose_name='Видео ресурс')
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
    asset = models.ForeignKey('media.Asset', on_delete=models.RESTRICT, verbose_name='Ресурс')
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
