import logging

import requests

from .base import BaseJCPAdapter

logger = logging.getLogger(__name__)


class HTTPWebhookAdapter(BaseJCPAdapter):
    """
    Sends payloads to the JCP Aggregator over HTTP.
    Useful when the plugin is deployed as an isolated microservice.
    """

    def __init__(self, webhook_url: str, secret_token: str, timeout: int = 10):
        self.webhook_url = webhook_url
        self.secret_token = secret_token
        self.timeout = timeout
        self.session = requests.Session()
        if self.secret_token:
            self.session.headers.update({"Authorization": f"Bearer {self.secret_token}"})

    def send_payload(self, payload: dict) -> tuple[dict, int]:
        try:
            response = self.session.post(self.webhook_url, json=payload, timeout=self.timeout)
            try:
                data = response.json()
            except ValueError:
                data = {"error": "Invalid JSON response from JCP"}
            return data, response.status_code
        except requests.RequestException as e:
            logger.error(f"HTTPWebhookAdapter failed to send payload: {e}")
            return {"error": str(e)}, 500
