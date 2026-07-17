from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TitleViewSet, player_manifest, rate_track_group,
    player_telemetry, episode_player_telemetry, continue_watching, WatchView, save_workbench,
    EpisodeWatchView,
    GenreViewSet, CatalogView, content_tree_api, assign_file_api, EpisodeViewSet,
    TrackGroupViewSet, AdditionalTrackViewSet
)

router = DefaultRouter()
router.register(r'titles', TitleViewSet, basename='title')
router.register(r'genres', GenreViewSet, basename='genre')
router.register(r'episodes', EpisodeViewSet, basename='episode')
router.register(r'track-groups', TrackGroupViewSet, basename='track-group')
router.register(r'additional-tracks', AdditionalTrackViewSet, basename='additional-track')

urlpatterns = [
    path('api/v1/content/', include(router.urls)),
    path('api/v1/player/manifest/<str:content_type_str>/<uuid:object_id>/', player_manifest, name='player-manifest'),
    path('api/v1/player/rate-track/<uuid:group_id>/', rate_track_group, name='rate-track'),
    path('api/v1/player/telemetry/', player_telemetry, name='player-telemetry'),
    path('api/v1/player/episode-telemetry/', episode_player_telemetry, name='episode-player-telemetry'),
    path('api/v1/content/history/', continue_watching, name='continue-watching'),
    path('watch/episode/<uuid:pk>/', EpisodeWatchView.as_view(), name='watch-episode'),
    path('api/v1/content/workbench/save/<str:content_type_str>/<uuid:object_id>/', save_workbench,
         name='save-workbench'),
    path('api/v1/content/tree/', content_tree_api, name='content-tree'),
    path('api/v1/content/assign-file/', assign_file_api, name='assign-file'),
    path('watch/<uuid:pk>/', WatchView.as_view(), name='watch'),
    path('catalog/', CatalogView.as_view(), name='catalog'),
]
