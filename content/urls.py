from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TitleViewSet, player_manifest

router = DefaultRouter()
router.register(r'titles', TitleViewSet, basename='title')

urlpatterns = [
    path('api/v1/content/', include(router.urls)),
    path('api/v1/player/manifest/<str:content_type_str>/<int:object_id>/', player_manifest, name='player-manifest'),
]
