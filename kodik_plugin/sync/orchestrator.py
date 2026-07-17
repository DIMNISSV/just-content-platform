import logging

from kodik_plugin.adapters.base import BaseJCPAdapter
from kodik_plugin.client.dump_api import KodikDumpClient
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.mapper.episode_mapper import map_kodik_item_to_jcp_payloads
from kodik_plugin.models import KodikSyncState

logger = logging.getLogger(__name__)


class KodikSyncOrchestrator:
    """
    Coordinates the synchronization process:
    Fetches data from Kodik API -> Maps to JCP format -> Sends via Adapter.
    """

    def __init__(self, client: KodikListClient | KodikDumpClient | None, adapter: BaseJCPAdapter, plugin_id: int):
        self.client = client
        self.adapter = adapter
        self.plugin_id = plugin_id

    def run_sync_api(self, resume: bool = False, max_pages: int = 0, max_items: int = 0,
                     state_key: str = 'api_sync_default', use_search: bool = False, **kwargs) -> tuple[int, int]:
        logger.info(
            f"Starting API synchronization. Resume: {resume}, Max Pages: {max_pages}, Max Items: {max_items}, State Key: {state_key}")

        state_obj, _ = KodikSyncState.objects.get_or_create(key=state_key)
        next_page_url = state_obj.state_data.get('next_page_url') if resume else None

        success_count, error_count, pages_processed, items_processed = 0, 0, 0

        try:
            while True:
                if max_pages and pages_processed >= max_pages:
                    logger.info(f"Reached maximum pages limit ({max_pages}). Stopping.")
                    break

                data = self.client.get_page(next_page_url=next_page_url, use_search=use_search, **kwargs)
                results = data.get('results', [])

                if not results:
                    logger.info("No more results returned from API.")
                    break

                for item in results:
                    if max_items and items_processed >= max_items:
                        break

                    succ, err = self._process_item(item)
                    success_count += succ
                    error_count += err
                    items_processed += 1

                pages_processed += 1
                next_page_url = data.get('next_page')

                state_obj.state_data['next_page_url'] = next_page_url
                state_obj.save(update_fields=['state_data', 'updated_at'])
                logger.debug(f"Saved state for key {state_key}. Next page: {next_page_url}")

                if not next_page_url or (max_items and items_processed >= max_items):
                    if max_items and items_processed >= max_items:
                        logger.info(f"Reached maximum items limit ({max_items}). Stopping.")
                    break

        except Exception as e:
            logger.exception("API Sync process interrupted due to an unexpected error.")
            raise e

        logger.info(
            f"API Sync cycle completed. Success: {success_count}, Errors: {error_count}. Pages processed: {pages_processed}.")
        return success_count, error_count

    def _process_item(self, item: dict) -> tuple[int, int]:
        success_count = 0
        error_count = 0
        item_id = item.get('id')

        payloads = map_kodik_item_to_jcp_payloads(item, self.plugin_id)

        for payload in payloads:
            response, status = self.adapter.send_payload(payload)
            if 200 <= status < 300:
                success_count += 1
            else:
                logger.error(f"Adapter rejected payload for Kodik ID {item_id}. HTTP Status: {status}")
                error_count += 1

        return success_count, error_count
