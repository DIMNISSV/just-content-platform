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
        logger.info(f"Starting Kodik synchronization process. Parameters: {kwargs}")
        success_count = 0
        error_count = 0

        try:
            for item in self.client.iter_list(**kwargs):
                item_id = item.get('id')
                item_title = item.get('title')
                logger.debug(f"Fetched Kodik item: {item_id} - '{item_title}'")

                payloads = map_kodik_item_to_jcp_payloads(item, self.plugin_id)
                logger.debug(f"Mapped item {item_id} into {len(payloads)} JCP payloads.")

                for payload in payloads:
                    logger.debug(f"Sending payload to adapter for item ID {item_id}.")
                    response, status = self.adapter.send_payload(payload)

                    if 200 <= status < 300:
                        success_count += 1
                    else:
                        logger.error(
                            f"Adapter rejected payload for Kodik ID {item_id}. "
                            f"HTTP Status: {status}, Response Details: {response}"
                        )
                        error_count += 1
        except Exception as e:
            logger.exception("Sync process interrupted due to an unexpected error during iteration.")
            raise e

        logger.info(
            f"Kodik synchronization cycle completed. "
            f"Processed successfully: {success_count} payloads. Errors: {error_count} payloads."
        )
        return success_count, error_count
