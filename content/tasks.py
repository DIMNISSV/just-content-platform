import io
import logging
import os

import requests
from PIL import Image
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile

from .models import Title

logger = logging.getLogger(__name__)


@shared_task
def download_and_save_poster(title_id, poster_url):
    """
    Downloads the poster image from the given URL, converts it to WebP,
    and saves it to the Title instance. Checks Redis cache first to avoid duplicates.
    """
    try:
        title = Title.objects.get(id=title_id)
        if title.poster and title.poster_url == poster_url:
            return

        keys_to_check = []
        if title.kp_id:
            keys_to_check.append(f"poster_idx:kp:{title.kp_id}")
        if title.imdb_id:
            keys_to_check.append(f"poster_idx:imdb:{title.imdb_id}")
        if title.shiki_id:
            keys_to_check.append(f"poster_idx:shiki:{title.shiki_id}")
        if title.mdl_id:
            keys_to_check.append(f"poster_idx:mdl:{title.mdl_id}")

        for key in keys_to_check:
            cached_path = cache.get(key)
            if cached_path:
                full_path = os.path.join(settings.MEDIA_ROOT, cached_path)
                if os.path.exists(full_path):
                    title.poster.name = cached_path
                    title.poster_url = poster_url
                    title._is_webhook_update = True
                    title.save(update_fields=['poster', 'poster_url'])
                    logger.info(f"Re-used existing poster from cache for Title {title_id}")
                    return

        response = requests.get(poster_url, timeout=15)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content))
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')

            webp_io = io.BytesIO()
            img.save(webp_io, format='WEBP', quality=85)

            kp = f"kp{title.kp_id}" if title.kp_id else "kp"
            imdb = f"imdb{title.imdb_id}" if title.imdb_id else "imdb"
            shiki = f"shiki{title.shiki_id}" if title.shiki_id else "shiki"
            mdl = f"mdl{title.mdl_id}" if title.mdl_id else "mdl"

            filename = f"poster_{title.id}_{kp}_{imdb}_{shiki}_{mdl}.webp"

            title.poster.save(filename, ContentFile(webp_io.getvalue()), save=False)
            title.poster_url = poster_url
            title._is_webhook_update = True
            title.save(update_fields=['poster', 'poster_url'])

            for key in keys_to_check:
                cache.set(key, title.poster.name, timeout=None)

            logger.info(f"Successfully downloaded, converted, and saved poster for Title {title_id}")
        else:
            logger.warning(f"Failed to download poster for Title {title_id}, HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading/converting poster for Title {title_id}: {str(e)}")
