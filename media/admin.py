from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .models import RawMediaFile, MediaStream, Asset, TranscodingPreset, AssetVariant
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


class AssetVariantInline(admin.TabularInline):
    model = AssetVariant
    extra = 0
    readonly_fields = ('status', 'progress', 'storage_path')


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'created_at')
    list_filter = ('type',)
    search_fields = ('id',)
    inlines = [AssetVariantInline]


@admin.register(AssetVariant)
class AssetVariantAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset', 'quality_label', 'status', 'display_progress', 'created_at')
    list_filter = ('status', 'asset__type')
    search_fields = ('id', 'storage_path')
    readonly_fields = ('storage_path', 'status', 'progress')

    def display_progress(self, obj):
        if obj.status == 'READY': return "100%"
        if obj.status == 'ERROR': return "❌"
        return f"{obj.progress}%"

    display_progress.short_description = 'Progress'


@admin.register(MediaStream)
class MediaStreamAdmin(admin.ModelAdmin):
    list_display = ('id', 'raw_file', 'index', 'codec_type', 'codec_name', 'language')
    list_filter = ('codec_type', 'raw_file')
    actions = ['extract_to_assets']

    @admin.action(description='Extract selected streams to Assets (with Presets)')
    def extract_to_assets(self, request, queryset):
        if 'apply' in request.POST:
            preset_ids = request.POST.getlist('presets')
            presets = TranscodingPreset.objects.filter(id__in=preset_ids)

            def start_tasks(variant_ids):
                for vid in variant_ids:
                    extract_stream_task.delay(vid)

            with transaction.atomic():
                variant_ids = []
                for stream in queryset:
                    # 1. Создаем ЛОГИЧЕСКИЙ контейнер
                    asset = Asset.objects.create(
                        source_stream=stream,
                        type=stream.codec_type
                    )

                    valid_presets = [p for p in presets if p.type == stream.codec_type]

                    # 2. Создаем ФИЗИЧЕСКИЕ варианты
                    if not valid_presets:
                        # Если пресеты не выбраны, создаем вариант "Original"
                        variant = AssetVariant.objects.create(
                            asset=asset,
                            quality_label="Original",
                            status=AssetVariant.Status.PROCESSING  # Исправлено здесь
                        )
                        variant_ids.append(variant.id)
                    else:
                        for preset in valid_presets:
                            variant = AssetVariant.objects.create(
                                asset=asset,
                                preset=preset,
                                quality_label=preset.name,
                                status=AssetVariant.Status.PROCESSING
                            )
                            variant_ids.append(variant.id)

                transaction.on_commit(lambda: start_tasks(variant_ids))

            self.message_user(request, f"Extraction tasks started for {len(variant_ids)} variants.", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())

        context = {
            'streams': queryset,
            'presets': TranscodingPreset.objects.all(),
            'title': 'Select Extraction Presets'
        }
        return render(request, 'admin/media/select_presets.html', context)
