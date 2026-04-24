from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import render
from django.views.generic import ListView, DetailView, TemplateView
from rest_framework import viewsets, filters, status, mixins
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response

from media.models import Asset, RawMediaFile, AssetVariant, TranscodingPreset
from media.tasks import extract_stream_task
from .models import Title, Episode, TrackGroupRating, TitleRating, WatchHistory, TrackGroup, AdditionalTrack, Genre, \
    Favorite
from .serializers import TitleSerializer, TitleDetailSerializer, WatchHistorySerializer, GenreSerializer, \
    EpisodeSerializer


class TitleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для каталога (Grid) и деталей (Watch).
    ReadOnly, так как созданием мы пока управляем через Django Admin.
    """
    queryset = Title.objects.prefetch_related('genres').all().order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'original_name']
    ordering_fields = ['created_at', 'rating_score', 'release_year']
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from django.db.models import Exists, OuterRef
        from .models import Favorite

        qs = super().get_queryset()

        user = self.request.user
        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(user=user, title=OuterRef('pk'))
            qs = qs.annotate(is_favorite_annotation=Exists(favorite_subquery))
        else:
            from django.db.models import Value
            qs = qs.annotate(is_favorite_annotation=Value(False))

        # Ручная фильтрация
        c_type = self.request.query_params.get('type')
        genre = self.request.query_params.get('genre')

        if c_type in [Title.Type.MOVIE, Title.Type.SERIES]:
            qs = qs.filter(type=c_type)
        if genre:
            qs = qs.filter(genres__slug=genre)

        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TitleDetailSerializer
        return TitleSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rate(self, request, pk=None):
        """Оценка фильма пользователем. POST: {"score": 8}"""
        title = self.get_object()
        score = request.data.get('score')

        if not score or not isinstance(score, int) or not (1 <= score <= 10):
            return Response({"error": "Score must be an integer between 1 and 10"}, status=status.HTTP_400_BAD_REQUEST)

        # update_or_create автоматически обновит оценку, если она уже была
        TitleRating.objects.update_or_create(
            user=request.user,
            title=title,
            defaults={'score': score}
        )
        # Сигнал сам пересчитает rating_score и votes_count у Title
        title.refresh_from_db()
        return Response({"status": "rated", "new_score": title.rating_score, "votes": title.votes_count})


@api_view(['POST'])
def rate_track_group(request, group_id):
    """Оценка конкретной озвучки/дорожки."""
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

    # --- 1. LOCAL SOURCES ---
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
            qualities = [{"variant_id": str(v.id), "label": v.quality_label or "Original",
                          "storage_path": f"{settings.MEDIA_URL}{v.storage_path}"} for v in v_variants]
            if qualities:
                sources.append({
                    "id": f"video_{tg.id}",
                    "asset_id": str(tg.video_asset.id),
                    "type": "VIDEO",
                    "sync_group_id": str(tg.id),
                    "group_title": tg.name,
                    "offset_ms": 0,
                    "qualities": qualities,
                    "active_path": qualities[0]["storage_path"]
                })

        for extra in tg.additional_tracks.all():
            if extra.asset:
                a_variants = extra.asset.variants.filter(status='READY')
                qualities = [{"variant_id": str(v.id), "label": v.quality_label or "Original",
                              "storage_path": f"{settings.MEDIA_URL}{v.storage_path}"} for v in a_variants]
                if qualities:
                    sources.append({
                        "id": f"extra_{extra.id}",
                        "asset_id": str(extra.asset.id),
                        "type": extra.asset.type,
                        "sync_group_id": str(tg.id),
                        "group_title": tg.name,
                        "offset_ms": extra.offset_ms,
                        "meta_info": {"language": extra.language},
                        "qualities": qualities,
                        "active_path": qualities[0]["storage_path"]
                    })

    # --- 2. EXTERNAL SOURCES (PLUGINS) & DOMAIN GATING ---
    domain = getattr(request, 'tenant_domain', None)

    registry_qs = ExternalContentRegistry.objects.select_related('plugin').filter(plugin__is_active=True)
    if content_type_str.lower() == 'title':
        registry_qs = registry_qs.filter(title_id=object_id, episode__isnull=True)
    else:
        registry_qs = registry_qs.filter(episode_id=object_id)

    valid_entries = []
    for entry in registry_qs:
        allowed = entry.plugin.allowed_domains
        # Если список разрешенных доменов пуст, либо содержит '*', либо текущий домен в списке
        if not allowed or '*' in allowed or domain in allowed:
            valid_entries.append(entry)

    manifest_entries = []
    for entry in valid_entries:
        # Интеграция внешних iframe-плееров
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

    # Параллельный опрос манифестов (Deep Integration)
    ext_manifest_sources = fetch_registry_manifests(manifest_entries)
    sources.extend(ext_manifest_sources)

    # --- 3. NEXT EPISODE LOGIC ---
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
    """
    Called by the video player every X seconds to save progress.
    Expected JSON: {"title_id": 1, "episode_id": null, "track_group_id": 2, "progress_ms": 15000, "is_completed": false}
    """
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

    # Собираем данные
    episode_id = data.get('episode_id')
    track_group_id = data.get('track_group_id')
    audio_asset_id = data.get('audio_asset_id')
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
            'last_quality_label': quality_label,
            'progress_ms': progress_ms,
            'is_completed': is_completed
        }
    )

    return Response({"status": "saved", "progress_ms": history.progress_ms})


@api_view(['GET'])
def continue_watching(request):
    """
    Returns the user's unfinished watch history.
    """
    if not request.user.is_authenticated:
        return Response([])

    # Get recent history where content is not finished
    history = WatchHistory.objects.filter(
        user=request.user,
        is_completed=False
    ).select_related('title', 'episode')[:10]

    serializer = WatchHistorySerializer(history, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def recommendations(request):
    """
    Simple Content-Based Filtering algorithm v1.0.
    Finds highly-rated titles with genres matching the user's recently watched titles.
    """
    # 1. Fallback for anonymous users: Top Rated
    if not request.user.is_authenticated:
        top_titles = Title.objects.order_by('-rating_score', '-votes_count')[:10]
        return Response(TitleSerializer(top_titles, many=True).data)

    # 2. Get user's last 3 watched titles
    recent_history = WatchHistory.objects.filter(user=request.user).order_by('-updated_at')[:3]

    if not recent_history:
        # User has no history yet, return Top Rated
        top_titles = Title.objects.order_by('-rating_score', '-votes_count')[:10]
        return Response(TitleSerializer(top_titles, many=True).data)

    # 3. Extract preferred genres
    preferred_genres = set()
    for item in recent_history:
        for genre in item.title.genres.all():
            preferred_genres.add(genre.id)

    # 4. Find titles matching these genres, exclude already watched
    watched_title_ids = WatchHistory.objects.filter(user=request.user).values_list('title_id', flat=True)

    recommended = Title.objects.filter(
        genres__in=preferred_genres
    ).exclude(
        id__in=watched_title_ids
    ).distinct().order_by('-rating_score')[:10]

    # 5. If recommendations are fewer than 10 (e.g. niche genres), pad with overall top titles
    if len(recommended) < 10:
        pad_amount = 10 - len(recommended)
        extra_titles = Title.objects.exclude(
            id__in=watched_title_ids
        ).exclude(
            id__in=[t.id for t in recommended]
        ).order_by('-rating_score')[:pad_amount]
        recommended = list(recommended) + list(extra_titles)

    return Response(TitleSerializer(recommended, many=True).data)


class HomeView(ListView):
    model = Title
    template_name = 'content/home.html'
    context_object_name = 'titles'

    def get_queryset(self):
        # Получаем последние добавленные фильмы с сортировкой по рейтингу
        return Title.objects.all().order_by('-rating_score', '-created_at')[:24]


class WatchView(DetailView):
    model = Title
    template_name = 'content/watch.html'
    context_object_name = 'title'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['content_type'] = 'title'
        context['player_id'] = self.object.id
        context['title_id'] = self.object.id
        context['episode_id'] = ''

        # Fetch telemetry data
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0

        context['is_favorite'] = 'false'

        if self.request.user.is_authenticated:
            if Favorite.objects.filter(user=self.request.user, title=self.object).exists():
                context['is_favorite'] = 'true'

            history = WatchHistory.objects.filter(user=self.request.user, title=self.object).first()
            if history:
                context['start_progress'] = history.progress_ms
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_quality'] = history.last_quality_label or ''

            rating = TitleRating.objects.filter(user=self.request.user, title=self.object).first()
            if rating:
                context['user_title_rating'] = rating.score

        return context


@api_view(['POST'])
@permission_classes([IsAdminUser])
def save_workbench(request, content_type_str, object_id):
    """
    Сохраняет собранную в Vue Воркбенче группу дорожек.
    """
    if content_type_str.lower() == 'title':
        ctype = ContentType.objects.get_for_model(Title)
    elif content_type_str.lower() == 'episode':
        ctype = ContentType.objects.get_for_model(Episode)
    else:
        return Response({"error": "Invalid content type"}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data
    group_name = data.get('name', 'Custom Version')
    video_asset_id = data.get('video_asset_id')
    tracks = data.get('tracks', [])  # [{asset_id, language, offset_ms}]

    try:
        video_asset = Asset.objects.get(id=video_asset_id, type=Asset.Type.VIDEO)
    except Asset.DoesNotExist:
        return Response({"error": "Invalid Video Asset"}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Создаем или обновляем базовую группу (TrackGroup)
    track_group = TrackGroup.objects.create(
        name=group_name,
        content_type=ctype,
        object_id=object_id,
        video_asset=video_asset
    )

    # 2. Добавляем аудиодорожки и субтитры
    for t in tracks:
        try:
            asset = Asset.objects.get(id=t['asset_id'])
            AdditionalTrack.objects.create(
                track_group=track_group,
                asset=asset,
                language=t.get('language', 'Unknown'),
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
        # title нужен шаблону для отображения общей информации о сериале
        title = self.object.title
        context['title'] = title
        context['content_type'] = 'episode'
        context['player_id'] = self.object.id  # ID Эпизода
        context['title_id'] = title.id
        context['episode_id'] = self.object.id

        # Fetch telemetry data
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0

        if self.request.user.is_authenticated:
            history = WatchHistory.objects.filter(user=self.request.user, title=title).first()
            if history:
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_quality'] = history.last_quality_label or ''
                if history.episode_id == self.object.id:
                    context['start_progress'] = history.progress_ms

            rating = TitleRating.objects.filter(user=self.request.user, title=title).first()
            if rating:
                context['user_title_rating'] = rating.score

        return context


@api_view(['GET'])
def player_external_sources(request, content_type_str, object_id):
    """
    Deprecated. Данные теперь интегрируются непосредственно в player_manifest.
    Оставлено для совместимости с текущим фронтендом до его обновления.
    """
    return Response({"sources": []})


class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Отдает список всех жанров для фильтров на фронтенде.
    """
    queryset = Genre.objects.all().order_by('name')
    serializer_class = GenreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None  # Отключаем пагинацию, чтобы вернуть плоский массив


class CatalogView(TemplateView):
    template_name = 'content/catalog.html'


@api_view(['GET'])
@permission_classes([IsAdminUser])
def content_tree_api(request):
    """Возвращает глубокую иерархию: Title -> Episode -> TrackGroups -> Assets"""
    titles = Title.objects.prefetch_related(
        'episodes',
        'track_groups__additional_tracks__asset',
        'episodes__track_groups__additional_tracks__asset'
    ).all()

    tree = []
    for t in titles:
        # Для краткости примера логика для Title и Episode идентична
        def serialize_groups(obj):
            groups = []
            for tg in obj.track_groups.all():
                assets = [{
                    'id': tg.video_asset.id,
                    'type': 'VIDEO',
                    'name': 'Base Video'
                }]
                for track in tg.additional_tracks.all():
                    assets.append({
                        'id': track.asset.id,
                        'link_id': track.id,
                        'type': 'AUDIO',
                        'name': track.language
                    })
                groups.append({
                    'id': tg.id,
                    'name': tg.name,
                    'assets': assets
                })
            return groups

        episodes = []
        for ep in t.episodes.all():
            episodes.append({
                'id': ep.id,
                'name': str(ep),
                'track_groups': serialize_groups(ep)
            })

        tree.append({
            'id': t.id,
            'name': t.name,
            'type': t.type,
            'track_groups': serialize_groups(t),
            'episodes': episodes
        })
    return Response(tree)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def assign_file_api(request):
    raw_file_id = request.data.get('raw_file_id')
    target_id = request.data.get('target_id')
    drop_type = request.data.get('drop_type')
    target_type = request.data.get('target_type')
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

            ctype = ContentType.objects.get_for_model(Title if target_type == 'title' else Episode)
            track_group = TrackGroup.objects.create(
                name=f"Version {(raw_file.original_name or 'New')[:30]}",
                content_type=ctype,
                object_id=target_id,
                video_asset=video_asset
            )
        else:
            track_group = TrackGroup.objects.get(id=target_id)

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
                    language=s_info.get('language', 'Unknown'),
                    offset_ms=s_info.get('offset_ms', 0)
                )

        transaction.on_commit(lambda: [extract_stream_task.delay(vid) for vid in new_variants_to_extract])

    return Response({"status": "success", "reused_count": len(selected_streams) - len(new_variants_to_extract)})


@staff_member_required
def upload_wizard_view(request):
    """
    Рендерит страницу Upload Wizard в рамках интерфейса Django Admin.
    """
    # Добавляем базовый контекст админки, чтобы работали стили шапки
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


@action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='toggle-favorite')
def toggle_favorite(self, request, pk=None):
    from .models import Favorite
    title = self.get_object()

    fav, created = Favorite.objects.get_or_create(user=request.user, title=title)
    if not created:
        fav.delete()
        return Response({"status": "removed", "is_favorite": False})

    return Response({"status": "added", "is_favorite": True})
