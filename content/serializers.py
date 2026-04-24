from rest_framework import serializers

from .models import Title, Episode, Genre, WatchHistory


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name', 'slug']


class EpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Episode
        fields = ['id', 'title', 'season_number', 'episode_number', 'name', 'description']


class TitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Title
        fields = [
            'id', 'type', 'name', 'original_name', 'description',
            'release_year', 'genres', 'imdb_id', 'tmdb_id',
            'poster', 'created_at', 'rating_score', 'is_favorite'
        ]

    def get_is_favorite(self, obj):
        # Используем аннотацию из QuerySet (чтобы избежать N+1 проблемы)
        # Если аннотации нет (например при единичном запросе без нее), падаем на обычный фильтр
        if hasattr(obj, 'is_favorite_annotation'):
            return obj.is_favorite_annotation

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorited_by.filter(user=request.user).exists()
        return False


class TitleDetailSerializer(TitleSerializer):
    episodes = EpisodeSerializer(many=True, read_only=True)

    class Meta(TitleSerializer.Meta):
        fields = TitleSerializer.Meta.fields + ['episodes']


class WatchHistorySerializer(serializers.ModelSerializer):
    # Nested serializer to quickly display title info in the UI (poster, name)
    title = TitleSerializer(read_only=True)
    episode = EpisodeSerializer(read_only=True)

    class Meta:
        model = WatchHistory
        fields = [
            'id', 'title', 'episode', 'track_group',
            'progress_ms', 'is_completed', 'updated_at'
        ]
