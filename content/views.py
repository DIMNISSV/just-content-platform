import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView, TemplateView
from rest_framework import viewsets, filters, status, mixins
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser, AllowAny
from rest_framework.response import Response

from aggregator.tasks import enqueue_title_refresh
from media.models import Asset, RawMediaFile, AssetVariant, TranscodingPreset
from media.tasks import extract_stream_task
from taxonomy.models import TaxonomyItem
from taxonomy.serializers import TaxonomyItemSerializer
from users.models import UserPreference
from .models import Title, Episode, TrackGroupRating, TitleRating, WatchHistory, TrackGroup, AdditionalTrack, Favorite
from .serializers import TitleSerializer, TitleDetailSerializer, WatchHistorySerializer, EpisodeSerializer
from .services.search_builder import parse_ast_to_q

logger = logging.getLogger(__name__)


class TitleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Title.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'original_name']
    ordering_fields = ['created_at', 'rating_score', 'release_year']
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from django.db.models import Exists, OuterRef
        qs = super().get_queryset().prefetch_related('taxonomy_items')
        user = self.request.user

        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(user=user, title=OuterRef('pk'))
            qs = qs.annotate(is_favorite_annotation=Exists(favorite_subquery))
        else:
            from django.db.models import Value
            qs = qs.annotate(is_favorite_annotation=Value(False))

        c_type = self.request.query_params.get('type')
        genre = self.request.query_params.get('genre')
        tax_items = self.request.query_params.get('taxonomy_items')
        tax_items_any = self.request.query_params.get('taxonomy_items_any')

        if c_type in [Title.Type.MOVIE, Title.Type.SERIES]:
            qs = qs.filter(type=c_type)
        if genre:
            qs = qs.filter(taxonomy_items__slug=genre)

        # Множественная фильтрация (И)
        if tax_items:
            slugs = tax_items.split(',')
            for slug in slugs:
                qs = qs.filter(taxonomy_items__slug=slug.strip())

        # Множественная фильтрация (ИЛИ)
        if tax_items_any:
            slugs = [s.strip() for s in tax_items_any.split(',')]
            qs = qs.filter(taxonomy_items__slug__in=slugs).distinct()

        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def advanced_search(self, request):
        ast = request.data.get('query')
        if not ast:
            return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)

        q_obj = parse_ast_to_q(ast)
        qs = self.get_queryset().filter(q_obj).distinct()

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def similar(self, request, pk=None):
        title = self.get_object()

        vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
        query = SearchQuery(title.name)

        qs = self.get_queryset().annotate(
            rank=SearchRank(vector, query)
        ).exclude(pk=title.pk).filter(rank__gte=0.05).order_by('-rank')[:10]

        if not qs.exists():
            tax_ids = title.taxonomy_items.values_list('id', flat=True)
            qs = self.get_queryset().filter(taxonomy_items__in=tax_ids).exclude(pk=title.pk).distinct().order_by(
                '-rating_score')[:10]

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='toggle-favorite')
    def toggle_favorite(self, request, pk=None):
        title = self.get_object()
        fav, created = Favorite.objects.get_or_create(user=request.user, title=title)
        if not created:
            fav.delete()
            return Response({"status": "removed", "is_favorite": False})
        return Response({"status": "added", "is_favorite": True})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def favorites(self, request):
        from django.db.models import Value, BooleanField
        fav_titles = Title.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
        fav_titles = fav_titles.annotate(is_favorite_annotation=Value(True, output_field=BooleanField()))
        page = self.paginate_queryset(fav_titles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(fav_titles, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TitleDetailSerializer
        return TitleSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rate(self, request, pk=None):
        title = self.get_object()
        score = request.data.get('score')
        if not score or not isinstance(score, int) or not (1 <= score <= 10):
            return Response({"error": "Score must be an integer between 1 and 10"}, status=status.HTTP_400_BAD_REQUEST)
        TitleRating.objects.update_or_create(
            user=request.user,
            title=title,
            defaults={'score': score}
        )
        title.refresh_from_db()
        return Response({"status": "rated", "new_score": title.rating_score, "votes": title.votes_count})


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
    from aggregator.models import ExternalContentRegistry
    from aggregator.services import fetch_registry_manifests
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
    if not request.user.is_authenticated:
        return Response({"error": "Unauthorized"}, status=401)
    data = request.data
    title_id = data.get('title_id')
    if not title_id:
        return Response({"error": "title_id is required"}, status=400)
    try:
        title = Title.objects.get(id=title_id)
    except Title.DoesNotExist:
        return Response({"error": "Title not found"}, status=404)
    episode_id = data.get('episode_id')
    track_group_id = data.get('track_group_id')
    audio_asset_id = data.get('audio_asset_id')
    audio_track_name = data.get('audio_track_name')
    quality_label = data.get('quality_label')
    progress_ms = data.get('progress_ms', 0)
    is_completed = data.get('is_completed', False)
    history, _ = WatchHistory.objects.update_or_create(
        user=request.user,
        title=title,
        defaults={
            'episode_id': episode_id if episode_id else None,
            'track_group_id': track_group_id if track_group_id else None,
            'last_audio_asset_id': audio_asset_id if audio_asset_id else None,
            'last_audio_track_name': audio_track_name if audio_track_name else None,
            'last_quality_label': quality_label,
            'progress_ms': progress_ms,
            'is_completed': is_completed
        }
    )
    return Response({"status": "saved", "progress_ms": history.progress_ms})


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


@api_view(['GET'])
def recommendations(request):
    if not request.user.is_authenticated:
        top_titles = Title.objects.order_by('-rating_score', '-votes_count')[:10]
        return Response(TitleSerializer(top_titles, many=True).data)

    recent_history = WatchHistory.objects.filter(user=request.user).order_by('-updated_at')[:3]
    if not recent_history:
        top_titles = Title.objects.order_by('-rating_score', '-votes_count')[:10]
        return Response(TitleSerializer(top_titles, many=True).data)

    watched_title_ids = WatchHistory.objects.filter(user=request.user).values_list('title_id', flat=True)
    search_texts = [item.title.name for item in recent_history]
    query_str = " | ".join(search_texts)

    query = SearchQuery(query_str, search_type='raw')
    vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')

    recommended = Title.objects.annotate(
        rank=SearchRank(vector, query)
    ).exclude(id__in=watched_title_ids).filter(rank__gte=0.05).order_by('-rank')[:10]

    if len(recommended) < 10:
        preferred_tax_items = set()
        for item in recent_history:
            for t in item.title.taxonomy_items.all():
                preferred_tax_items.add(t.id)

        user_favorites = Favorite.objects.filter(user=request.user).select_related('title').prefetch_related(
            'title__taxonomy_items')
        for fav in user_favorites:
            for t in fav.title.taxonomy_items.all():
                preferred_tax_items.add(t.id)

        pad_amount = 10 - len(recommended)
        extra_titles = Title.objects.filter(
            taxonomy_items__in=preferred_tax_items
        ).exclude(
            id__in=watched_title_ids
        ).exclude(
            id__in=[t.id for t in recommended]
        ).distinct().order_by('-rating_score')[:pad_amount]
        recommended = list(recommended) + list(extra_titles)

    if len(recommended) < 10:
        pad_amount = 10 - len(recommended)
        extra_titles = Title.objects.exclude(
            id__in=watched_title_ids
        ).exclude(
            id__in=[t.id for t in recommended]
        ).order_by('-rating_score')[:pad_amount]
        recommended = list(recommended) + list(extra_titles)

    return Response(TitleSerializer(recommended, many=True).data)


class HomeView(TemplateView):
    template_name = 'content/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trending'] = Title.objects.all().order_by('-rating_score', '-created_at')[:12]
        context['new_movies'] = Title.objects.filter(type=Title.Type.MOVIE).order_by('-created_at')[:6]
        context['new_series'] = Title.objects.filter(type=Title.Type.SERIES).order_by('-created_at')[:6]
        return context


class WatchView(DetailView):
    model = Title
    template_name = 'content/watch.html'
    context_object_name = 'title'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('taxonomy_items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        enqueue_title_refresh(self.object)

        context['content_type'] = 'title'
        context['player_id'] = self.object.id
        context['title_id'] = self.object.id
        context['episode_id'] = ''
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_audio_track_name'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0
        context['is_favorite'] = 'false'
        context['language_code'] = 'rus'
        context['preferred_voiceovers'] = '[]'
        context['auto_skip'] = 'false'
        title_obj = self.object
        if self.request.user.is_authenticated:
            pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
            context['language_code'] = pref.language_code
            context['preferred_voiceovers'] = json.dumps(pref.preferred_voiceovers)
            context['auto_skip'] = 'true' if pref.auto_skip_intro else 'false'
            if Favorite.objects.filter(user=self.request.user, title=title_obj).exists():
                context['is_favorite'] = 'true'
            history = WatchHistory.objects.filter(user=self.request.user, title=title_obj).first()
            if history:
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_audio_track_name'] = history.last_audio_track_name or ''
                context['last_quality'] = history.last_quality_label or ''
                context['start_progress'] = history.progress_ms
            rating = TitleRating.objects.filter(user=self.request.user, title=self.object).first()
            if rating:
                context['user_title_rating'] = rating.score
        return context


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


class EpisodeWatchView(DetailView):
    model = Episode
    template_name = 'content/watch.html'
    context_object_name = 'episode'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        title = self.object.title

        enqueue_title_refresh(title)

        context['title'] = title
        context['content_type'] = 'episode'
        context['player_id'] = self.object.id
        context['title_id'] = title.id
        context['episode_id'] = self.object.id
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_audio_track_name'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0
        context['is_favorite'] = 'false'
        context['language_code'] = 'rus'
        context['preferred_voiceovers'] = '[]'
        context['auto_skip'] = 'false'
        if self.request.user.is_authenticated:
            pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
            context['language_code'] = pref.language_code
            context['preferred_voiceovers'] = json.dumps(pref.preferred_voiceovers)
            context['auto_skip'] = 'true' if pref.auto_skip_intro else 'false'
            if Favorite.objects.filter(user=self.request.user, title=title).exists():
                context['is_favorite'] = 'true'
            history = WatchHistory.objects.filter(user=self.request.user, title=title).first()
            if history:
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_audio_track_name'] = history.last_audio_track_name or ''
                context['last_quality'] = history.last_quality_label or ''
                if history.episode_id == self.object.id:
                    context['start_progress'] = history.progress_ms
            rating = TitleRating.objects.filter(user=self.request.user, title=title).first()
            if rating:
                context['user_title_rating'] = rating.score
        return context


class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Эндпоинт, который отдает TaxonomyItem с типом GENRE,
    тем самым сохраняя обратную совместимость с фронтендом, запрашивающим /genres/.
    """
    queryset = TaxonomyItem.objects.filter(type=TaxonomyItem.TypeChoices.GENRE).order_by('name')
    serializer_class = TaxonomyItemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None


class CatalogView(TemplateView):
    template_name = 'content/catalog.html'


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


@staff_member_required
def upload_wizard_view(request):
    context = {
        'site_header': 'Just Content Admin',
        'has_permission': True,
        'is_popup': False,
    }
    return render(request, 'admin/upload_wizard.html', context)


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.all()
    serializer_class = EpisodeSerializer
    permission_classes = [IsAdminUser]


class TrackGroupViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = TrackGroup.objects.all()
    permission_classes = [IsAdminUser]


class AdditionalTrackViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = AdditionalTrack.objects.all()
    permission_classes = [IsAdminUser]
