from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from .models import Genre, Title, Episode, TrackGroup, AdditionalTrack

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

class AdditionalTrackInline(admin.TabularInline):
    model = AdditionalTrack
    extra = 0
    # raw_id_fields удобен, когда ассетов станут тысячи, чтобы не грузить огромный селект
    raw_id_fields = ('asset',)

@admin.register(TrackGroup)
class TrackGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'content_object', 'video_asset')
    search_fields = ('name',)
    raw_id_fields = ('video_asset',)
    inlines = [AdditionalTrackInline]

class TrackGroupGenericInline(GenericTabularInline):
    model = TrackGroup
    extra = 0
    raw_id_fields = ('video_asset',)
    show_change_link = True # Позволяет кликнуть на группу и перейти к добавлению аудио-дорожек

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0

@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'release_year', 'workbench_link') # Добавили ссылку
    list_filter = ('type', 'genres')
    search_fields = ('name', 'original_name')
    filter_horizontal = ('genres',)
    inlines = [TrackGroupGenericInline, EpisodeInline]

    # Создаем кнопку-ссылку в списке фильмов
    def workbench_link(self, obj):
        return format_html('<a class="button" href="{}workbench/">Open Workbench</a>', obj.pk)
    workbench_link.short_description = 'Workbench'
    workbench_link.allow_tags = True

    # Регистрируем кастомный URL внутри админки Title
    def get_urls(self):
        urls = super().get_urls()
        custom_urls =[
            path('<int:object_id>/workbench/', self.admin_site.admin_view(self.workbench_view), name='content_title_workbench'),
        ]
        return custom_urls + urls

    # Кастомная View, которая отрендерит Vue Воркбенч
    def workbench_view(self, request, object_id):
        title = self.get_object(request, object_id)
        context = dict(
            self.admin_site.each_context(request),
            title=title,
            object_id=object_id,
            content_type='title'
        )
        return TemplateResponse(request, "admin/workbench.html", context)

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'title', 'season_number', 'episode_number')
    list_filter = ('title',)
    # Для эпизодов показываем сборки дорожек (Воркбенч)
    inlines = [TrackGroupGenericInline]