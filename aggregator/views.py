import logging

from django.db.models import Q
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.models import Title, Episode, Genre
from content.tasks import download_and_save_poster
from .models import PluginProvider, ExternalContentRegistry

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
    title_meta = data.get('title_metadata')

    if not title:
        if not plugin.allow_title_creation:
            return Response({"error": "Title not found and creation is disabled"}, status=status.HTTP_404_NOT_FOUND)
        if not title_meta:
            return Response({"error": "Title not found and no title_metadata provided"},
                            status=status.HTTP_400_BAD_REQUEST)

        title = Title(
            type=title_meta.get('type', Title.Type.MOVIE),
            name=title_meta.get('name', 'Unknown'),
            original_name=title_meta.get('original_name', ''),
            description=title_meta.get('description', ''),
            release_year=title_meta.get('release_year'),
            metadata_priority_level=plugin.metadata_priority
        )
        for k, v in external_ids.items():
            if k in valid_id_fields and v:
                setattr(title, k, str(v))

        title._is_webhook_update = True
        title.save()

        genres_data = title_meta.get('genres')
        if genres_data:
            genre_objs = []
            for g_name in genres_data:
                slug = slugify(g_name, allow_unicode=True)
                g_obj, _ = Genre.objects.get_or_create(slug=slug, defaults={'name': g_name})
                genre_objs.append(g_obj)
            title.genres.set(genre_objs)

        poster_url = title_meta.get('poster_url')
        if poster_url:
            download_and_save_poster.delay(title.id, poster_url)
    else:
        if plugin.allow_title_update and title_meta:
            updated = False
            prio = plugin.metadata_priority
            curr_prio = title.metadata_priority_level

            def try_update(field_name, new_val):
                nonlocal updated
                if not new_val:
                    return
                curr_val = getattr(title, field_name)
                if not curr_val:
                    setattr(title, field_name, new_val)
                    updated = True
                elif prio >= curr_prio and curr_val != new_val:
                    setattr(title, field_name, new_val)
                    updated = True

            try_update('name', title_meta.get('name'))
            try_update('original_name', title_meta.get('original_name'))
            try_update('description', title_meta.get('description'))
            try_update('release_year', title_meta.get('release_year'))
            try_update('type', title_meta.get('type'))

            for k, v in external_ids.items():
                if k in valid_id_fields and v and not getattr(title, k):
                    setattr(title, k, str(v))
                    updated = True

            if updated:
                title.metadata_priority_level = max(curr_prio, prio)
                title._is_webhook_update = True
                title.save()

            genres_data = title_meta.get('genres')
            if genres_data is not None:
                if not title.genres.exists() or prio >= curr_prio:
                    genre_objs = []
                    for g_name in genres_data:
                        slug = slugify(g_name, allow_unicode=True)
                        g_obj, _ = Genre.objects.get_or_create(slug=slug, defaults={'name': g_name})
                        genre_objs.append(g_obj)
                    title.genres.set(genre_objs)

            poster_url = title_meta.get('poster_url')
            if poster_url:
                if not title.poster or prio >= curr_prio:
                    download_and_save_poster.delay(title.id, poster_url)

    episodes_meta = data.get('episodes_metadata', [])
    if title.type == Title.Type.SERIES and episodes_meta:
        for ep_data in episodes_meta:
            s_num = ep_data.get('season_number')
            e_num = ep_data.get('episode_number')
            if s_num is None or e_num is None:
                continue

            ep = Episode.objects.filter(title=title, season_number=s_num, episode_number=e_num).first()
            if not ep:
                if plugin.allow_title_creation:
                    ep = Episode(
                        title=title,
                        season_number=s_num,
                        episode_number=e_num,
                        name=ep_data.get('name', ''),
                        description=ep_data.get('description', ''),
                        metadata_priority_level=plugin.metadata_priority
                    )
                    ep._is_webhook_update = True
                    ep.save()
            else:
                if plugin.allow_title_update:
                    ep_updated = False
                    prio = plugin.metadata_priority
                    curr_prio = ep.metadata_priority_level

                    ep_name = ep_data.get('name')
                    if ep_name:
                        if not ep.name:
                            ep.name = ep_name
                            ep_updated = True
                        elif prio >= curr_prio and ep.name != ep_name:
                            ep.name = ep_name
                            ep_updated = True

                    ep_desc = ep_data.get('description')
                    if ep_desc:
                        if not ep.description:
                            ep.description = ep_desc
                            ep_updated = True
                        elif prio >= curr_prio and ep.description != ep_desc:
                            ep.description = ep_desc
                            ep_updated = True

                    if ep_updated:
                        ep.metadata_priority_level = max(curr_prio, prio)
                        ep._is_webhook_update = True
                        ep.save()

    episode = None
    season_num = data.get('season_number')
    episode_num = data.get('episode_number')
    if season_num is not None and episode_num is not None:
        episode = Episode.objects.filter(title=title, season_number=season_num, episode_number=episode_num).first()
        if not episode:
            if plugin.allow_title_creation:
                episode = Episode(
                    title=title,
                    season_number=season_num,
                    episode_number=episode_num,
                    metadata_priority_level=plugin.metadata_priority
                )
                episode._is_webhook_update = True
                episode.save()
            else:
                return Response({"error": "Matching episode not found and creation disabled"},
                                status=status.HTTP_404_NOT_FOUND)

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
                'external_id': str(list(external_ids.values())[0]),
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
