from django.contrib import admin
from .models import TaxonomyItem, RawTerm, RawTermMapping


@admin.register(TaxonomyItem)
class TaxonomyItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'slug', 'parent')
    list_filter = ('type',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(RawTerm)
class RawTermAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_field', 'created_at')
    list_filter = ('source_field',)
    search_fields = ('name',)


@admin.register(RawTermMapping)
class RawTermMappingAdmin(admin.ModelAdmin):
    list_display = ('raw_term', 'taxonomy_item', 'created_at')
    search_fields = ('raw_term__name', 'taxonomy_item__name')
