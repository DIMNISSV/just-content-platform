import logging

from celery import shared_task
from django.conf import settings

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
    Celery task to update already existing titles in the database
    with fresh data from the Kodik API (useful for ongoing series).
    """
    token = getattr(settings, 'KODIK_API_TOKEN', '')
    plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
    if not token:
        logger.error("KODIK_API_TOKEN is not configured in Django settings. Aborting update task.")
        return "Failed: Missing KODIK_API_TOKEN"
    try:
        client = KodikListClient(token=token)
        adapter = LocalServiceAdapter(plugin_id=plugin_id)
        orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)
        logger.info(f"Starting background update for existing {title_type} titles (Stale > {stale_minutes}m).")
        success, error = orchestrator.run_update_existing(
            title_type=title_type,
            delay=delay,
            stale_minutes=stale_minutes
        )
        return f"Update complete. Success: {success}, Errors: {error}"
    except Exception as e:
        logger.exception("Fatal error occurred during background existing titles update.")
        return f"Failed: {str(e)}"
