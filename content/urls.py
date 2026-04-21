from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TitleViewSet, player_manifest, rate_track_group,
    player_telemetry, continue_watching, recommendations, WatchView, save_workbench, EpisodeWatchView,
    player_external_sources
)

router = DefaultRouter()
router.register(r'titles', TitleViewSet, basename='title')

urlpatterns = [
    path('api/v1/content/', include(router.urls)),
    path('api/v1/player/manifest/<str:content_type_str>/<int:object_id>/', player_manifest, name='player-manifest'),
    path('api/v1/player/manifest/external/<str:content_type_str>/<int:object_id>/', player_external_sources,
         name='player-external-sources'),
    path('api/v1/player/rate-track/<int:group_id>/', rate_track_group, name='rate-track'),

    # Telemetry and History
    path('api/v1/player/telemetry/', player_telemetry, name='player-telemetry'),
    path('api/v1/content/history/', continue_watching, name='continue-watching'),
    path('api/v1/content/recommendations/', recommendations, name='recommendations'),
    path('watch/<int:pk>/', WatchView.as_view(), name='watch'),
    path('watch/episode/<int:pk>/', EpisodeWatchView.as_view(), name='watch-episode'),
    path('api/v1/content/workbench/save/<str:content_type_str>/<int:object_id>/', save_workbench,
         name='save-workbench'),
]
