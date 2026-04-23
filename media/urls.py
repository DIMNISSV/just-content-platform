from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AssetViewSet, RawFileViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'raw-files', RawFileViewSet, basename='raw-file')

urlpatterns = [
    path('api/v1/media/', include(router.urls)),
]
