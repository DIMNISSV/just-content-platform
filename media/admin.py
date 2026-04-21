from django.contrib import admin
from django.contrib import messages
from .models import RawMediaFile, MediaStream, Asset
from .tasks import extract_stream_task


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
    inlines = [MediaStreamInline]


@admin.register(MediaStream)
class MediaStreamAdmin(admin.ModelAdmin):
    list_display = ('id', 'raw_file', 'index', 'codec_type', 'codec_name', 'language')
    list_filter = ('codec_type', 'raw_file')
    actions = ['extract_to_assets']

    @admin.action(description='Extract selected streams to Assets')
    def extract_to_assets(self, request, queryset):
        from django.db import transaction

        def start_tasks(asset_ids):
            for aid in asset_ids:
                extract_stream_task.delay(aid)

        with transaction.atomic():
            asset_ids = []
            for stream in queryset:
                asset = Asset.objects.create(
                    source_stream=stream,
                    type=stream.codec_type,
                    status=Asset.Status.PROCESSING
                )
                asset_ids.append(asset.id)

            # Отправляем в Celery только после того, как commit завершится
            transaction.on_commit(lambda: start_tasks(asset_ids))

        self.message_user(
            request,
            f"Started extraction for {len(asset_ids)} streams.",
            messages.SUCCESS
        )

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'status', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('id', 'storage_path')
    readonly_fields = ('storage_path', 'status')