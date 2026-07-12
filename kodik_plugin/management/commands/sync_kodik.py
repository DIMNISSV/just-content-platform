import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from kodik_plugin.adapters.http_adapter import HTTPWebhookAdapter
from kodik_plugin.adapters.local_adapter import LocalServiceAdapter
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.sync.orchestrator import KodikSyncOrchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronizes content from Kodik API into JCP'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Items per page limit')
        parser.add_argument('--sort', type=str, default='updated_at', help='Sort field (e.g., updated_at, year)')
        parser.add_argument('--order', type=str, default='desc', help='Sort order (asc, desc)')
        parser.add_argument('--types', type=str, default='', help='Comma-separated Kodik content types')
        parser.add_argument('--adapter', type=str, choices=['local', 'http'], default='local', help='Adapter to use')
        parser.add_argument('--webhook-url', type=str, default='', help='JCP Webhook URL (if HTTP adapter is used)')

    def handle(self, *args, **options):
        token = getattr(settings, 'KODIK_API_TOKEN', '')
        plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
        webhook_secret = getattr(settings, 'KODIK_WEBHOOK_SECRET', '')

        if not token:
            self.stdout.write(self.style.ERROR("KODIK_API_TOKEN is missing in settings."))
            return

        client = KodikListClient(token=token)

        adapter_type = options['adapter']
        if adapter_type == 'local':
            adapter = LocalServiceAdapter(plugin_id=plugin_id)
        else:
            webhook_url = options['webhook_url']
            if not webhook_url:
                self.stdout.write(self.style.ERROR("--webhook-url is required when using HTTP adapter."))
                return
            adapter = HTTPWebhookAdapter(webhook_url=webhook_url, secret_token=webhook_secret)

        orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)

        sync_kwargs = {
            'limit': options['limit'],
            'sort': options['sort'],
            'order': options['order']
        }
        if options['types']:
            sync_kwargs['types'] = options['types']

        self.stdout.write(self.style.NOTICE(f"Starting sync using {adapter_type} adapter..."))

        success, error = orchestrator.run_sync(**sync_kwargs)

        self.stdout.write(self.style.SUCCESS(f"Done. Successfully processed: {success}. Errors: {error}."))
