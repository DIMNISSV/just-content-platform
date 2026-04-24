from django.urls import path

from .mock_views import mock_manifest_view, mock_iframe_view
from .views import plugin_webhook_view

urlpatterns = [
    path('api/v1/aggregator/webhook/', plugin_webhook_view, name='plugin_webhook'),
    path('api/mock-plugin/manifest/', mock_manifest_view, name='mock_manifest'),
    path('api/mock-plugin/iframe/', mock_iframe_view, name='mock_iframe'),
]
