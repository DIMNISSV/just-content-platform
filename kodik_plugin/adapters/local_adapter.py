import logging

from .base import BaseJCPAdapter

logger = logging.getLogger(__name__)


class LocalServiceAdapter(BaseJCPAdapter):
    """
    Directly calls the JCP Aggregator service layer via Python.
    Bypasses network serialization, suitable for monolithic deployments.
    """

    def __init__(self, plugin_id: int):
        from aggregator.models import PluginProvider

        self.plugin_id = plugin_id
        try:
            self.plugin = PluginProvider.objects.get(id=self.plugin_id, is_active=True)
        except PluginProvider.DoesNotExist:
            raise ValueError(f"Active PluginProvider with ID {self.plugin_id} not found.")

    def send_payload(self, payload: dict) -> tuple[dict, int]:
        # Отложенный импорт для избежания циклических зависимостей,
        # если плагин будет использоваться вне Django-контекста
        from aggregator.services import process_plugin_payload

        # Добавляем ID плагина, как если бы это пришло через Webhook
        payload['plugin_id'] = self.plugin_id

        try:
            return process_plugin_payload(self.plugin, payload)
        except Exception as e:
            logger.exception("LocalServiceAdapter failed during payload processing")
            return {"error": str(e)}, 500
