from django.db import models


class PluginProvider(models.Model):
    name = models.CharField(max_length=100, help_text="Название донора (напр. Kodik, Collaps)")
    endpoint_url = models.URLField(help_text="URL эндпоинта плагина")
    api_token = models.CharField(max_length=255, blank=True, help_text="Токен авторизации (если нужен)")
    is_active = models.BooleanField(default=True, help_text="Включен ли опрос этого плагина")
    timeout = models.IntegerField(default=3, help_text="Таймаут ожидания ответа в секундах")

    allowed_domains = models.JSONField(
        blank=True,
        default=list,
        help_text="Список разрешенных хостов (напр. ['anime-gate.ru']). Пусто = глобально"
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Секрет для подтверждения WebHook-ов от плагина"
    )
    can_restore_assets = models.BooleanField(
        default=False,
        help_text="Может ли плагин заменять удаленные локальные видео-ассеты (Lifeboat)?"
    )

    def __str__(self):
        status = "✅" if self.is_active else "❌"
        return f"{status} {self.name}"


class ExternalContentRegistry(models.Model):
    class ContentTypeChoices(models.TextChoices):
        MANIFEST = 'MANIFEST', 'External Manifest'
        EPISODE_IFRAME = 'EPISODE_IFRAME', 'Episode iFrame'
        ENTITY_IFRAME = 'ENTITY_IFRAME', 'Entity iFrame'

    plugin = models.ForeignKey(PluginProvider, on_delete=models.CASCADE, related_name='registry_entries')
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='external_content')
    episode = models.ForeignKey('content.Episode', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='external_content')

    external_id = models.CharField(max_length=100, help_text="ID контента на стороне плагина")
    content_type = models.CharField(max_length=20, choices=ContentTypeChoices.choices)

    # Привязка к физическому ассету для точной синхронизации (UUID видео)
    target_asset_uuid = models.UUIDField(null=True, blank=True, help_text="UUID локального видео-ассета")

    fetch_url = models.URLField(max_length=500, help_text="URL для запроса манифеста или iframe")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('plugin', 'title', 'episode', 'content_type', 'target_asset_uuid')

    def __str__(self):
        obj_name = f"{self.title.name} S{self.episode.season_number}E{self.episode.episode_number}" if self.episode else self.title.name
        return f"[{self.plugin.name}] {obj_name} ({self.content_type})"
