from .base import map_content_type


def extract_title_metadata(item: dict) -> dict:
    """
    Extracts normalized JCP title metadata from a Kodik API item.
    Supports data merging from KinoPoisk, Shikimori, and MyDramaList fields.
    """
    mat_data = item.get('material_data', {})

    name = mat_data.get('title') or mat_data.get('anime_title') or item.get('title', 'Unknown')
    orig_name = mat_data.get('title_en') or item.get('title_orig', '')
    year = mat_data.get('year') or item.get('year')
    description = mat_data.get('description') or mat_data.get('anime_description', '')
    poster_url = mat_data.get('poster_url') or mat_data.get('anime_poster_url') or mat_data.get('drama_poster_url', '')
    genres = mat_data.get('all_genres') or mat_data.get('genres') or mat_data.get('anime_genres', [])

    return {
        "type": map_content_type(item.get('type', '')),
        "name": name,
        "original_name": orig_name,
        "description": description,
        "release_year": int(year) if year else None,
        "genres": genres,
        "poster_url": poster_url
    }


def extract_external_ids(item: dict) -> dict:
    """
    Extracts external mapping IDs to guarantee idempotent synchronization.
    """
    ext_ids = {}
    if item.get('kinopoisk_id'):
        ext_ids['kp_id'] = str(item['kinopoisk_id'])
    if item.get('imdb_id'):
        ext_ids['imdb_id'] = str(item['imdb_id'])
    if item.get('shikimori_id'):
        ext_ids['shiki_id'] = str(item['shikimori_id'])
    if item.get('mdl_id'):
        ext_ids['mdl_id'] = str(item['mdl_id'])
    return ext_ids
