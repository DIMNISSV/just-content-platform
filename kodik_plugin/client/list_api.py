from typing import Generator

from .base import KodikBaseClient


class KodikListClient(KodikBaseClient):
    """
    Client for interacting with the /list Kodik API endpoint.
    Provides lazy fetching using pagination.
    """
    BASE_URL = "https://kodikapi.com/list"

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
