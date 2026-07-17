import json
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Max
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView, DetailView

from aggregator.models import ExternalContentRegistry
from aggregator.services.session_manager import SessionManager
from aggregator.tasks import enqueue_title_refresh
from content.models import Title, Episode, Favorite, WatchHistory, TitleRating
from recommendations.services.velocity import get_trending_titles
from users.models import UserPreference


class HomeView(TemplateView):
    template_name = 'content/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trending'] = get_trending_titles(limit=12)
        context['new_movies'] = Title.objects.filter(
            type=Title.Type.MOVIE
        ).order_by('-created_at')[:6]

        thirty_days_ago = timezone.now() - timedelta(days=30)
        new_series_qs = Title.objects.filter(
            type=Title.Type.SERIES,
            episodes__created_at__gte=thirty_days_ago
        ).annotate(
            last_episode_date=Max('episodes__created_at')
        ).order_by('-last_episode_date', '-release_year').distinct()[:6]
        context['new_series'] = new_series_qs

        return context


class WatchView(DetailView):
    model = Title
    template_name = 'content/watch.html'
    context_object_name = 'title'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('taxonomy_items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        enqueue_title_refresh(self.object)

        context['content_type'] = 'title'
        context['player_id'] = self.object.id
        context['title_id'] = self.object.id
        context['episode_id'] = ''
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_audio_track_name'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0
        context['is_favorite'] = 'false'
        context['language_code'] = 'rus'
        context['preferred_voiceovers'] = '[]'
        context['auto_skip'] = 'false'

        context['session_token'] = ''
        context['plugin_script_url'] = ''

        title_obj = self.object
        if self.request.user.is_authenticated:
            plugin = ExternalContentRegistry.objects.filter(
                title=title_obj,
                episode__isnull=True,
                plugin__is_active=True
            ).select_related('plugin').first()

            if plugin:
                context['plugin_script_url'] = plugin.plugin.client_script_url or ''

                ctype = ContentType.objects.get_for_model(Title)
                session = SessionManager.create_session(
                    user=self.request.user,
                    content_type=ctype,
                    object_id=title_obj.id
                )
                context['session_token'] = str(session.id)

            pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
            context['language_code'] = pref.language_code
            context['preferred_voiceovers'] = json.dumps(pref.preferred_voiceovers)
            context['auto_skip'] = 'true' if pref.auto_skip_intro else 'false'
            if Favorite.objects.filter(user=self.request.user, title=title_obj).exists():
                context['is_favorite'] = 'true'
            history = WatchHistory.objects.filter(user=self.request.user, title=title_obj).first()
            if history:
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_audio_track_name'] = history.last_audio_track_name or ''
                context['last_quality'] = history.last_quality_label or ''
                context['start_progress'] = history.progress_ms
            rating = TitleRating.objects.filter(user=self.request.user, title=self.object).first()
            if rating:
                context['user_title_rating'] = rating.score
        return context


class EpisodeWatchView(DetailView):
    model = Episode
    template_name = 'content/watch.html'
    context_object_name = 'episode'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        title = self.object.title

        enqueue_title_refresh(title)

        context['title'] = title
        context['content_type'] = 'episode'
        context['player_id'] = self.object.id
        context['title_id'] = title.id
        context['episode_id'] = self.object.id
        context['start_progress'] = 0
        context['last_track_group'] = ''
        context['last_audio_asset'] = ''
        context['last_audio_track_name'] = ''
        context['last_quality'] = ''
        context['user_title_rating'] = 0
        context['is_favorite'] = 'false'
        context['language_code'] = 'rus'
        context['preferred_voiceovers'] = '[]'
        context['auto_skip'] = 'false'

        context['session_token'] = ''
        context['plugin_script_url'] = ''

        if self.request.user.is_authenticated:
            plugin = ExternalContentRegistry.objects.filter(
                episode=self.object,
                plugin__is_active=True
            ).select_related('plugin').first()

            if plugin:
                context['plugin_script_url'] = plugin.plugin.client_script_url or ''

                ctype = ContentType.objects.get_for_model(Episode)
                session = SessionManager.create_session(
                    user=self.request.user,
                    content_type=ctype,
                    object_id=self.object.id
                )
                context['session_token'] = str(session.id)

            pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
            context['language_code'] = pref.language_code
            context['preferred_voiceovers'] = json.dumps(pref.preferred_voiceovers)
            context['auto_skip'] = 'true' if pref.auto_skip_intro else 'false'
            if Favorite.objects.filter(user=self.request.user, title=title).exists():
                context['is_favorite'] = 'true'
            history = WatchHistory.objects.filter(user=self.request.user, title=title).first()
            if history:
                context['last_track_group'] = history.track_group_id or ''
                context['last_audio_asset'] = str(history.last_audio_asset_id) if history.last_audio_asset_id else ''
                context['last_audio_track_name'] = history.last_audio_track_name or ''
                context['last_quality'] = history.last_quality_label or ''
                if history.episode_id == self.object.id:
                    context['start_progress'] = history.progress_ms
            rating = TitleRating.objects.filter(user=self.request.user, title=title).first()
            if rating:
                context['user_title_rating'] = rating.score
        return context


class CatalogView(TemplateView):
    template_name = 'content/catalog.html'


@staff_member_required
def upload_wizard_view(request):
    context = {
        'site_header': 'Just Content Admin',
        'has_permission': True,
        'is_popup': False,
    }
    return render(request, 'admin/upload_wizard.html', context)
