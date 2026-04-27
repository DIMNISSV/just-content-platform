import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.models import Title, Episode, AdditionalTrack, TrackGroup
from media.models import AssetVariant, Asset
from .models import PluginProvider, ExternalContentRegistry

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


@api_view(['POST'])
@permission_classes([AllowAny])
def track_group_sync_view(request):
    # 1. Auth check (используем уже написанный check_provider_auth или inline)
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(' ')[1] if auth_header else ''
    provider = PluginProvider.objects.filter(api_token=token, is_active=True).first()

    if not provider:
        return Response({"error": "Unauthorized"}, status=401)

    data = request.data
    try:
        with transaction.atomic():
            from django.contrib.contenttypes.models import ContentType
            ctype = ContentType.objects.get(app_label='content', model=data['content_type'])

            # Создаем/обновляем группу
            tg, _ = TrackGroup.objects.update_or_create(
                id=data['tg_id'],
                defaults={
                    'name': data['name'],
                    'author': data['author'],
                    'provider': provider,
                    'content_type': ctype,
                    'object_id': data['object_id'],
                    'video_asset_id': data['video_asset_id']
                }
            )

            # Обновляем треки
            tg.additional_tracks.all().delete()
            for t_data in data['tracks']:
                AdditionalTrack.objects.create(
                    track_group=tg,
                    asset_id=t_data['asset_id'],
                    language=t_data['language'],
                    author=t_data['author'],
                    offset_ms=t_data['offset_ms']
                )

        return Response({"status": "synced"})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
