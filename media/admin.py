from django.contrib import admin

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

    @admin.action(description='Extract selected streams to Assets (with Presets)')
    def extract_to_assets(self, request, queryset):
        from django.db import transaction
        from django.shortcuts import render
        from django.http import HttpResponseRedirect
        from .models import TranscodingPreset

        if 'apply' in request.POST:
            preset_ids = request.POST.getlist('presets')
            presets = TranscodingPreset.objects.filter(id__in=preset_ids)

            def start_tasks(asset_ids):
                for aid in asset_ids:
                    extract_stream_task.delay(aid)

            with transaction.atomic():
                asset_ids = []
                for stream in queryset:
                    if not presets:
                        # Fallback: no presets selected
                        asset = Asset.objects.create(
                            source_stream=stream,
                            type=stream.codec_type,
                            status=Asset.Status.PROCESSING
                        )
                        asset_ids.append(asset.id)
                    else:
                        # Filter presets by stream type to avoid processing Audio preset on Video
                        valid_presets = [p for p in presets if p.type == stream.codec_type]
                        if not valid_presets:
                            asset = Asset.objects.create(
                                source_stream=stream,
                                type=stream.codec_type,
                                status=Asset.Status.PROCESSING
                            )
                            asset_ids.append(asset.id)

                        for preset in valid_presets:
                            asset = Asset.objects.create(
                                source_stream=stream,
                                type=stream.codec_type,
                                status=Asset.Status.PROCESSING,
                                preset=preset,
                                quality_label=preset.name
                            )
                            asset_ids.append(asset.id)

                transaction.on_commit(lambda: start_tasks(asset_ids))

            self.message_user(request, f"Extraction tasks started for {len(asset_ids)} assets.")
            return HttpResponseRedirect(request.get_full_path())

        context = {
            'streams': queryset,
            'presets': TranscodingPreset.objects.all(),
            'title': 'Select Extraction Presets'
        }
        return render(request, 'admin/media/select_presets.html', context)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'status', 'display_progress', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('id', 'storage_path')
    readonly_fields = ('storage_path', 'status')

    def display_progress(self, obj):
        if obj.status == 'READY':
            return "100%"
        if obj.status == 'ERROR':
            return "❌"
        return f"{obj.progress}%"

    display_progress.short_description = 'Progress'
