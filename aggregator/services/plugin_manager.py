import json
import logging

from django.utils.module_loading import import_string
from django_celery_beat.models import PeriodicTask, CrontabSchedule

logger = logging.getLogger(__name__)


def sync_plugin_tasks(plugin):
    """
    Synchronizes tasks from a local plugin provider with the database scheduler.
    """
    if not plugin.is_local or not plugin.app_label:
        return

    prefix = f"plugin_{plugin.id}_{plugin.app_label}_"

    if not plugin.is_active:
        PeriodicTask.objects.filter(name__startswith=prefix).update(enabled=False)
        return

    try:
        provider_cls = import_string(f"{plugin.app_label}.provider.PluginProvider")
    except ImportError as e:
        logger.error(f"Failed to load provider for app {plugin.app_label}: {e}")
        return

    provider = provider_cls()
    tasks = provider.get_periodic_tasks()

    existing_tasks = set(PeriodicTask.objects.filter(name__startswith=prefix).values_list('name', flat=True))
    active_tasks = set()

    for task_info in tasks:
        task_name = f"{prefix}{task_info['name']}"
        active_tasks.add(task_name)

        crontab_data = task_info.get('schedule', {})
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=crontab_data.get('minute', '*'),
            hour=crontab_data.get('hour', '*'),
            day_of_week=crontab_data.get('day_of_week', '*'),
            day_of_month=crontab_data.get('day_of_month', '*'),
            month_of_year=crontab_data.get('month_of_year', '*')
        )

        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': task_info['task'],
                'crontab': schedule,
                'kwargs': json.dumps(task_info.get('kwargs', {})),
                'enabled': True
            }
        )

    tasks_to_disable = existing_tasks - active_tasks
    if tasks_to_disable:
        PeriodicTask.objects.filter(name__in=tasks_to_disable).update(enabled=False)


def remove_plugin_tasks(plugin):
    """
    Removes all scheduled tasks associated with a local plugin.
    """
    if not plugin.is_local or not plugin.app_label:
        return
    prefix = f"plugin_{plugin.id}_{plugin.app_label}_"
    PeriodicTask.objects.filter(name__startswith=prefix).delete()