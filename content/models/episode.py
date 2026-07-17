import uuid

from django.db import models


class Episode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='episodes',
                              verbose_name='Произведение')
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
