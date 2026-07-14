from abc import ABC, abstractmethod


class BaseLocalProvider(ABC):
    """
    Abstract interface defining the contract for local plugins executed within the JCP monolith.
    """

    @abstractmethod
    def get_periodic_tasks(self) -> list[dict]:
        """
        Returns a list of periodic tasks to be registered in the Celery Beat scheduler.
        Format example:
        [
            {
                "name": "sync-hourly",
                "task": "my_plugin.tasks.sync_task",
                "schedule": {"minute": "15", "hour": "*"},
                "kwargs": {"limit": 100}
            }
        ]
        """
        pass

    @abstractmethod
    def refresh_title(self, title_id: str) -> None:
        """
        Triggers an immediate background refresh for a specific title.
        """
        pass
