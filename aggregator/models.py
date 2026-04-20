from django.db import models


class PluginProvider(models.Model):
    name = models.CharField(max_length=100, help_text="Название донора (напр. Kodik, Collaps)")
    endpoint_url = models.URLField(help_text="URL эндпоинта плагина")
    api_token = models.CharField(max_length=255, blank=True, help_text="Токен авторизации (если нужен)")
    is_active = models.BooleanField(default=True, help_text="Включен ли опрос этого плагина")
    timeout = models.IntegerField(default=3, help_text="Таймаут ожидания ответа в секундах")

    def __str__(self):
        status = "✅" if self.is_active else "❌"
        return f"{status} {self.name}"
