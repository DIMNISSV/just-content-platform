from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from .models import Asset, AssetVariant
from .serializers import AssetSerializer


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для получения логических ассетов в Воркбенче (Только для админов).
    """
    serializer_class = AssetSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        # Возвращаем логические ассеты, у которых есть хотя бы один READY вариант
        return Asset.objects.filter(
            variants__status=AssetVariant.Status.READY
        ).prefetch_related(
            # Подтягиваем только READY варианты, чтобы не отправлять на фронт битые
            Prefetch('variants', queryset=AssetVariant.objects.filter(status=AssetVariant.Status.READY))
        ).distinct().order_by('-created_at')
