from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import Title, Episode, TrackGroup, AdditionalTrack
from media.models import Asset, RawMediaFile, AssetVariant, TranscodingPreset
from media.tasks import extract_stream_task


@api_view(['POST'])
@permission_classes([IsAdminUser])
def save_workbench(request, content_type_str, object_id):
    if content_type_str.lower() == 'title':
        ctype = ContentType.objects.get_for_model(Title)
    elif content_type_str.lower() == 'episode':
        ctype = ContentType.objects.get_for_model(Episode)
    else:
        return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)
    data = request.data
    group_name = data.get('name', 'Custom Version')
    video_asset_id = data.get('video_asset_id')
    tracks = data.get('tracks', [])
    try:
        video_asset = Asset.objects.get(id=video_asset_id, type=Asset.Type.VIDEO)
    except Asset.DoesNotExist:
        return Response({"error": "Invalid Video Asset"}, status=status.HTTP_400_BAD_REQUEST)
    author = data.get('author', '')
    track_group = TrackGroup.objects.create(
        name=group_name,
        author=author,
        content_type=ctype,
        object_id=object_id,
        video_asset=video_asset
    )
    for t in tracks:
        try:
            asset = Asset.objects.get(id=t['asset_id'])
            AdditionalTrack.objects.create(
                track_group=track_group,
                asset=asset,
                language=t.get('language', 'Unknown'),
                author=t.get('author', ''),
                offset_ms=t.get('offset_ms', 0)
            )
        except Asset.DoesNotExist:
            continue
    return Response({"status": "success", "track_group_id": track_group.id})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def content_tree_api(request):
    titles = Title.objects.prefetch_related('episodes').all()
    title_ctype = ContentType.objects.get_for_model(Title)
    episode_ctype = ContentType.objects.get_for_model(Episode)
    from django.db.models import Prefetch
    all_track_groups = TrackGroup.objects.prefetch_related(
        Prefetch('additional_tracks', queryset=AdditionalTrack.objects.select_related('asset'))
    ).all()
    groups_by_title = {}
    groups_by_episode = {}
    for g in all_track_groups:
        key = str(g.object_id)
        if g.content_type_id == title_ctype.id:
            groups_by_title.setdefault(key, []).append(g)
        elif g.content_type_id == episode_ctype.id:
            groups_by_episode.setdefault(key, []).append(g)
    tree = []
    for t in titles:
        t_id_str = str(t.id)
        episodes_data = []
        for ep in t.episodes.all():
            ep_id_str = str(ep.id)
            ep_groups = groups_by_episode.get(ep_id_str, [])
            episodes_data.append({
                'id': ep_id_str,
                'name': str(ep),
                'season': ep.season_number,
                'number': ep.episode_number,
                'track_groups': [
                    {
                        'id': str(g.id),
                        'name': g.name,
                        'author': g.author,
                        'assets': [
                                      {
                                          'id': str(track.asset.id),
                                          'type': track.asset.type,
                                          'name': track.author or track.language,
                                          'link_id': str(track.id)
                                      } for track in g.additional_tracks.all()
                                  ] + [{'id': str(g.video_asset_id), 'type': 'VIDEO', 'name': 'Video Source'}]
                    } for g in ep_groups
                ]
            })
        title_groups = groups_by_title.get(t_id_str, [])
        tree.append({
            'id': t_id_str,
            'name': t.name,
            'type': t.type,
            'episodes': episodes_data,
            'track_groups': [
                {
                    'id': str(g.id),
                    'name': g.name,
                    'author': g.author,
                    'assets': [
                                  {
                                      'id': str(track.asset.id),
                                      'type': track.asset.type,
                                      'name': track.author or track.language,
                                      'link_id': str(track.id)
                                  } for track in g.additional_tracks.all()
                              ] + [{'id': str(g.video_asset_id), 'type': 'VIDEO', 'name': 'Video Source'}]
                } for g in title_groups
            ]
        })
    return Response(tree)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def assign_file_api(request):
    raw_file_id = request.data.get('raw_file_id')
    target_id = request.data.get('target_id')
    target_type = request.data.get('target_type')
    drop_type = request.data.get('drop_type')
    selected_streams = request.data.get('selected_streams', [])
    try:
        raw_file = RawMediaFile.objects.get(id=raw_file_id)
    except RawMediaFile.DoesNotExist:
        return Response({"error": "File not found"}, status=404)
    with transaction.atomic():
        new_variants_to_extract = []
        if drop_type == 'new_group':
            v_stream_info = next((s for s in selected_streams if s.get('is_video')), None)
            if not v_stream_info:
                return Response({"error": "Video stream required"}, status=400)
            v_stream = raw_file.streams.get(index=v_stream_info['index'])
            source_width = v_stream.extra_info.get('width', 0)
            video_asset, _ = Asset.objects.get_or_create(source_stream=v_stream, type=Asset.Type.VIDEO)
            orig_var, v_created = AssetVariant.objects.get_or_create(
                asset=video_asset, quality_label="Original",
                defaults={'status': AssetVariant.Status.PROCESSING}
            )
            if v_created: new_variants_to_extract.append(orig_var.id)
            default_presets = TranscodingPreset.objects.filter(type='VIDEO', is_default=True)
            for p in default_presets:
                if p.width and p.width <= source_width:
                    p_var, p_created = AssetVariant.objects.get_or_create(
                        asset=video_asset, preset=p, quality_label=p.name,
                        defaults={'status': AssetVariant.Status.PROCESSING}
                    )
                    if p_created: new_variants_to_extract.append(p_var.id)
            if target_type == 'title':
                content_object = get_object_or_404(Title, pk=target_id)
            else:
                content_object = get_object_or_404(Episode, pk=target_id)
            group_author = request.data.get('group_author', '')
            track_group = TrackGroup.objects.create(
                name=f"Version {(raw_file.original_name or 'New')[:30]}",
                author=group_author,
                content_object=content_object,
                video_asset=video_asset
            )
        else:
            track_group = get_object_or_404(TrackGroup, pk=target_id)
        for s_info in selected_streams:
            if s_info.get('is_video'): continue
            stream = raw_file.streams.get(index=s_info['index'])
            audio_asset, _ = Asset.objects.get_or_create(source_stream=stream, type=stream.codec_type)
            variant, v_created = AssetVariant.objects.get_or_create(
                asset=audio_asset,
                quality_label="Original",
                defaults={'status': AssetVariant.Status.PROCESSING}
            )
            if v_created:
                new_variants_to_extract.append(variant.id)
            if not AdditionalTrack.objects.filter(track_group=track_group, asset=audio_asset).exists():
                AdditionalTrack.objects.create(
                    track_group=track_group, asset=audio_asset,
                    language=s_info.get('language', 'und'),
                    author=s_info.get('author', ''),
                    offset_ms=s_info.get('offset_ms', 0)
                )
        transaction.on_commit(lambda: [extract_stream_task.delay(str(vid)) for vid in new_variants_to_extract])
    return Response({"status": "success", "reused_count": len(selected_streams) - len(new_variants_to_extract)})
