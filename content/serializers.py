from rest_framework import serializers

from .models import Title, Episode, Genre


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name', 'slug']


class EpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Episode
        fields = ['id', 'season_number', 'episode_number', 'name', 'description']


class TitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)

    class Meta:
        model = Title
        fields = [
            'id', 'type', 'name', 'original_name', 'description',
            'release_year', 'genres', 'imdb_id', 'tmdb_id',
            'poster', 'created_at'
        ]


class TitleDetailSerializer(TitleSerializer):
    episodes = EpisodeSerializer(many=True, read_only=True)

    class Meta(TitleSerializer.Meta):
        fields = TitleSerializer.Meta.fields + ['episodes']
