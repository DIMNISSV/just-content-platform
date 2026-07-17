from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from aggregator.services.session_manager import SessionManager


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


@csrf_exempt
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
