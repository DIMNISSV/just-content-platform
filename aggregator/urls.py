from django.urls import path

from .mock_views import mock_manifest_view, mock_iframe_view
from .views import (
    plugin_webhook_view,
    player_session_start,
    player_session_heartbeat,
    player_session_telemetry
)

urlpatterns = [
    path('api/v1/aggregator/webhook/', plugin_webhook_view, name='plugin_webhook'),
    path('api/mock-plugin/manifest/', mock_manifest_view, name='mock_manifest'),
    path('api/mock-plugin/iframe/', mock_iframe_view, name='mock_iframe'),
    path('api/v1/player/session/start/', player_session_start, name='player-session-start'),
    path('api/v1/player/session/heartbeat/', player_session_heartbeat, name='player-session-heartbeat'),
    path('api/v1/player/session-telemetry/', player_session_telemetry, name='player-session-telemetry'),
]
