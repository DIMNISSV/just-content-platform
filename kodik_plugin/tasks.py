import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from kodik_plugin.adapters.local_adapter import LocalServiceAdapter
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
