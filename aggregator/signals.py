from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import PluginProvider
from .services.plugin_manager import sync_plugin_tasks, remove_plugin_tasks


@receiver(post_save, sender=PluginProvider)
def handle_plugin_save(sender, instance, **kwargs):
    sync_plugin_tasks(instance)


@receiver(post_delete, sender=PluginProvider)
def handle_plugin_delete(sender, instance, **kwargs):
    remove_plugin_tasks(instance)
