from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.views.generic import ListView, DetailView, TemplateView
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response

from media.models import Asset, RawMediaFile, MediaStream, AssetVariant
from .models import Title, Episode, TrackGroupRating, TitleRating, WatchHistory, TrackGroup, AdditionalTrack, Genre
from .serializers import TitleSerializer, TitleDetailSerializer, WatchHistorySerializer, GenreSerializer
from media.tasks import extract_stream_task


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
        qs = super().get_queryset()

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
        # 1. VIDEO QUALITIES
        if tg.video_asset:
            v_variants = tg.video_asset.variants.filter(status='READY').order_by('-preset__width')
            qualities = []
            for v in v_variants:
                qualities.append({
                    "variant_id": str(v.id),
                    "label": v.quality_label or "Original",
                    "storage_path": f"{settings.MEDIA_URL}{v.storage_path}"
                })

            if qualities:
                sources.append({
                    "id": f"video_{tg.id}",
                    "asset_id": str(tg.video_asset.id) if tg.video_asset else None,
                    "type": "VIDEO",
                    "sync_group_id": str(tg.id),
                    "group_title": tg.name,
                    "offset_ms": 0,
                    "qualities": qualities,
                    "active_path": qualities[0]["storage_path"]
                })

        # 2. AUDIO QUALITIES
        for extra in tg.additional_tracks.all():
            if extra.asset:
                a_variants = extra.asset.variants.filter(status='READY')
                qualities = []
                for v in a_variants:
                    qualities.append({
                        "variant_id": str(v.id),
                        "label": v.quality_label or "Original",
                        "storage_path": f"{settings.MEDIA_URL}{v.storage_path}"
                    })

                if qualities:
                    sources.append({
                        "id": f"extra_{extra.id}",
                        "asset_id": str(extra.asset.id) if extra.asset else None,
                        "type": extra.asset.type,
                        "sync_group_id": str(tg.id),
                        "group_title": tg.name,
                        "offset_ms": extra.offset_ms,
                        "meta_info": {"language": extra.language},
                        "qualities": qualities,
                        "active_path": qualities[0]["storage_path"]
                    })

    # Вычисление следующей серии
    next_episode_id = None
    if content_type_str.lower() == 'episode':
        try:
            current_ep = Episode.objects.get(id=object_id)
            # Ищем следующую серию в текущем сезоне
            next_ep = Episode.objects.filter(
                title=current_ep.title,
                season_number=current_ep.season_number,
                episode_number__gt=current_ep.episode_number
            ).order_by('episode_number').first()

            # Если нет в текущем, ищем первую серию следующего сезона
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

        if self.request.user.is_authenticated:
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
    Опрашивает внешние плагины для манифеста.
    """
    from aggregator.services import get_external_sources

    if content_type_str.lower() == 'title':
        model_class = Title
    elif content_type_str.lower() == 'episode':
        model_class = Episode
    else:
        return Response({"error": "invalid type"}, status=400)

    try:
        content_obj = model_class.objects.get(id=object_id)
    except model_class.DoesNotExist:
        return Response({"error": "not found"}, status=404)

    external_ids = {}
    if content_type_str.lower() == 'episode':
        if content_obj.title.imdb_id: external_ids['imdb'] = content_obj.title.imdb_id
        if content_obj.title.tmdb_id: external_ids['tmdb'] = content_obj.title.tmdb_id
        external_ids['season'] = content_obj.season_number
        external_ids['episode'] = content_obj.episode_number
    else:
        if content_obj.imdb_id: external_ids['imdb'] = content_obj.imdb_id
        if content_obj.tmdb_id: external_ids['tmdb'] = content_obj.tmdb_id

    # Этот вызов может длиться несколько секунд
    external_sources = get_external_sources(external_ids)

    return Response({"sources": external_sources})


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
    # target_id может быть либо ID Эпизода/Тайтла (для новой группы), либо ID самой TrackGroup
    target_id = request.data.get('target_id')
    drop_type = request.data.get('drop_type')  # 'new_group' or 'existing_group'
    target_type = request.data.get('target_type')  # 'title' or 'episode' (только для new_group)
    selected_streams = request.data.get('selected_streams', [])  # List of {index, type, language, offset_ms, is_video}

    try:
        raw_file = RawMediaFile.objects.get(id=raw_file_id)
    except RawMediaFile.DoesNotExist:
        return Response({"error": "File not found"}, status=404)

    with transaction.atomic():
        track_group = None
        variant_ids = []

        # 1. Обработка логики Группы (Версии)
        if drop_type == 'new_group':
            # Ищем выбранный видео-стрим
            v_stream_info = next((s for s in selected_streams if s.get('is_video')), None)
            if not v_stream_info:
                return Response({"error": "Video stream is required for new version"}, status=400)

            v_stream = raw_file.streams.get(index=v_stream_info['index'])
            video_asset = Asset.objects.create(source_stream=v_stream, type=Asset.Type.VIDEO)
            v_variant = AssetVariant.objects.create(asset=video_asset, quality_label="Original")
            variant_ids.append(v_variant.id)

            # Создаем саму группу
            ctype = ContentType.objects.get_for_model(Title if target_type == 'title' else Episode)
            track_group = TrackGroup.objects.create(
                name=f"Version {raw_file.original_name[:30]}",
                content_type=ctype,
                object_id=target_id,
                video_asset=video_asset
            )
        else:
            # Добавляем в существующую группу
            track_group = TrackGroup.objects.get(id=target_id)

        # 2. Обработка аудио-дорожек и субтитров
        for s_info in selected_streams:
            if s_info.get('is_video') and drop_type == 'existing_group':
                continue  # Видео в существующей группе менять нельзя через этот API

            if not s_info.get('is_video'):
                stream = raw_file.streams.get(index=s_info['index'])
                asset = Asset.objects.create(source_stream=stream, type=stream.codec_type)
                variant = AssetVariant.objects.create(asset=asset, quality_label="Original")
                variant_ids.append(variant.id)

                AdditionalTrack.objects.create(
                    track_group=track_group,
                    asset=asset,
                    language=s_info.get('language', 'Unknown'),
                    offset_ms=s_info.get('offset_ms', 0)
                )

        # 3. Запуск транскодирования
        transaction.on_commit(lambda: [extract_stream_task.delay(vid) for vid in variant_ids])

    return Response({"status": "success", "track_group_id": track_group.id})
