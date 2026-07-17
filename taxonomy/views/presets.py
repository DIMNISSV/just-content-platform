from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from taxonomy.services import sync_taxonomy_presets


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_sync_presets(request):
    result = sync_taxonomy_presets()
    if result['status'] == 'success':
        return Response(result, status=status.HTTP_200_OK)
    return Response(result, status=status.HTTP_400_BAD_REQUEST)
