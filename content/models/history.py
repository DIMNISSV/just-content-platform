from django.conf import settings
from django.db import models


class WatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='watch_history', verbose_name='Пользователь')
    guest_id = models.UUIDField(null=True, blank=True, db_index=True, verbose_name='ID гостя')
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='watch_history',
                              verbose_name='Произведение')
    episode = models.ForeignKey('content.Episode', on_delete=models.CASCADE, null=True, blank=True,
                                verbose_name='Серия')
    track_group = models.ForeignKey('content.TrackGroup', on_delete=models.SET_NULL, null=True, blank=True,
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
        ordering = ['-updated_at']
        verbose_name = 'История просмотра'
        verbose_name_plural = 'История просмотров'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'title'],
                name='unique_user_title_history',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['guest_id', 'title'],
                name='unique_guest_title_history',
                condition=models.Q(guest_id__isnull=False)
            ),
        ]

    def __str__(self):
        identifier = self.user.email if self.user else f"Guest {self.guest_id}"
        return f"{identifier} watching {self.title} ({self.progress_ms}ms)"


class EpisodeWatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='episode_watch_history', verbose_name='Пользователь')
    guest_id = models.UUIDField(null=True, blank=True, db_index=True, verbose_name='ID гостя')
    episode = models.ForeignKey('content.Episode', on_delete=models.CASCADE, related_name='watch_history',
                                verbose_name='Серия')
    progress_ms = models.PositiveIntegerField(default=0, help_text="Текущая позиция воспроизведения в миллисекундах",
                                              verbose_name='Прогресс (мс)')
    is_completed = models.BooleanField(default=False, help_text="Установите в True, если просмотр завершен",
                                       verbose_name='Просмотр завершен')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'История просмотра серии'
        verbose_name_plural = 'Истории просмотра серий'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'episode'],
                name='unique_user_episode_history',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['guest_id', 'episode'],
                name='unique_guest_episode_history',
                condition=models.Q(guest_id__isnull=False)
            ),
        ]

    def __str__(self):
        identifier = self.user.email if self.user else f"Guest {self.guest_id}"
        return f"{identifier} - {self.episode} ({self.progress_ms}ms)"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites',
                             verbose_name='Пользователь')
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='favorited_by',
                              verbose_name='Произведение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        unique_together = ('user', 'title')
        ordering = ['-created_at']
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self):
        return f"{self.user} favorited {self.title}"
