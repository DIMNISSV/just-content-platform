import json
import logging
import time
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from content.models import Title
from kodik_plugin.adapters.base import BaseJCPAdapter
from kodik_plugin.client.dump_api import KodikDumpClient
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.mapper.episode_mapper import map_kodik_item_to_jcp_payloads
from kodik_plugin.mapper.title_mapper import extract_external_ids
from kodik_plugin.models import KodikSyncState, KodikDumpProcessedID

logger = logging.getLogger(__name__)


class KodikSyncOrchestrator:
    """
    Coordinates the synchronization process:
    Fetches data from Kodik API -> Maps to JCP format -> Sends via Adapter.
    """

    def __init__(self, client: KodikListClient | KodikDumpClient, adapter: BaseJCPAdapter, plugin_id: int):
        self.client = client
        self.adapter = adapter
        self.plugin_id = plugin_id

    def run_update_existing(self, title_type: str = 'SERIES', delay: float = 0.5, stale_minutes: int = 0) -> tuple[
        int, int]:
        logger.info(
            f"Starting update of existing titles. Type: {title_type}, Delay: {delay}s, Stale minutes: {stale_minutes}")

        query = ~Q(shiki_id='') | ~Q(kp_id='') | ~Q(imdb_id='') | ~Q(mdl_id='')
        qs = Title.objects.filter(query)

        if title_type in ['SERIES', 'MOVIE']:
            qs = qs.filter(type=title_type)

        if stale_minutes > 0:
            stale_threshold = timezone.now() - timedelta(minutes=stale_minutes)
            qs = qs.filter(updated_at__lt=stale_threshold)

        titles = qs.iterator()
        success_count, error_count, processed_count = 0, 0, 0

        for title in titles:
            search_kwargs = {}
            if title.kp_id:
                search_kwargs['kinopoisk_id'] = title.kp_id
            elif title.imdb_id:
                search_kwargs['imdb_id'] = title.imdb_id
            elif title.mdl_id:
                search_kwargs['mdl_id'] = title.mdl_id
            elif title.shiki_id:
                search_kwargs['shikimori_id'] = title.shiki_id
            else:
                continue

            try:
                data = self.client.get_page(use_search=True, **search_kwargs)
                results = data.get('results', [])

                if not results:
                    logger.debug(f"No results found in Kodik for Title {title.name} ({search_kwargs})")
                    if delay > 0:
                        time.sleep(delay)
                    continue

                for item in results:
                    succ, err = self._process_item(item)
                    success_count += succ
                    error_count += err

                processed_count += 1

            except Exception as e:
                logger.error(f"Error updating Title {title.name} ({title.id}): {e}")
                error_count += 1

            if delay > 0:
                time.sleep(delay)

        logger.info(
            f"Finished updating existing titles. Processed: {processed_count}. Success: {success_count}, Errors: {error_count}.")
        return success_count, error_count

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

    def run_sync_dump(self, dump_name: str, resume: bool = False, max_items: int = 0,
                      state_key: str = 'dump_sync_default', dry_run: bool = False) -> tuple[int, int]:
        logger.info(
            f"Starting Dump synchronization from {dump_name}. Resume: {resume}, Max Items: {max_items}, State Key: {state_key}, Dry Run: {dry_run}")

        if dry_run:
            logger.info("[DRY-RUN] Simulation mode active. No database changes will be made.")

        state_obj, _ = KodikSyncState.objects.get_or_create(key=state_key)
        start_index = state_obj.state_data.get('last_index', 0) if resume else 0

        if not hasattr(self.client, 'download_dump'):
            raise ValueError(
                "Provided client does not support dump downloads. Please supply a KodikDumpClient instance.")

        file_path = self.client.download_dump(dump_name)

        success_count, error_count, items_processed = 0, 0, 0
        titles_to_create = 0

        try:
            logger.info("Loading dump JSON into memory...")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Dump loaded. Total items in file: {len(data)}. Starting from index: {start_index}")

            for i in range(start_index, len(data)):
                if max_items and items_processed >= max_items:
                    logger.info(f"Reached maximum items limit ({max_items}). Stopping.")
                    break

                item = data[i]
                ext_ids = extract_external_ids(item)
                kp_id = ext_ids.get('kp_id')
                imdb_id = ext_ids.get('imdb_id')
                shiki_id = ext_ids.get('shiki_id')
                mdl_id = ext_ids.get('mdl_id')

                query = Q()
                if kp_id: query |= Q(kp_id=kp_id)
                if imdb_id: query |= Q(imdb_id=imdb_id)
                if shiki_id: query |= Q(shiki_id=shiki_id)
                if mdl_id: query |= Q(mdl_id=mdl_id)

                if not query:
                    items_processed += 1
                    continue

                # Filter check (same as real process)
                is_processed = KodikDumpProcessedID.objects.filter(query).exists()
                is_already_in_db = Title.objects.filter(query).exists()

                if is_processed or is_already_in_db:
                    items_processed += 1
                    continue

                if dry_run:
                    title_name = item.get('title', 'Unknown')
                    titles_to_create += 1
                    logger.info(f"[DRY-RUN] Title {title_name} would be created")
                    logger.info(
                        f"[DRY-RUN] Celery task deep_sync_kodik_title_task would be dispatched for episodes of this series")
                    logger.info(f"[DRY-RUN] Entry in KodikDumpProcessedID would be created for IDs: {ext_ids}")
                else:
                    # Real execution
                    succ, err = self._process_item(item)
                    success_count += succ
                    error_count += err

                    from kodik_plugin.tasks import deep_sync_kodik_title_task
                    deep_sync_kodik_title_task.delay(
                        kp_id=kp_id,
                        imdb_id=imdb_id,
                        shiki_id=shiki_id,
                        mdl_id=mdl_id
                    )

                    KodikDumpProcessedID.objects.create(
                        kp_id=kp_id,
                        imdb_id=imdb_id,
                        shiki_id=shiki_id,
                        mdl_id=mdl_id
                    )

                items_processed += 1

                if items_processed % 100 == 0:
                    if dry_run:
                        logger.info(f"[DRY-RUN] KodikSyncState would be updated (index: {i})")
                    else:
                        state_obj.state_data['last_index'] = i + 1
                        state_obj.save(update_fields=['state_data', 'updated_at'])

            if dry_run:
                logger.info(f"Dry run complete. Total titles to be created: {titles_to_create}")
                return titles_to_create, 0

            state_obj.state_data['last_index'] = start_index + items_processed
            state_obj.save(update_fields=['state_data', 'updated_at'])

        except Exception as e:
            logger.exception("Dump Sync process interrupted due to an unexpected error.")
            raise e

        logger.info(
            f"Dump Sync cycle completed. Success: {success_count}, Errors: {error_count}. Total items processed this run: {items_processed}.")
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
