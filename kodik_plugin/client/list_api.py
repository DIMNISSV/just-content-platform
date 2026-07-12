from typing import Generator

from .base import KodikBaseClient


class KodikListClient(KodikBaseClient):
    """
    Client for interacting with the /list Kodik API endpoint.
    Provides lazy fetching using pagination.
    """
    BASE_URL = "https://kodik-api.com/list"
    SEARCH_URL = "https://kodik-api.com/search"

    def iter_list(self, limit: int = 50, sort: str = 'updated_at', order: str = 'desc', types: str = None, **kwargs) -> \
            Generator[dict, None, None]:
        """
        Iterates over the Kodik library, automatically handling the 'next_page' token.
        Yields individual items.
        """
        url = self.BASE_URL
        params = {
            'limit': limit,
            'sort': sort,
            'order': order,
            'with_episodes_data': 'true',
            'with_material_data': 'true'
        }

        if types:
            params['types'] = types

        params.update(kwargs)

        while url:
            data = self._request('GET', url, params=params)
            results = data.get('results', [])

            for item in results:
                yield item

            next_url = data.get('next_page')
            if not next_url:
                break

            url = next_url
            params = {}

    def get_page(self, next_page_url: str = None, use_search: bool = False, **kwargs) -> dict:
        """
        Fetches a single page of results.
        If next_page_url is provided, it ignores kwargs and fetches that exact URL.
        """
        if next_page_url:
            return self._request('GET', next_page_url)

        params = {
            'with_episodes_data': 'true',
            'with_material_data': 'true'
        }
        params.update(kwargs)

        url = self.SEARCH_URL if use_search else self.BASE_URL
        return self._request('GET', url, params=params)
