from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'type', 'status', 'storage_path', 'created_at']
