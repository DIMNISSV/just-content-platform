from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
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
    list_display = ('name', 'type', 'release_year')
    list_filter = ('type', 'genres')
    search_fields = ('name', 'original_name')
    filter_horizontal = ('genres',)
    # Для Фильмов показываем сборки дорожек (Воркбенч), для Сериалов - список эпизодов
    inlines =[TrackGroupGenericInline, EpisodeInline]

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'title', 'season_number', 'episode_number')
    list_filter = ('title',)
    # Для эпизодов показываем сборки дорожек (Воркбенч)
    inlines = [TrackGroupGenericInline]