from django.urls import path

from .mock_views import mock_manifest_view, mock_iframe_view
from .views import plugin_webhook_view, asset_sync_view, track_group_sync_view, metadata_sync_view, \
    check_asset_lock_view, trigger_migration_view

urlpatterns = [
    path('api/v1/aggregator/webhook/', plugin_webhook_view, name='plugin_webhook'),
    path('api/v1/aggregator/sync/asset/', asset_sync_view, name='asset_sync'),
    path('api/v1/aggregator/sync/track-group/', track_group_sync_view, name='track_group_sync'),
    path('api/mock-plugin/manifest/', mock_manifest_view, name='mock_manifest'),
    path('api/mock-plugin/iframe/', mock_iframe_view, name='mock_iframe'),
    path('api/v1/aggregator/sync/metadata/', metadata_sync_view, name='metadata_sync'),
    path('api/v1/aggregator/sync/asset-check-lock/<uuid:asset_id>/', check_asset_lock_view, name='asset_check_lock'),
    path('api/v1/aggregator/sync/trigger-migration/<uuid:asset_id>/', trigger_migration_view, name='trigger_migration'),
]
