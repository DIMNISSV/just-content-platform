import logging
import requests
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class KodikBaseClient:
    """
    Base HTTP client for Kodik API.
    Handles session management, authentication, and error wrapping.
    """

    def __init__(self, token: str, timeout: int = 15):
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method: str, url: str, **kwargs) -> dict:
        params = kwargs.pop('params', {})

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        if 'token' not in query_params:
            params['token'] = self.token

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(result)
            return result
        except requests.RequestException as e:
            logger.error(f"Kodik API network error: {str(e)}")
            raise
