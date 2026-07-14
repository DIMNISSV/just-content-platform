from rest_framework import serializers

from .models import TaxonomyItem, RawTerm, RawTermMapping


class TaxonomyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxonomyItem
        fields = ['id', 'name', 'slug', 'type', 'parent', 'description']


class RawTermSerializer(serializers.ModelSerializer):
    is_mapped = serializers.SerializerMethodField()

    class Meta:
        model = RawTerm
        fields = ['id', 'name', 'source_field', 'created_at', 'is_mapped']

    def get_is_mapped(self, obj):
        return obj.mappings.exists()


class RawTermMappingSerializer(serializers.ModelSerializer):
    raw_term_name = serializers.CharField(source='raw_term.name', read_only=True)
    taxonomy_item_name = serializers.CharField(source='taxonomy_item.name', read_only=True)

    class Meta:
        model = RawTermMapping
        fields = ['id', 'raw_term', 'raw_term_name', 'taxonomy_item', 'taxonomy_item_name', 'created_at']
