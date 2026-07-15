import logging
import os
import re

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from content.models import Title

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Indexes existing WebP posters into Redis cache and links them to Titles missing posters'

    def handle(self, *args, **options):
        posters_dir = os.path.join(settings.MEDIA_ROOT, 'posters')
        if not os.path.exists(posters_dir):
            self.stdout.write(self.style.ERROR("Posters directory does not exist."))
            return

        # Поддержка как старого формата с UUID, так и нового без него
        pattern1 = re.compile(r'^poster_.*?_kp(.*?)_imdb(.*?)_shiki(.*?)_mdl(.*?)\.webp$')
        pattern2 = re.compile(r'^poster_kp(.*?)_imdb(.*?)_shiki(.*?)_mdl(.*?)\.webp$')
        count = 0

        for entry in os.scandir(posters_dir):
            if entry.is_file() and entry.name.endswith('.webp'):
                match = pattern1.match(entry.name) or pattern2.match(entry.name)
                if match:
                    kp, imdb, shiki, mdl = match.groups()
                    rel_path = f"posters/{entry.name}"

                    keys = []
                    if kp:
                        keys.append(f"poster_idx:kp:{kp}")
                    if imdb:
                        keys.append(f"poster_idx:imdb:{imdb}")
                    if shiki:
                        keys.append(f"poster_idx:shiki:{shiki}")
                    if mdl:
                        keys.append(f"poster_idx:mdl:{mdl}")

                    for key in keys:
                        cache.set(key, rel_path, timeout=None)

                    if keys:
                        count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully indexed {count} posters into Redis."))

        titles_missing = Title.objects.filter(poster='')
        linked = 0

        for t in titles_missing:
            keys_to_check = []
            if t.kp_id:
                keys_to_check.append(f"poster_idx:kp:{t.kp_id}")
            if t.imdb_id:
                keys_to_check.append(f"poster_idx:imdb:{t.imdb_id}")
            if t.shiki_id:
                keys_to_check.append(f"poster_idx:shiki:{t.shiki_id}")
            if t.mdl_id:
                keys_to_check.append(f"poster_idx:mdl:{t.mdl_id}")

            for key in keys_to_check:
                cached_path = cache.get(key)
                if cached_path:
                    full_path = os.path.join(settings.MEDIA_ROOT, cached_path)
                    if os.path.exists(full_path):
                        t.poster.name = cached_path
                        t._is_webhook_update = True
                        t.save(update_fields=['poster'])
                        linked += 1
                        break

        self.stdout.write(self.style.SUCCESS(f"Successfully linked {linked} missing posters to existing titles."))
