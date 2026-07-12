import logging

from django.db import transaction

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
        logger.debug(f"Initializing LocalServiceAdapter with plugin ID: {plugin_id}")
        try:
            self.plugin = PluginProvider.objects.get(id=self.plugin_id, is_active=True)
            logger.info(f"LocalServiceAdapter successfully bound to active provider: {self.plugin.name}")
        except PluginProvider.DoesNotExist:
            logger.error(f"Initialization failed. Active PluginProvider with ID {self.plugin_id} does not exist.")
            raise ValueError(f"Active PluginProvider with ID {self.plugin_id} not found.")

    def send_payload(self, payload: dict) -> tuple[dict, int]:
        from aggregator.services import process_plugin_payload

        payload['plugin_id'] = self.plugin_id
        title_name = payload.get('title_metadata', {}).get('name')
        logger.debug(f"Processing local service payload for: {title_name}")

        try:
            with transaction.atomic():
                response, status = process_plugin_payload(self.plugin, payload)

            logger.debug(f"Local payload processing complete. Status: {status}")
            return response, status
        except Exception as e:
            logger.exception(
                f"Transaction rolled back due to an exception during local payload processing for: {title_name}")
            return {"error": str(e)}, 500
