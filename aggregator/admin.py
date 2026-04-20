from django.contrib import admin
from .models import PluginProvider


@admin.register(PluginProvider)
class PluginProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'endpoint_url', 'timeout')
    list_filter = ('is_active',)
    search_fields = ('name',)
