from rest_framework import viewsets, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from .models import Title, Episode, TrackGroup
from .serializers import TitleSerializer, TitleDetailSerializer


class TitleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API для каталога (Grid) и деталей (Watch).
    ReadOnly, так как созданием мы пока управляем через Django Admin.
    """
    queryset = Title.objects.prefetch_related('genres').all().order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'original_name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TitleDetailSerializer
        return TitleSerializer


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

    return Response({
        "content_id": str(object_id),
        "sources": sources
    })
