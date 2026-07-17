from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class TitleRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='title_ratings',
                             verbose_name='Пользователь')
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='ratings',
                              verbose_name='Произведение')
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
    track_group = models.ForeignKey('content.TrackGroup', on_delete=models.CASCADE, related_name='ratings',
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
