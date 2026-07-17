import json
import logging
import os
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from kodik_plugin.adapters.local_adapter import LocalServiceAdapter
from kodik_plugin.client.dump_api import KodikDumpClient
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.sync.orchestrator import KodikSyncOrchestrator

logger = logging.getLogger(__name__)


@shared_task
def sync_kodik_updates_task(limit: int = 100):
    """
    Celery task for incremental synchronization of Kodik content.
    Usually triggered periodically (e.g., every hour) to fetch the latest updates.
    """
    token = getattr(settings, 'KODIK_API_TOKEN', '')
    plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
    if not token:
        logger.error("KODIK_API_TOKEN is not configured in Django settings. Aborting sync task.")
        return "Failed: Missing KODIK_API_TOKEN"
    try:
        client = KodikListClient(token=token)
        adapter = LocalServiceAdapter(plugin_id=plugin_id)
        orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)
        logger.info(f"Starting background Kodik sync for the latest {limit} items.")
        success, error = orchestrator.run_sync_api(
            resume=False,
            max_items=limit,
            sort='updated_at',
            order='desc'
        )
        return f"Sync complete. Success: {success}, Errors: {error}"
    except Exception as e:
        logger.exception("Fatal error occurred during background Kodik sync execution.")
        return f"Failed: {str(e)}"


@shared_task
def update_existing_titles_task(title_type: str = 'SERIES', delay: float = 0.5, stale_minutes: int = 1440):
    """
    Celery dispatcher task to update already existing titles in the database
    with fresh data from the Kodik API (useful for ongoing series).
    Dispatches a single atomic task for each title.
    """
    from content.models import Title

    logger.info(f"Starting Fan-Out update dispatcher for existing {title_type} titles (Stale > {stale_minutes}m).")

    query = ~Q(shiki_id='') | ~Q(kp_id='') | ~Q(imdb_id='') | ~Q(mdl_id='')
    qs = Title.objects.filter(query)

    if title_type in ['SERIES', 'MOVIE']:
        qs = qs.filter(type=title_type)

    if stale_minutes > 0:
        stale_threshold = timezone.now() - timedelta(minutes=stale_minutes)
        qs = qs.filter(updated_at__lt=stale_threshold)

    title_ids = qs.values_list('id', flat=True)
    count = 0

    for t_id in title_ids:
        refresh_single_title_task.delay(str(t_id))
        count += 1

    return f"Update dispatcher complete. Queued {count} titles for refresh."


@shared_task
def refresh_single_title_task(title_id: str):
    """
    On-Demand refresh for a specific title directly through the Kodik API.
    """
    from content.models import Title

    try:
        title = Title.objects.get(id=title_id)
    except Title.DoesNotExist:
        return

    token = getattr(settings, 'KODIK_API_TOKEN', '')
    plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
    if not token:
        return

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
        return

    client = KodikListClient(token=token)
    adapter = LocalServiceAdapter(plugin_id=plugin_id)
    orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)

    try:
        data = client.get_page(use_search=True, **search_kwargs)
        results = data.get('results', [])
        for item in results:
            orchestrator._process_item(item)
    except Exception as e:
        logger.error(f"Error during single title refresh for {title_id}: {e}")


@shared_task
def deep_sync_kodik_title_task(kp_id=None, imdb_id=None, shiki_id=None, mdl_id=None):
    """
    Asynchronously queries the Kodik search API for a given title's external IDs
    and processes the complete metadata tree (seasons, episodes) via Celery.
    """
    token = getattr(settings, 'KODIK_API_TOKEN', '')
    plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
    if not token:
        logger.error("KODIK_API_TOKEN is not configured in Django settings. Aborting deep sync task.")
        return "Failed: Missing KODIK_API_TOKEN"

    search_kwargs = {}
    if kp_id:
        search_kwargs['kinopoisk_id'] = kp_id
    elif imdb_id:
        search_kwargs['imdb_id'] = imdb_id
    elif shiki_id:
        search_kwargs['shikimori_id'] = shiki_id
    elif mdl_id:
        search_kwargs['mdl_id'] = mdl_id

    if not search_kwargs:
        return "Ignored: No external IDs provided"

    try:
        client = KodikListClient(token=token)
        adapter = LocalServiceAdapter(plugin_id=plugin_id)
        orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)

        logger.info(f"Starting async deep sync for {search_kwargs}")
        data = client.get_page(use_search=True, **search_kwargs)
        results = data.get('results', [])

        success_count, error_count = 0, 0
        for item in results:
            succ, err = orchestrator._process_item(item)
            success_count += succ
            error_count += err

        return f"Deep sync done. Success: {success_count}, Errors: {error_count}"
    except Exception as e:
        logger.exception(f"Fatal error occurred during background deep sync execution for {search_kwargs}.")
        return f"Failed: {str(e)}"


@shared_task
def sync_dump_dispatcher_task(dump_name: str, max_items: int = 0, dry_run: bool = False, chunk_size: int = 1000):
    import ijson

    token = getattr(settings, 'KODIK_API_TOKEN', '')
    if not token:
        logger.error("KODIK_API_TOKEN is missing. Aborting dump dispatcher.")
        return "Failed: Missing Token"

    client = KodikDumpClient(token=token)
    try:
        file_path = client.download_dump(dump_name)
    except Exception as e:
        logger.error(f"Failed to download dump {dump_name}: {e}")
        return "Failed: Dump Download Error"

    chunk_files = []
    current_chunk = []
    chunk_index = 0
    items_processed = 0

    logger.info(f"Starting chunked parsing of dump {dump_name} via ijson.")

    try:
        with open(file_path, 'rb') as f:
            for item in ijson.items(f, 'item'):
                if max_items and items_processed >= max_items:
                    break

                current_chunk.append(item)
                items_processed += 1

                if len(current_chunk) >= chunk_size:
                    chunk_filename = f"{file_path}_chunk_{chunk_index}.json"
                    with open(chunk_filename, 'w', encoding='utf-8') as cf:
                        json.dump(current_chunk, cf)
                    chunk_files.append(chunk_filename)

                    process_dump_chunk_task.delay(chunk_filename, dry_run)

                    current_chunk = []
                    chunk_index += 1

        if current_chunk:
            chunk_filename = f"{file_path}_chunk_{chunk_index}.json"
            with open(chunk_filename, 'w', encoding='utf-8') as cf:
                json.dump(current_chunk, cf)
            chunk_files.append(chunk_filename)
            process_dump_chunk_task.delay(chunk_filename, dry_run)

    except Exception as e:
        logger.exception(f"Failed during dump chunking for {dump_name}")
        raise e
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    logger.info(f"Dispatched {len(chunk_files)} chunks ({items_processed} items) for dump {dump_name}")
    return f"Dispatched {len(chunk_files)} chunks."


@shared_task
def process_dump_chunk_task(chunk_file_path: str, dry_run: bool = False):
    from content.models import Title
    from kodik_plugin.models import KodikDumpProcessedID
    from kodik_plugin.mapper.title_mapper import extract_external_ids

    if not os.path.exists(chunk_file_path):
        return f"File {chunk_file_path} not found"

    with open(chunk_file_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
    adapter = LocalServiceAdapter(plugin_id=plugin_id)
    orchestrator = KodikSyncOrchestrator(client=None, adapter=adapter, plugin_id=plugin_id)

    success_count, error_count = 0, 0
    titles_to_create = 0

    try:
        for item in items:
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
                continue

            is_processed = KodikDumpProcessedID.objects.filter(query).exists()
            is_already_in_db = Title.objects.filter(query).exists()

            if is_processed or is_already_in_db:
                continue

            if dry_run:
                titles_to_create += 1
            else:
                succ, err = orchestrator._process_item(item)
                success_count += succ
                error_count += err

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
    finally:
        if os.path.exists(chunk_file_path):
            os.remove(chunk_file_path)

    if dry_run:
        return f"[DRY-RUN] Would create {titles_to_create} titles."

    return f"Chunk processed. Success: {success_count}, Errors: {error_count}"
