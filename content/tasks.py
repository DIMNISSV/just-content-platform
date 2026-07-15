import io
import logging
import os

import requests
from PIL import Image
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q

from .models import Title

logger = logging.getLogger(__name__)


@shared_task
def download_and_save_poster(title_id, poster_url):
    """
    Downloads the poster image from the given URL, converts it to WebP,
    and saves it to the Title instance. Checks DB and disk first to avoid duplicates.
    """
    try:
        title = Title.objects.get(id=title_id)
        if title.poster and title.poster_url == poster_url:
            return

        query = Q()
        if title.kp_id: query |= Q(kp_id=title.kp_id)
        if title.imdb_id: query |= Q(imdb_id=title.imdb_id)
        if title.shiki_id: query |= Q(shiki_id=title.shiki_id)
        if title.mdl_id: query |= Q(mdl_id=title.mdl_id)

        if query:
            existing = Title.objects.exclude(id=title.id).filter(query).exclude(poster='').first()
            if existing:
                title.poster.name = existing.poster.name
                title.poster_url = poster_url
                title._is_webhook_update = True
                title.save(update_fields=['poster', 'poster_url'])
                logger.info(f"Re-used existing poster from Title {existing.id} for Title {title_id}")
                return

        posters_dir = os.path.join(settings.MEDIA_ROOT, 'posters')
        if os.path.exists(posters_dir) and query:
            for file_name in os.listdir(posters_dir):
                if not file_name.endswith('.webp'):
                    continue

                match = False
                if title.kp_id and f"_kp{title.kp_id}_" in file_name:
                    match = True
                elif title.imdb_id and f"_imdb{title.imdb_id}_" in file_name:
                    match = True
                elif title.shiki_id and f"_shiki{title.shiki_id}_" in file_name:
                    match = True
                elif title.mdl_id and (f"_mdl{title.mdl_id}.webp" in file_name or f"_mdl{title.mdl_id}_" in file_name):
                    match = True

                if match:
                    title.poster.name = f"posters/{file_name}"
                    title.poster_url = poster_url
                    title._is_webhook_update = True
                    title.save(update_fields=['poster', 'poster_url'])
                    logger.info(f"Re-used existing poster {file_name} from disk for Title {title_id}")
                    return

        # 3. Download and Save
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

            filename = f"poster_{kp}_{imdb}_{shiki}_{mdl}.webp"
            rel_path = f"posters/{filename}"

            if default_storage.exists(rel_path):
                default_storage.delete(rel_path)

            title.poster.save(filename, ContentFile(webp_io.getvalue()), save=False)
            title.poster_url = poster_url
            title._is_webhook_update = True
            title.save(update_fields=['poster', 'poster_url'])

            logger.info(f"Successfully downloaded, converted, and saved poster for Title {title_id}")
        else:
            logger.warning(f"Failed to download poster for Title {title_id}, HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading/converting poster for Title {title_id}: {str(e)}")
