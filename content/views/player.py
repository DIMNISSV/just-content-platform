from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from aggregator.models import ExternalContentRegistry
from aggregator.services import fetch_registry_manifests
from content.models import Title, Episode, TrackGroup, WatchHistory, TrackGroupRating
from content.serializers import WatchHistorySerializer
from content.services.history_service import update_episode_progress, update_title_progress
from recommendations.services.velocity import log_title_view


@api_view(['POST'])
def rate_track_group(request, group_id):
    if not request.user.is_authenticated:
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    score = request.data.get('score')
    if not score or not isinstance(score, int) or not (1 <= score <= 10):
        return Response({"error": "Invalid score"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        track_group = TrackGroup.objects.get(id=group_id)
    except TrackGroup.DoesNotExist:
        return Response({"error": "TrackGroup not found"}, status=status.HTTP_404_NOT_FOUND)
    TrackGroupRating.objects.update_or_create(
        user=request.user,
        track_group=track_group,
        defaults={'score': score}
    )
    track_group.refresh_from_db()
    return Response({"status": "rated", "new_score": track_group.rating_score})


@api_view(['GET'])
def player_manifest(request, content_type_str, object_id):
    if content_type_str.lower() == 'title':
        ctype = ContentType.objects.get_for_model(Title)
    elif content_type_str.lower() == 'episode':
        ctype = ContentType.objects.get_for_model(Episode)
    else:
        return Response({"error": "invalid content type"}, status=400)
    track_groups = TrackGroup.objects.filter(
        content_type=ctype,
        object_id=object_id
    ).prefetch_related(
        'video_asset__variants__preset',
        'additional_tracks__asset__variants'
    ).order_by('-rating_score')
    sources = []
    for tg in track_groups:
        if tg.video_asset:
            v_variants = tg.video_asset.variants.filter(status='READY').order_by('-preset__width')
            qualities = [
                {
                    "variant_id": str(v.id),
                    "label": v.quality_label or "Original",
                    "storage_path": v.get_absolute_url()
                } for v in v_variants
            ]
            if qualities:
                sources.append({
                    "id": f"video_{tg.id}",
                    "asset_id": str(tg.video_asset.id),
                    "type": "VIDEO",
                    "sync_group_id": str(tg.id),
                    "group_title": tg.name,
                    "group_author": tg.author,
                    "offset_ms": 0,
                    "qualities": qualities,
                    "active_path": qualities[0]["storage_path"]
                })
        for extra in tg.additional_tracks.all():
            if extra.asset:
                a_variants = extra.asset.variants.filter(status='READY')
                qualities = [
                    {
                        "variant_id": str(v.id),
                        "label": v.quality_label or "Original",
                        "storage_path": v.get_absolute_url()
                    } for v in a_variants
                ]
                if qualities:
                    sources.append({
                        "id": f"extra_{extra.id}",
                        "asset_id": str(extra.asset.id),
                        "type": extra.asset.type,
                        "sync_group_id": str(tg.id),
                        "group_title": tg.name,
                        "group_author": tg.author,
                        "offset_ms": extra.offset_ms,
                        "meta_info": {"language": extra.language, "author": extra.author},
                        "qualities": qualities,
                        "active_path": qualities[0]["storage_path"]
                    })
    domain = getattr(request, 'tenant_domain', None)
    registry_qs = ExternalContentRegistry.objects.select_related('plugin').filter(plugin__is_active=True)
    if content_type_str.lower() == 'title':
        registry_qs = registry_qs.filter(title_id=object_id, episode__isnull=True)
    else:
        registry_qs = registry_qs.filter(episode_id=object_id)
    valid_entries = []
    for entry in registry_qs:
        allowed = entry.plugin.allowed_domains
        if not allowed or '*' in allowed or domain in allowed:
            valid_entries.append(entry)
    manifest_entries = []
    for entry in valid_entries:
        if entry.content_type in [ExternalContentRegistry.ContentTypeChoices.EPISODE_IFRAME,
                                  ExternalContentRegistry.ContentTypeChoices.ENTITY_IFRAME]:
            sources.append({
                "id": f"ext_iframe_{entry.id}",
                "asset_id": str(entry.id),
                "type": "EXTERNAL_PLAYER",
                "provider": entry.plugin.name,
                "storage_path": entry.fetch_url,
                "sync_group_id": f"ext_group_{entry.id}",
                "group_title": f"External Player ({entry.plugin.name})"
            })
        elif entry.content_type == ExternalContentRegistry.ContentTypeChoices.MANIFEST:
            manifest_entries.append(entry)
    ext_manifest_sources = fetch_registry_manifests(manifest_entries)
    sources.extend(ext_manifest_sources)
    next_episode_id = None
    if content_type_str.lower() == 'episode':
        try:
            current_ep = Episode.objects.get(id=object_id)
            next_ep = Episode.objects.filter(
                title=current_ep.title,
                season_number=current_ep.season_number,
                episode_number__gt=current_ep.episode_number
            ).order_by('episode_number').first()
            if not next_ep:
                next_ep = Episode.objects.filter(
                    title=current_ep.title,
                    season_number__gt=current_ep.season_number
                ).order_by('season_number', 'episode_number').first()
            if next_ep:
                next_episode_id = str(next_ep.id)
        except Episode.DoesNotExist:
            pass
    return Response({
        "content_id": str(object_id),
        "next_episode_id": next_episode_id,
        "sources": sources
    })


@api_view(['POST'])
def player_telemetry(request):
    data = request.data
    guest_id = data.get('guest_id')
    user = request.user if request.user.is_authenticated else None

    if not user and not guest_id:
        return Response({"error": "Unauthorized or missing guest_id"}, status=status.HTTP_401_UNAUTHORIZED)

    title_id = data.get('title_id')
    if not title_id:
        return Response({"error": "title_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        title = Title.objects.get(id=title_id)
    except Title.DoesNotExist:
        return Response({"error": "Title not found"}, status=status.HTTP_404_NOT_FOUND)

    episode_id = data.get('episode_id')
    track_group_id = data.get('track_group_id')
    audio_asset_id = data.get('audio_asset_id')
    audio_track_name = data.get('audio_track_name')
    quality_label = data.get('quality_label')
    progress_ms = data.get('progress_ms', 0)
    is_completed = data.get('is_completed', False)

    track_group = None
    if track_group_id:
        try:
            track_group = TrackGroup.objects.get(id=track_group_id)
        except TrackGroup.DoesNotExist:
            pass

    viewer_id = str(user.id) if user else str(guest_id)

    if episode_id:
        try:
            episode = Episode.objects.get(id=episode_id)
            episode_history, title_history = update_episode_progress(
                user=user,
                episode=episode,
                progress_ms=progress_ms,
                is_completed=is_completed,
                track_group=track_group,
                last_audio_asset_id=audio_asset_id,
                last_audio_track_name=audio_track_name,
                last_quality_label=quality_label,
                guest_id=guest_id
            )

            log_title_view(str(title.id), viewer_id)

            return Response({"status": "saved", "progress_ms": episode_history.progress_ms})
        except Episode.DoesNotExist:
            return Response({"error": "Episode not found"}, status=status.HTTP_404_NOT_FOUND)
    else:
        title_history = update_title_progress(
            user=user,
            title=title,
            progress_ms=progress_ms,
            is_completed=is_completed,
            track_group=track_group,
            last_audio_asset_id=audio_asset_id,
            last_audio_track_name=audio_track_name,
            last_quality_label=quality_label,
            guest_id=guest_id
        )

        log_title_view(str(title.id), viewer_id)

        return Response({"status": "saved", "progress_ms": title_history.progress_ms})


@api_view(['POST'])
def episode_player_telemetry(request):
    data = request.data
    guest_id = data.get('guest_id')
    user = request.user if request.user.is_authenticated else None

    if not user and not guest_id:
        return Response({"error": "Unauthorized or missing guest_id"}, status=status.HTTP_401_UNAUTHORIZED)

    episode_id = data.get('episode_id')
    if not episode_id:
        return Response({"error": "episode_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        episode = Episode.objects.get(id=episode_id)
    except Episode.DoesNotExist:
        return Response({"error": "Episode not found"}, status=status.HTTP_404_NOT_FOUND)

    progress_ms = data.get('progress_ms', 0)
    is_completed = data.get('is_completed', False)

    track_group_id = data.get('track_group_id')
    track_group = None
    if track_group_id:
        try:
            track_group = TrackGroup.objects.get(id=track_group_id)
        except TrackGroup.DoesNotExist:
            pass

    audio_asset_id = data.get('audio_asset_id')
    audio_track_name = data.get('audio_track_name')
    quality_label = data.get('quality_label')

    episode_history, title_history = update_episode_progress(
        user=user,
        episode=episode,
        progress_ms=progress_ms,
        is_completed=is_completed,
        track_group=track_group,
        last_audio_asset_id=audio_asset_id,
        last_audio_track_name=audio_track_name,
        last_quality_label=quality_label,
        guest_id=guest_id
    )

    viewer_id = str(user.id) if user else str(guest_id)
    log_title_view(str(episode.title_id), viewer_id)

    return Response({
        "status": "saved",
        "episode_id": str(episode.id),
        "progress_ms": episode_history.progress_ms,
        "is_completed": episode_history.is_completed
    })


@api_view(['GET'])
def continue_watching(request):
    if not request.user.is_authenticated:
        return Response([])
    history = WatchHistory.objects.filter(
        user=request.user,
        is_completed=False
    ).select_related('title', 'episode')[:10]
    serializer = WatchHistorySerializer(history, many=True)
    return Response(serializer.data)
