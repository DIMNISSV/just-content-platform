from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AssetViewSet, RawFileViewSet, lifeboat_download_view

router = DefaultRouter()
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'raw-files', RawFileViewSet, basename='raw-file')

urlpatterns = [
    path('api/v1/media/', include(router.urls)),
    path('api/v1/media/lifeboat/download/', lifeboat_download_view, name='lifeboat_download'),
]
