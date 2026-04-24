import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


def fetch_single_manifest(entry):
    """
    Запрашивает манифест по зарегистрированному fetch_url плагина.
    Кеширует результат для предотвращения спама запросами.
    """
    cache_key = f"ext_manifest_{entry.id}"
    cached_data = cache.get(cache_key)

    if cached_data is not None:
        return cached_data

    headers = {"Content-Type": "application/json"}
    if entry.plugin.api_token:
        headers["Authorization"] = f"Bearer {entry.plugin.api_token}"

    try:
        # Поскольку плагин сам прислал нам fetch_url (например GET), делаем простой GET запрос
        resp = requests.get(entry.fetch_url, headers=headers, timeout=entry.plugin.timeout)
        if resp.status_code == 200:
            data = resp.json()
            sources = data.get('sources', [])

            # Инжектим имя провайдера в дорожки
            for s in sources:
                s['provider'] = entry.plugin.name

            cache.set(cache_key, sources, timeout=60 * 15)  # Кеш на 15 минут
            return sources
        else:
            logger.warning(f"Plugin {entry.plugin.name} returned status {resp.status_code} on {entry.fetch_url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Plugin {entry.plugin.name} error on fetch: {e}")

    return []


def fetch_registry_manifests(manifest_entries) -> list:
    """
    Асинхронно опрашивает все подтвержденные URL плагинов для сбора внешних дорожек.
    """
    if not manifest_entries:
        return []

    all_sources = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single_manifest, e) for e in manifest_entries]
        for future in as_completed(futures):
            all_sources.extend(future.result())

    return all_sources
