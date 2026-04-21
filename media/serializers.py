from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    original_name = serializers.CharField(source='source_stream.raw_file.original_name', read_only=True,
                                          default='Unknown File')

    class Meta:
        model = Asset
        fields = ['id', 'type', 'status', 'storage_path', 'created_at', 'quality_label', 'original_name']
