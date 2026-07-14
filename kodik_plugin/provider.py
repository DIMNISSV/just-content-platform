from aggregator.providers.base import BaseLocalProvider


class PluginProvider(BaseLocalProvider):
    def get_periodic_tasks(self) -> list[dict]:
        return [
            {
                "name": "sync-kodik-updates-hourly",
                "task": "kodik_plugin.tasks.sync_kodik_updates_task",
                "schedule": {"minute": "13"},
                "kwargs": {"limit": 100}
            },
            {
                "name": "update-existing-series-daily",
                "task": "kodik_plugin.tasks.update_existing_titles_task",
                "schedule": {"hour": "4", "minute": "7"},
                "kwargs": {"title_type": "SERIES", "delay": 0.5, "stale_minutes": 60}
            }
        ]

    def refresh_title(self, title_id: str) -> None:
        from .tasks import refresh_single_title_task
        refresh_single_title_task.delay(title_id)
