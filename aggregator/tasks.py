import logging

import requests
from celery import shared_task

from .models import PluginProvider, ExternalContentRegistry

logger = logging.getLogger(__name__)


@shared_task
def verify_plugin_registry():
    """
    Background task to verify the integrity of external content.
    Sends batches of external_ids to the plugin's /verify endpoint.
    If the plugin omits an ID from 'valid_ids' in the response,
    the stale registry entry is deleted from our database.
    """
    plugins = PluginProvider.objects.filter(is_active=True)
    batch_size = 500

    for plugin in plugins:
        # Assuming the verify endpoint is at the root path + /verify
        # e.g., http://plugin.com/api/resolve -> http://plugin.com/api/verify
        base_path = plugin.endpoint_url.rsplit('/', 1)[0]
        verify_url = f"{base_path}/verify"

        all_ids_qs = ExternalContentRegistry.objects.filter(plugin=plugin).values_list('external_id',
                                                                                       flat=True).distinct()
        all_ids = list(all_ids_qs)

        if not all_ids:
            continue

        headers = {"Content-Type": "application/json"}
        if plugin.api_token:
            headers["Authorization"] = f"Bearer {plugin.api_token}"

        invalid_ids_to_delete = []

        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i:i + batch_size]
            payload = {"external_ids": batch}

            try:
                response = requests.post(verify_url, json=payload, headers=headers, timeout=plugin.timeout)
                if response.status_code == 200:
                    data = response.json()
                    valid_ids = set(data.get('valid_ids', []))

                    # IDs that we sent but were not returned as valid
                    missing_ids = set(batch) - valid_ids
                    invalid_ids_to_delete.extend(missing_ids)
                else:
                    logger.warning(f"Verification failed for {plugin.name}. HTTP {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error during verification for {plugin.name}: {e}")

        if invalid_ids_to_delete:
            deleted_count, _ = ExternalContentRegistry.objects.filter(
                plugin=plugin,
                external_id__in=invalid_ids_to_delete
            ).delete()
            logger.info(f"Garbage Collector: Removed {deleted_count} stale entries for {plugin.name}.")
