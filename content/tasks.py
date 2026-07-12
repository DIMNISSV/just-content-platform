import logging

import requests
from celery import shared_task
from django.core.files.base import ContentFile

from .models import Title

logger = logging.getLogger(__name__)


@shared_task
def download_and_save_poster(title_id, poster_url):
    """
    Downloads the poster image from the given URL and saves it to the Title instance.
    """
    try:
        title = Title.objects.get(id=title_id)
        if title.poster and title.poster_url == poster_url:
            logger.info(f"Poster for Title {title_id} is already up to date.")
            return

        response = requests.get(poster_url, timeout=15)
        if response.status_code == 200:
            filename = f"poster_{title_id}.jpg"
            title.poster.save(filename, ContentFile(response.content), save=False)
            title.poster_url = poster_url

            title._is_webhook_update = True
            title.save(update_fields=['poster', 'poster_url'])
            logger.info(f"Successfully downloaded and saved poster for Title {title_id}")
        else:
            logger.warning(f"Failed to download poster for Title {title_id}, HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading poster for Title {title_id}: {str(e)}")
