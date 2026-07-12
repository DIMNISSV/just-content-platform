MOVIE_TYPES = {
    'foreign-movie',
    'soviet-cartoon',
    'foreign-cartoon',
    'russian-cartoon',
    'anime',
    'russian-movie'
}

SERIES_TYPES = {
    'cartoon-serial',
    'documentary-serial',
    'russian-serial',
    'foreign-serial',
    'anime-serial',
    'multi-part-film'
}


def map_content_type(kodik_type: str) -> str:
    """
    Maps Kodik content type to JCP Domain Title.Type.
    """
    if kodik_type in MOVIE_TYPES:
        return 'MOVIE'
    return 'SERIES'


def normalize_link(link: str) -> str:
    """
    Normalizes Kodik iframe links to absolute URLs.
    """
    if link and link.startswith('//'):
        return f"https:{link}"
    return link
