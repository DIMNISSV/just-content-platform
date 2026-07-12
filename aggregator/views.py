import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PluginProvider
from .services import process_plugin_payload

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def plugin_webhook_view(request):
    data = request.data
    plugin_id = data.get('plugin_id')
    if not plugin_id:
        return Response({"error": "plugin_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plugin = PluginProvider.objects.get(id=plugin_id, is_active=True)
    except PluginProvider.DoesNotExist:
        return Response({"error": "Plugin not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

    if plugin.webhook_secret:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({"error": "Missing or invalid Authorization header"}, status=status.HTTP_401_UNAUTHORIZED)
        token = auth_header.split(' ')[1]
        if token != plugin.webhook_secret:
            return Response({"error": "Invalid webhook secret"}, status=status.HTTP_403_FORBIDDEN)

    response_data, status_code = process_plugin_payload(plugin, data)
    return Response(response_data, status=status_code)
