from rest_framework import serializers

from .models import Asset, AssetVariant, RawMediaFile


class AssetVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetVariant
        fields = ['id', 'quality_label', 'status', 'storage_path', 'progress']


class AssetSerializer(serializers.ModelSerializer):
    # Достаем оригинальное имя файла через цепочку связей
    original_name = serializers.CharField(source='source_stream.raw_file.original_name', read_only=True,
                                          default='Unknown Source')
    # Вкладываем варианты
    variants = AssetVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = ['id', 'type', 'created_at', 'original_name', 'variants']


class RawFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawMediaFile
        fields = ['id', 'original_name', 'status', 'metadata', 'created_at']
