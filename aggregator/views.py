import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist

from .models import PluginProvider
from .services import process_plugin_payload
from .services.session_manager import SessionManager
from .services.telemetry_processor import TelemetryProcessor

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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def player_session_start(request):
    content_type_str = request.data.get('content_type')
    object_id = request.data.get('object_id')

    if not content_type_str or not object_id:
        return Response({"error": "content_type and object_id are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ctype = ContentType.objects.get(app_label='content', model=content_type_str.lower())
    except ContentType.DoesNotExist:
        return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)

    session = SessionManager.create_session(
        user=request.user,
        content_type=ctype,
        object_id=object_id
    )

    return Response({
        "session_token": str(session.id),
        "expires_at": session.expires_at
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def player_session_heartbeat(request):
    session_id = request.data.get('session_token')
    if not session_id:
        return Response({"error": "session_token is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        session = SessionManager.extend_session(session_id)
        return Response({
            "status": "extended",
            "expires_at": session.expires_at
        }, status=status.HTTP_200_OK)
    except ObjectDoesNotExist:
        return Response({"error": "Session not found or expired"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def player_session_telemetry(request):
    session_token = request.data.get('session_token')
    if not session_token:
        return Response({"error": "session_token is required"}, status=status.HTTP_400_BAD_REQUEST)

    response_data, status_code = TelemetryProcessor.process_session_telemetry(
        session_token=session_token,
        payload=request.data
    )
    return Response(response_data, status=status_code)
