from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Title, Episode, TrackGroup, TrackGroupRating, TitleRating, WatchHistory
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
    """
    Эндпоинт генерации манифеста для VideoPlayer.vue.
    content_type_str может быть 'title' (для фильмов) или 'episode' (для сериалов).
    Возвращает плоский массив `sources` с видео и привязанными дорожками.
    """
    if content_type_str.lower() == 'title':
        ctype = ContentType.objects.get_for_model(Title)
    elif content_type_str.lower() == 'episode':
        ctype = ContentType.objects.get_for_model(Episode)
    else:
        return Response({"error": "invalid content type"}, status=400)

    # Загружаем все сборки дорожек для данного объекта с оптимизацией запросов
    track_groups = TrackGroup.objects.filter(
        content_type=ctype,
        object_id=object_id
    ).prefetch_related('video_asset', 'additional_tracks__asset')

    sources = []

    for tg in track_groups:
        if tg.video_asset and tg.video_asset.status == 'READY':
            # Добавляем базовое ВИДЕО
            sources.append({
                "asset_id": str(tg.video_asset.id),
                "type": tg.video_asset.type,
                "storage_path": f"{settings.MEDIA_URL}{tg.video_asset.storage_path}",
                "sync_group_id": str(tg.id),
                "group_title": tg.name,
                "offset_ms": 0,
            })

        # Добавляем связанные АУДИО и СУБТИТРЫ из этой же сборки
        for extra in tg.additional_tracks.all():
            if extra.asset and extra.asset.status == 'READY':
                sources.append({
                    "asset_id": str(extra.asset.id),
                    "type": extra.asset.type,
                    "storage_path": f"{settings.MEDIA_URL}{extra.asset.storage_path}",
                    "sync_group_id": str(tg.id),
                    "group_title": tg.name,
                    "offset_ms": extra.offset_ms,
                    "meta_info": {"language": extra.language}
                })

        # На этом этапе можно также дернуть внешний Агрегатор плагинов и добавить external_sources
        # (Сделаем это в Итерации 6)
        from aggregator.services import get_external_sources

        external_ids = {}
        content_obj = ctype.get_object_for_this_type(id=object_id)

        # Если это эпизод, берем ID от родительского тайтла (зачастую плагинам нужен TMDB сериала + season/episode)
        # Для простоты MVP пока передаем просто ID тайтла.
        if content_type_str.lower() == 'episode':
            if content_obj.title.imdb_id:
                external_ids['imdb'] = content_obj.title.imdb_id
            if content_obj.title.tmdb_id:
                external_ids['tmdb'] = content_obj.title.tmdb_id
            external_ids['season'] = content_obj.season_number
            external_ids['episode'] = content_obj.episode_number
        else:
            if content_obj.imdb_id:
                external_ids['imdb'] = content_obj.imdb_id
            if content_obj.tmdb_id:
                external_ids['tmdb'] = content_obj.tmdb_id

        external_sources = get_external_sources(external_ids)

        # Добавляем внешние источники к локальным
        sources.extend(external_sources)

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
