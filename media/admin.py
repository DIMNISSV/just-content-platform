from django.contrib import admin
from .models import RawMediaFile, MediaStream, Asset

class MediaStreamInline(admin.TabularInline):
    model = MediaStream
    extra = 0
    readonly_fields = ('index', 'codec_type', 'codec_name', 'language')
    can_delete = False

@admin.register(RawMediaFile)
class RawMediaFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('original_name',)
    inlines =[MediaStreamInline]

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'status', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('id', 'storage_path')