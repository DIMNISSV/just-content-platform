from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from .models import Asset
from .serializers import AssetSerializer


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для получения готовых ассетов в Воркбенче (Только для админов).
    """
    queryset = Asset.objects.filter(status=Asset.Status.READY).order_by('-created_at')
    serializer_class = AssetSerializer
    permission_classes = [IsAdminUser]
