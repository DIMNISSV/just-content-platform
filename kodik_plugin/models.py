from django.db import models


class KodikSyncState(models.Model):
    key = models.CharField(max_length=100, unique=True, verbose_name='Идентификатор задачи',
                           help_text="Unique identifier for the sync task")
    state_data = models.JSONField(default=dict, verbose_name='Данные состояния',
                                  help_text="Stored state (e.g., next_page_url, last_index)")
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Состояние синхронизации Kodik'
        verbose_name_plural = 'Состояния синхронизации Kodik'

    def __str__(self):
        return self.key


class KodikDumpProcessedID(models.Model):
    kp_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='Кинопоиск ID')
    imdb_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='IMDb ID')
    shiki_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='Шикимори ID')
    mdl_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='MyDramaList ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата обработки')

    class Meta:
        verbose_name = 'Обработанный ID дампа Kodik'
        verbose_name_plural = 'Обработанные ID дампов Kodik'

    def __str__(self):
        return f"Обработанный ID (KP:{self.kp_id}, IMDb:{self.imdb_id}, Shiki:{self.shiki_id}, MDL:{self.mdl_id})"
