import logging

import requests
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def push_delete_track_group_to_hub(tg_id_str):
    hub_url = getattr(settings, 'HUB_URL', '').rstrip('/')
    hub_token = getattr(settings, 'HUB_API_TOKEN', '')
    if not hub_url or getattr(settings, 'PLATFORM_ROLE', 'NODE') != 'NODE':
        return

    headers = {"Authorization": f"Bearer {hub_token}"}
    try:
        # Мы используем метод DELETE на тот же эндпоинт
        resp = requests.delete(
            f"{hub_url}/api/v1/aggregator/sync/track-group/?tg_id={tg_id_str}",
            headers=headers,
            timeout=10
        )
    except Exception as e:
        logger.error(f"Failed to delete TG on Hub: {e}")
