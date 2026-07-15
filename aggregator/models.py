import uuid

from django.contrib.contenttypes.models import ContentType
from django.db import models


class PluginProvider(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название донора",
                            help_text="Название донора (например: Kodik, Collaps)")
    endpoint_url = models.URLField(blank=True, null=True, verbose_name="URL эндпоинта",
                                   help_text="URL эндпоинта плагина (если удаленный)")
    is_local = models.BooleanField(default=False, verbose_name="Локальное выполнение",
                                   help_text="Выполняется ли этот плагин локально внутри JCP?")
    app_label = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=" Django-приложение",
        help_text="Имя Django-приложения локального плагина (например: 'kodik_plugin')"
    )
    api_token = models.CharField(max_length=255, blank=True, verbose_name="Токен авторизации",
                                 help_text="Токен авторизации (если нужен)")
    is_active = models.BooleanField(default=True, verbose_name="Активен", help_text="Включен ли опрос этого плагина")
    timeout = models.IntegerField(default=3, verbose_name="Таймаут (сек)",
                                  help_text="Таймаут ожидания ответа в секундах")
    allowed_domains = models.JSONField(
        blank=True,
        default=list,
        verbose_name="Разрешенные домены",
        help_text="Список разрешенных хостов (например: ['anime-gate.ru']). Пусто = глобально"
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Секрет вебхука",
        help_text="Секрет для подтверждения WebHook-ов от плагина"
    )
    allow_title_creation = models.BooleanField(
        default=False,
        verbose_name="Создание произведений",
        help_text="Разрешает плагину создавать новые тайтлы и серии"
    )
    allow_title_update = models.BooleanField(
        default=False,
        verbose_name="Обновление произведений",
        help_text="Разрешает плагину обновлять метаданные существующих тайтлов"
    )
    metadata_priority = models.IntegerField(
        default=0,
        verbose_name="Приоритет метаданных",
        help_text="Приоритет метаданных плагина. Чем выше, тем авторитетнее источник"
    )
    client_script_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="URL клиентского скрипта",
        help_text="URL JavaScript файла плагина для отслеживания телеметрии на фронтенде"
    )

    class Meta:
        verbose_name = 'Провайдер плагина'
        verbose_name_plural = 'Провайдеры плагинов'

    def __str__(self):
        status = "Активен" if self.is_active else "Неактивен"
        location = "Локальный" if self.is_local else "Удаленный"
        return f"[{status}] [{location}] {self.name}"


class ExternalContentRegistry(models.Model):
    class ContentTypeChoices(models.TextChoices):
        MANIFEST = 'MANIFEST', 'Внешний манифест'
        EPISODE_IFRAME = 'EPISODE_IFRAME', 'iFrame серии'
        ENTITY_IFRAME = 'ENTITY_IFRAME', 'iFrame произведения'

    plugin = models.ForeignKey(PluginProvider, on_delete=models.CASCADE, related_name='registry_entries',
                               verbose_name='Плагин')
    title = models.ForeignKey('content.Title', on_delete=models.CASCADE, related_name='external_content',
                              verbose_name='Произведение')
    episode = models.ForeignKey('content.Episode', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='external_content', verbose_name='Серия')
    external_id = models.CharField(max_length=100, verbose_name='Внешний ID',
                                   help_text="ID контента на стороне плагина")
    content_type = models.CharField(max_length=20, choices=ContentTypeChoices.choices, verbose_name='Тип контента')
    target_asset_uuid = models.UUIDField(null=True, blank=True, verbose_name='UUID локального ассета',
                                         help_text="UUID локального видео-ассета")
    fetch_url = models.URLField(max_length=500, verbose_name='URL источника',
                                help_text="URL для запроса манифеста или iframe")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        unique_together = ('plugin', 'title', 'episode', 'content_type', 'target_asset_uuid')
        verbose_name = 'Реестр внешнего контента'
        verbose_name_plural = 'Реестры внешнего контента'

    def __str__(self):
        obj_name = f"{self.title.name} S{self.episode.season_number}E{self.episode.episode_number}" if self.episode else self.title.name
        return f"[{self.plugin.name}] {obj_name} ({self.content_type})"


class ViewingSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='viewing_sessions',
                             verbose_name='Пользователь')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='Тип контента')
    object_id = models.CharField(max_length=255, db_index=True, verbose_name='ID объекта')
    expires_at = models.DateTimeField(verbose_name='Срок истечения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Сессия просмотра'
        verbose_name_plural = 'Сессии просмотра'

    def __str__(self):
        return f"Session {self.id} for User {self.user.email}"
