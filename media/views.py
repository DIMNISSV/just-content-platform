import logging

import requests
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.response import Response

from aggregator.utils import check_provider_auth
from media.tasks import trigger_lifeboat
from .models import Asset, AssetVariant, RawMediaFile
from .serializers import AssetSerializer, RawFileSerializer

logger = logging.getLogger(__name__)


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


# Обновляем AssetViewSet в media/views.py
class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для получения логических ассетов в Воркбенче (Только для админов).
    """
    serializer_class = AssetSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        # Локальные готовые ассеты
        return Asset.objects.filter(
            variants__status=AssetVariant.Status.READY
        ).prefetch_related(
            'variants', 'provider'
        ).distinct().order_back('-created_at')

    def get_permissions(self):
        # Если это HUB и в запросе есть Bearer токен — разрешаем (проверка токена будет в list)
        if getattr(settings, 'PLATFORM_ROLE', 'HUB') == 'HUB':
            return [AllowAny()]
        return [IsAdminUser()]

    def list(self, request, *args, **kwargs):
        # Проверка авторизации для HUB (от Провайдеров)
        if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'HUB':
            if not check_provider_auth(request) and not request.user.is_staff:
                return Response({"error": "Unauthorized"}, status=401)

        # 1. Получаем локальные ассеты через стандартный механизм
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        local_assets = serializer.data

        # 2. Если мы NODE — запрашиваем список ассетов у HUB
        if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'NODE':
            hub_url = getattr(settings, 'HUB_URL', '').rstrip('/')
            hub_token = getattr(settings, 'HUB_API_TOKEN', '')
            try:
                # Запрашиваем у HUB ассеты (HUB вернет реестр всех провайдеров)
                resp = requests.get(
                    f"{hub_url}/api/v1/media/assets/",
                    headers={"Authorization": f"Bearer {hub_token}"},
                    timeout=5
                )
                if resp.status_code == 200:
                    hub_data = resp.json()
                    remote_assets = hub_data.get('results', hub_data)

                    # Помечаем удаленные ассеты, чтобы отличить их в UI
                    for ra in remote_assets:
                        # Если ассет не локальный (ID нет в локальном списке)
                        if not any(la['id'] == ra['id'] for la in local_assets):
                            ra['is_remote'] = True
                            local_assets.append(ra)
            except Exception as e:
                logger.error(f"Failed to fetch assets from Hub: {e}")

        return Response(local_assets)

    def perform_destroy(self, instance):
        if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'NODE':
            hub_url = getattr(settings, 'HUB_URL', '').rstrip('/')
            hub_token = getattr(settings, 'HUB_API_TOKEN', '')

            # Спрашиваем Hub: есть ли зависимости?
            resp = requests.get(
                f"{hub_url}/api/v1/aggregator/sync/asset-check-lock/{instance.id}/",
                headers={"Authorization": f"Bearer {hub_token}"}
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get('is_locked'):
                    # Если заблокировано — инициируем Lifeboat и кидаем ошибку
                    trigger_lifeboat.delay(str(instance.id), data.get('dependent_providers'))
                    raise ValidationError(
                        "Asset is used by other providers. Migration started. Please try deleting later.")

        instance.delete()


@api_view(['POST'])
@permission_classes([AllowAny])
def lifeboat_download_view(request):
    """
    Эндпоинт на NODE. Вызывается HUB-ом.
    Приказывает узлу скачать ассет с другого узла, чтобы сохранить его.
    """
    # Проверка секрета HUB (webhook_secret)
    # ...

    asset_id = request.data.get('asset_id')
    source_url = request.data.get('source_url')  # Прямая ссылка на мастер-файл

    # Запускаем фоновую задачу скачивания и перехвата владения
    # download_and_rehost_asset.delay(asset_id, source_url)

    return Response({"status": "accepted"})
