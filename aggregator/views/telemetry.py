from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from aggregator.services.telemetry_processor import TelemetryProcessor


@csrf_exempt
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
