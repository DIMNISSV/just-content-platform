from django.contrib import admin

from .models import PluginProvider


@admin.register(PluginProvider)
class PluginProviderAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'is_active', 'endpoint_url', 'timeout',
        'allow_title_creation', 'allow_title_update', 'metadata_priority'
    )
    list_filter = ('is_active', 'allow_title_creation', 'allow_title_update')
    search_fields = ('name',)
