import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.cache import cache
from .models import PluginProvider

logger = logging.getLogger(__name__)


def fetch_from_plugin(plugin: PluginProvider, external_ids: dict) -> list:
    """
    Опрашивает конкретный плагин. Результат кешируется на 15 минут,
    чтобы не положить внешние API при наплыве пользователей.
    """
    # Создаем уникальный ключ кеша на основе ID плагина и внешних ID тайтла
    ids_hash = "_".join([f"{k}:{v}" for k, v in sorted(external_ids.items())])
    cache_key = f"plugin_{plugin.id}_{ids_hash}"

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    payload = {"external_ids": external_ids}
    headers = {"Content-Type": "application/json"}
    if plugin.api_token:
        headers["Authorization"] = f"Bearer {plugin.api_token}"

    try:
        resp = requests.post(plugin.endpoint_url, json=payload, headers=headers, timeout=plugin.timeout)
        if resp.status_code == 200:
            data = resp.json()  # Ожидаем, что плагин вернет массив PlaybackSource
            if isinstance(data, list):
                cache.set(cache_key, data, timeout=60 * 15)  # Кеш 15 минут
                return data
        else:
            logger.warning(f"Plugin {plugin.name} returned status {resp.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Plugin {plugin.name} error: {e}")

    return []


def get_external_sources(external_ids: dict) -> list:
    """
    Собирает источники со всех активных плагинов параллельно.
    """
    if not external_ids:
        return []

    active_plugins = PluginProvider.objects.filter(is_active=True)
    if not active_plugins.exists():
        return []

    all_sources = []

    # Параллельный опрос всех доноров
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_from_plugin, p, external_ids) for p in active_plugins]
        for future in as_completed(futures):
            all_sources.extend(future.result())

    return all_sources
