from django.contrib import admin

from .models import KodikSyncState


@admin.register(KodikSyncState)
class KodikSyncStateAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)
    readonly_fields = ('updated_at',)
