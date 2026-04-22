from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.views.generic import ListView, DetailView
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response

from media.models import Asset
from .models import Title, Episode, TrackGroupRating, TitleRating, WatchHistory, TrackGroup, AdditionalTrack
from .serializers import TitleSerializer, TitleDetailSerializer, WatchHistorySerializer


class TitleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для каталога (Grid) и деталей (Watch).
    ReadOnly, так как созданием мы пока управляем через Django Admin.
    """
    queryset = Title.objects.prefetch_related('genres').all().order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'original_name']
    # Разрешаем сортировку по рейтингу (для виджетов на Главной)
    ordering_fields = ['created_at', 'rating_score', 'release_year']
    permission_classes = [IsAuthenticatedOrReadOnly]

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

    # Подтягиваем логические ассеты и их варианты
    track_groups = TrackGroup.objects.filter(
        content_type=ctype,
        object_id=object_id
    ).prefetch_related(
        'video_asset__variants__preset',
        'additional_tracks__asset__variants'
    )

    sources = []
    for tg in track_groups:
        # 1. VIDEO QUALITIES
        if tg.video_asset:
            # Сортируем по ширине пресета (от высокого качества к низкому)
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
                    "type": "VIDEO",
                    "sync_group_id": str(tg.id),
                    "group_title": tg.name,
                    "offset_ms": 0,
                    "qualities": qualities,
                    "active_path": qualities[0]["storage_path"]  # Самое высокое качество по умолчанию
                })

        # 2. AUDIO & SUBTITLE QUALITIES
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
                        "type": extra.asset.type,
                        "sync_group_id": str(tg.id),
                        "group_title": tg.name,
                        "offset_ms": extra.offset_ms,
                        "meta_info": {"language": extra.language},
                        "qualities": qualities,
                        "active_path": qualities[0]["storage_path"]
                    })

    return Response({
        "content_id": str(object_id),
        "sources": sources
    })


@api_view(['POST'])
def player_telemetry(request):
    """
    Called by the video player every X seconds to save progress.
    Expected JSON: {"title_id": 1, "episode_id": null, "track_group_id": 2, "progress_ms": 15000, "is_completed": false}
    """
    if not request.user.is_authenticated:
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    title_id = request.data.get('title_id')
    progress_ms = request.data.get('progress_ms', 0)
    is_completed = request.data.get('is_completed', False)

    if not title_id:
        return Response({"error": "title_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        title = Title.objects.get(id=title_id)
    except Title.DoesNotExist:
        return Response({"error": "Title not found"}, status=status.HTTP_404_NOT_FOUND)

    episode_id = request.data.get('episode_id')
    track_group_id = request.data.get('track_group_id')

    episode = Episode.objects.filter(id=episode_id).first() if episode_id else None
    track_group = TrackGroup.objects.filter(id=track_group_id).first() if track_group_id else None

    # Update or create the history record for this title
    history, created = WatchHistory.objects.update_or_create(
        user=request.user,
        title=title,
        defaults={
            'episode': episode,
            'track_group': track_group,
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
        context['title'] = self.object.title
        context['content_type'] = 'episode'
        context['player_id'] = self.object.id  # ID Эпизода
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
