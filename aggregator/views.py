import logging

from django.db import transaction, models
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.models import Title, Episode, AdditionalTrack, TrackGroup
from media.models import AssetVariant, Asset
from .models import PluginProvider, ExternalContentRegistry
from .utils import check_provider_auth

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def plugin_webhook_view(request):
    """
    Webhook endpoint for plugins to register their content in our platform.
    Expected JSON body:
    {
        "plugin_id": 1,
        "external_ids": {
            "imdb_id": "tt12345",
            "shiki_id": "123"
        },
        "content_type": "MANIFEST",
        "fetch_url": "https://plugin.com/manifest/123.json",
        "target_asset_uuid": "uuid-string-here" (optional),
        "season_number": 1 (optional),
        "episode_number": 1 (optional)
    }
    """
    data = request.data
    plugin_id = data.get('plugin_id')

    if not plugin_id:
        return Response({"error": "plugin_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plugin = PluginProvider.objects.get(id=plugin_id, is_active=True)
    except PluginProvider.DoesNotExist:
        return Response({"error": "Plugin not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

    # Security check: Validate webhook_secret if configured
    if plugin.webhook_secret:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({"error": "Missing or invalid Authorization header"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(' ')[1]
        if token != plugin.webhook_secret:
            return Response({"error": "Invalid webhook secret"}, status=status.HTTP_403_FORBIDDEN)

    # Soft Matching: Find Title by any provided external ID
    external_ids = data.get('external_ids', {})
    if not external_ids:
        return Response({"error": "external_ids mapping is required"}, status=status.HTTP_400_BAD_REQUEST)

    valid_id_fields = ['imdb_id', 'tmdb_id', 'kp_id', 'shiki_id', 'mal_id', 'mdl_id', 'wa_id']
    query = Q()
    for key, val in external_ids.items():
        if key in valid_id_fields and val:
            query |= Q(**{key: val})

    if not query:
        return Response({"error": "No valid external ID fields provided"}, status=status.HTTP_400_BAD_REQUEST)

    title = Title.objects.filter(query).first()
    if not title:
        return Response({"error": "Matching title not found in platform database"}, status=status.HTTP_404_NOT_FOUND)

    # Optional: Find Episode
    episode = None
    season_num = data.get('season_number')
    episode_num = data.get('episode_number')
    if season_num is not None and episode_num is not None:
        episode = Episode.objects.filter(title=title, season_number=season_num, episode_number=episode_num).first()
        if not episode:
            return Response({"error": "Matching episode not found"}, status=status.HTTP_404_NOT_FOUND)

    # Upsert the Registry Entry
    content_type = data.get('content_type')
    target_asset_uuid = data.get('target_asset_uuid')
    fetch_url = data.get('fetch_url')

    if not content_type or not fetch_url:
        return Response({"error": "content_type and fetch_url are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        registry_entry, created = ExternalContentRegistry.objects.update_or_create(
            plugin=plugin,
            title=title,
            episode=episode,
            content_type=content_type,
            target_asset_uuid=target_asset_uuid if target_asset_uuid else None,
            defaults={
                'external_id': str(list(external_ids.values())[0]),  # Store the primary reported ID
                'fetch_url': fetch_url
            }
        )
        logger.info(f"Plugin {plugin.name} registered {content_type} for {title.name}")
        return Response({
            "status": "success",
            "registry_id": registry_entry.id,
            "created": created
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error saving registry entry: {str(e)}")
        return Response({"error": "Internal server error during registration"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def asset_sync_view(request):
    """
    Принимает метаданные об успешно сгенерированном Ассете от узла Провайдера (NODE).
    Ожидаемый формат JSON:
    {
        "asset_id": "uuid",
        "type": "VIDEO",
        "variants":[
            {
                "variant_id": "uuid",
                "quality_label": "1080p",
                "storage_path": "assets/..."
            }
        ]
    }
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return Response({"error": "Missing or invalid Authorization header"}, status=status.HTTP_401_UNAUTHORIZED)

    token = auth_header.split(' ')[1]
    try:
        # Аутентификация Провайдера по токену
        plugin = PluginProvider.objects.get(api_token=token, is_active=True)
    except PluginProvider.DoesNotExist:
        return Response({"error": "Invalid token or inactive provider"}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    asset_id = data.get('asset_id')
    asset_type = data.get('type')
    variants_data = data.get('variants', [])

    if not asset_id or not asset_type:
        return Response({"error": "asset_id and type are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            # Создаем или обновляем виртуальный Asset, привязанный к Провайдеру
            asset, created = Asset.objects.update_or_create(
                id=asset_id,
                defaults={
                    'type': asset_type,
                    'provider': plugin,
                }
            )

            # Синхронизируем готовые варианты
            for v_data in variants_data:
                AssetVariant.objects.update_or_create(
                    id=v_data.get('variant_id'),
                    defaults={
                        'asset': asset,
                        'quality_label': v_data.get('quality_label', ''),
                        'storage_path': v_data.get('storage_path', ''),
                        'status': AssetVariant.Status.READY,
                        'progress': 100
                    }
                )

        logger.info(f"Successfully synced virtual Asset {asset_id} from provider {plugin.name}")
        return Response({"status": "success", "asset_id": str(asset.id)}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error syncing asset {asset_id}: {str(e)}")
        return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'DELETE'])
@permission_classes([AllowAny])
def track_group_sync_view(request):
    provider = check_provider_auth(request)
    if not provider:
        return Response({"error": "Unauthorized"}, status=401)

    if request.method == 'DELETE':
        tg_id = request.query_params.get('tg_id')
        if not tg_id: return Response({"error": "tg_id is required"}, status=400)
        count, _ = TrackGroup.objects.filter(id=tg_id, provider=provider).delete()
        return Response({"status": "deleted", "count": count})

    data = request.data
    try:
        with transaction.atomic():
            from django.contrib.contenttypes.models import ContentType
            ctype = ContentType.objects.get(app_label='content', model=data['content_type'])

            # 1. ГАРАНТИРУЕМ НАЛИЧИЕ ВИДЕО-АССЕТА (Stub)
            # Если HUB еще не знает об этом ассете, создаем его виртуальную копию
            video_asset, _ = Asset.objects.get_or_create(
                id=data['video_asset_id'],
                defaults={'type': Asset.Type.VIDEO, 'provider': provider}
            )

            # 2. Создаем/обновляем группу
            tg, _ = TrackGroup.objects.update_or_create(
                id=data['tg_id'],
                defaults={
                    'name': data['name'],
                    'author': data['author'],
                    'provider': provider,
                    'content_type': ctype,
                    'object_id': data['object_id'],
                    'video_asset': video_asset
                }
            )

            # 3. Обновляем дополнительные треки
            tg.additional_tracks.all().delete()
            for t_data in data['tracks']:
                # Также гарантируем наличие аудио-ассета
                audio_asset, _ = Asset.objects.get_or_create(
                    id=t_data['asset_id'],
                    defaults={'type': Asset.Type.AUDIO, 'provider': provider}
                )

                AdditionalTrack.objects.create(
                    track_group=tg,
                    asset=audio_asset,
                    language=t_data.get('language', 'und'),
                    author=t_data.get('author', ''),
                    offset_ms=t_data.get('offset_ms', 0)
                )

        return Response({"status": "synced"})
    except Exception as e:
        logger.error(f"Sync TG Error on HUB: {str(e)}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def check_asset_lock_view(request, asset_id):
    provider = check_provider_auth(request)
    # Ищем группы, использующие этот ассет, автором которых НЕ является текущий провайдер
    dependents = TrackGroup.objects.filter(
        models.Q(video_asset_id=asset_id) | models.Q(additional_tracks__asset_id=asset_id)
    ).exclude(provider=provider).select_related('provider')

    if dependents.exists():
        provider_emails = list(dependents.values_list('provider__api_token', flat=True))  # Или эмейлы для уведомлений
        return Response({
            "is_locked": True,
            "dependent_providers": provider_emails
        })

    return Response({"is_locked": False})


@api_view(['POST'])
@permission_classes([AllowAny])
def metadata_sync_view(request):
    """Принимает новые Title/Episode от NODE и сохраняет их в глобальную базу HUB."""
    provider = check_provider_auth(request)
    if not provider:
        return Response({"error": "Unauthorized"}, status=401)

    payload = request.data
    m_type = payload.get('type')
    data = payload.get('data')

    try:
        with transaction.atomic():
            if m_type == 'title':
                obj, _ = Title.objects.update_or_create(
                    id=data['id'],
                    defaults={
                        'name': data['name'],
                        'original_name': data['original_name'],
                        'description': data['description'],
                        'release_year': data['release_year'],
                        'type': data['type_choice']
                    }
                )
            elif m_type == 'episode':
                obj, _ = Episode.objects.update_or_create(
                    id=data['id'],
                    defaults={
                        'title_id': data['title_id'],
                        'season_number': data['season_number'],
                        'episode_number': data['episode_number'],
                        'name': data['name']
                    }
                )
        return Response({"status": "success", "id": str(obj.id)})
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def trigger_migration_view(request, asset_id):
    """
    HUB получает сигнал от владельца ассета: 'Я хочу удалить файл'.
    HUB находит всех, кто использует это видео, и отправляет им команду Lifeboat.
    """
    owner_provider = check_provider_auth(request)
    if not owner_provider:
        return Response({"error": "Unauthorized"}, status=401)

    # Находим всех КРОМЕ владельца, кто использует этот ассет в своих сборках
    dependents = TrackGroup.objects.filter(
        models.Q(video_asset_id=asset_id) | models.Q(additional_tracks__asset_id=asset_id)
    ).exclude(provider=owner_provider).select_related('provider').distinct()

    if not dependents.exists():
        return Response({"status": "no_dependents_found"})

    # Для каждого зависимого провайдера инициируем команду скачивания (Lifeboat)
    # В реальной системе здесь будет вызов Webhook-а на сторону NODE
    for tg in dependents:
        target_node_url = tg.provider.endpoint_url.rsplit('/', 2)[0]  # Базовый URL ноды
        logger.warning(f"SENDING LIFEBOAT COMMAND TO {tg.provider.name} AT {target_node_url} FOR ASSET {asset_id}")
        # Здесь должен быть requests.post(f"{target_node_url}/api/v1/media/lifeboat/download/", ...)
        # Мы реализуем этот эндпоинт на стороне NODE в следующем шаге.

    return Response({"status": "migration_started", "count": dependents.count()})
