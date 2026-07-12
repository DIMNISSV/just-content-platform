import logging

from kodik_plugin.adapters.base import BaseJCPAdapter
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.mapper.episode_mapper import map_kodik_item_to_jcp_payloads

logger = logging.getLogger(__name__)


class KodikSyncOrchestrator:
    """
    Coordinates the synchronization process:
    Fetches data from Kodik API -> Maps to JCP format -> Sends via Adapter.
    """

    def __init__(self, client: KodikListClient, adapter: BaseJCPAdapter, plugin_id: int):
        self.client = client
        self.adapter = adapter
        self.plugin_id = plugin_id

    def run_sync(self, **kwargs) -> tuple[int, int]:
        """
        Runs the synchronization loop.
        Accepts Kodik API parameters (limit, sort, order, types, etc.).
        Returns a tuple of (success_count, error_count).
        """
        logger.info(f"Starting Kodik sync with parameters: {kwargs}")
        success_count = 0
        error_count = 0

        for item in self.client.iter_list(**kwargs):
            payloads = map_kodik_item_to_jcp_payloads(item, self.plugin_id)
            for payload in payloads:
                response, status = self.adapter.send_payload(payload)
                if 200 <= status < 300:
                    success_count += 1
                else:
                    logger.error(
                        f"Failed to sync payload for Kodik ID {item.get('id')}. Status: {status}, Response: {response}")
                    error_count += 1

        logger.info(f"Kodik sync complete. Successfully processed: {success_count}, Errors: {error_count}")
        return success_count, error_count
