from abc import ABC, abstractmethod


class BaseJCPAdapter(ABC):
    """
    Abstract interface for dispatching mapped payloads to the JCP Aggregator.
    """

    @abstractmethod
    def send_payload(self, payload: dict) -> tuple[dict, int]:
        """
        Sends the payload to JCP.
        Returns a tuple: (response_dict, http_status_code)
        """
        pass
