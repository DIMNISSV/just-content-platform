from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TaxonomyItemViewSet,
    RawTermViewSet,
    RawTermMappingViewSet,
    trigger_sync_presets
)

router = DefaultRouter()
router.register(r'items', TaxonomyItemViewSet, basename='taxonomy-item')
router.register(r'raw-terms', RawTermViewSet, basename='raw-term')
router.register(r'mappings', RawTermMappingViewSet, basename='raw-term-mapping')

urlpatterns = [
    path('api/v1/taxonomy/', include(router.urls)),
    path('api/v1/taxonomy/sync-presets/', trigger_sync_presets, name='taxonomy-sync-presets'),
]
