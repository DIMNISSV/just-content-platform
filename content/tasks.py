import logging
import requests
from celery import shared_task
from django.conf import settings
from .models import TrackGroup, AdditionalTrack

logger = logging.getLogger(__name__)


@shared_task
def push_track_group_to_hub(tg_id):
    hub_url = getattr(settings, 'HUB_URL', '').rstrip('/')
    hub_token = getattr(settings, 'HUB_API_TOKEN', '')

    if not hub_url or getattr(settings, 'PLATFORM_ROLE', 'NODE') != 'NODE':
        return

    try:
        tg = TrackGroup.objects.get(id=tg_id)
    except TrackGroup.DoesNotExist:
        return

    # Собираем данные сборки
    payload = {
        "tg_id": tg.id,
        "name": tg.name,
        "author": tg.author,
        "content_type": tg.content_type.model,  # 'title' or 'episode'
        "object_id": str(tg.object_id),
        "video_asset_id": str(tg.video_asset_id),
        "tracks": [
            {
                "asset_id": str(at.asset_id),
                "language": at.language,
                "author": at.author,
                "offset_ms": at.offset_ms
            } for at in tg.additional_tracks.all()
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {hub_token}"
    }

    try:
        resp = requests.post(f"{hub_url}/api/v1/aggregator/sync/track-group/", json=payload, headers=headers,
                             timeout=10)
        if resp.status_code == 200:
            logger.info(f"TrackGroup {tg_id} pushed to Hub")
        else:
            logger.error(f"Push TG failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"Network error pushing TG: {e}")
