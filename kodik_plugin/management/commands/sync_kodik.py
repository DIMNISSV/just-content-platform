import logging
from django.conf import settings
from django.core.management.base import BaseCommand

from kodik_plugin.adapters.http_adapter import HTTPWebhookAdapter
from kodik_plugin.adapters.local_adapter import LocalServiceAdapter
from kodik_plugin.client.list_api import KodikListClient
from kodik_plugin.client.dump_api import KodikDumpClient
from kodik_plugin.sync.orchestrator import KodikSyncOrchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronizes content from Kodik API or Database Dumps into JCP'

    def add_arguments(self, parser):
        # Targeting specific items
        parser.add_argument('--id', type=str, help='Sync specific Kodik ID')
        parser.add_argument('--shikimori-id', type=str, help='Sync specific Shikimori ID')
        parser.add_argument('--kinopoisk-id', type=str, help='Sync specific Kinopoisk ID')
        parser.add_argument('--imdb-id', type=str, help='Sync specific IMDb ID')

        # Dumps
        parser.add_argument('--dump', type=str, help='Use file dump instead of API (e.g., films, serials, films/anime)')

        # Updating existing titles in DB
        parser.add_argument('--update-existing', action='store_true', help='Update existing titles in DB')
        parser.add_argument('--update-type', type=str, choices=['SERIES', 'MOVIE', 'ALL'], default='SERIES',
                            help='Type of titles to update')
        parser.add_argument('--delay', type=float, default=0.5, help='Delay between API requests for existing updates')
        parser.add_argument('--stale-minutes', type=int, default=0, help='Update only titles older than N minutes')

        # Generic API Params
        parser.add_argument('--types', type=str, default='', help='Comma-separated Kodik content types for API')
        parser.add_argument('--sort', type=str, default='updated_at',
                            help='Sort field for API (e.g., updated_at, year)')
        parser.add_argument('--order', type=str, default='desc', help='Sort order for API (asc, desc)')

        # State and Limits
        parser.add_argument('--max-pages', type=int, default=0, help='Max pages to process (API only)')
        parser.add_argument('--max-items', type=int, default=0, help='Max items to process')
        parser.add_argument('--resume', action='store_true', help='Resume from last saved state')
        parser.add_argument('--state-key', type=str, default='', help='Custom key for state tracking')

        # Adapter
        parser.add_argument('--adapter', type=str, choices=['local', 'http'], default='local', help='Adapter to use')
        parser.add_argument('--webhook-url', type=str, default='', help='JCP Webhook URL (if HTTP adapter is used)')

    def handle(self, *args, **options):
        token = getattr(settings, 'KODIK_API_TOKEN', '')
        plugin_id = getattr(settings, 'KODIK_PLUGIN_ID', 1)
        webhook_secret = getattr(settings, 'KODIK_WEBHOOK_SECRET', '')

        if not token:
            self.stdout.write(self.style.ERROR("KODIK_API_TOKEN is missing in settings."))
            return

        adapter_type = options['adapter']
        if adapter_type == 'local':
            adapter = LocalServiceAdapter(plugin_id=plugin_id)
        else:
            webhook_url = options['webhook_url']
            if not webhook_url:
                self.stdout.write(self.style.ERROR("--webhook-url is required when using HTTP adapter."))
                return
            adapter = HTTPWebhookAdapter(webhook_url=webhook_url, secret_token=webhook_secret)

        if options['update_existing']:
            client = KodikListClient(token=token)
            orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)
            self.stdout.write(self.style.NOTICE(f"Starting to update existing {options['update_type']} titles..."))
            success, error = orchestrator.run_update_existing(
                title_type=options['update_type'],
                delay=options['delay'],
                stale_minutes=options['stale_minutes']
            )
            self.stdout.write(self.style.SUCCESS(f"Update done. Success: {success}, Errors: {error}."))
            return

        is_dump = bool(options['dump'])
        specific_ids = {
            'id': options['id'],
            'shikimori_id': options['shikimori_id'],
            'kinopoisk_id': options['kinopoisk_id'],
            'imdb_id': options['imdb_id']
        }
        active_specific_ids = {k: v for k, v in specific_ids.items() if v is not None}

        if is_dump:
            client = KodikDumpClient(token=token)
            orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)
            dump_name = options['dump']
            state_key = options['state_key'] or f"dump_sync_{dump_name.replace('/', '_')}"

            self.stdout.write(self.style.NOTICE(f"Starting dump sync for {dump_name}..."))
            success, error = orchestrator.run_sync_dump(
                dump_name=dump_name,
                resume=options['resume'],
                max_items=options['max_items'],
                state_key=state_key
            )
        else:
            client = KodikListClient(token=token)
            orchestrator = KodikSyncOrchestrator(client=client, adapter=adapter, plugin_id=plugin_id)
            state_key = options['state_key'] or 'api_sync_default'

            api_kwargs = {
                'sort': options['sort'],
                'order': options['order']
            }
            if options['types']:
                api_kwargs['types'] = options['types']

            use_search = False
            if active_specific_ids:
                api_kwargs.update(active_specific_ids)
                use_search = True
                self.stdout.write(self.style.WARNING("Specific ID provided. Using search endpoint. Resume ignored."))

            self.stdout.write(self.style.NOTICE("Starting API sync..."))
            success, error = orchestrator.run_sync_api(
                resume=options['resume'] if not active_specific_ids else False,
                max_pages=options['max_pages'],
                max_items=options['max_items'],
                state_key=state_key,
                use_search=use_search,
                **api_kwargs
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Successfully processed: {success}. Errors: {error}."))
