from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser

from .models import Asset, AssetVariant, RawMediaFile
from .serializers import AssetSerializer, RawFileSerializer


class RawFileViewSet(viewsets.ModelViewSet):
    """
    API для управления сырыми файлами. Поддерживает загрузку файлов (Multipart).
    """
    queryset = RawMediaFile.objects.all().order_by('-created_at')
    serializer_class = RawFileSerializer
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        file_obj = self.request.data.get('file')
        if file_obj:
            serializer.save(original_name=file_obj.name)
        else:
            serializer.save()


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для получения логических ассетов в Воркбенче (Только для админов).
    """
    serializer_class = AssetSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Asset.objects.filter(
            variants__status=AssetVariant.Status.READY
        ).prefetch_related(
            Prefetch('variants', queryset=AssetVariant.objects.filter(status=AssetVariant.Status.READY))
        ).distinct().order_by('-created_at')
