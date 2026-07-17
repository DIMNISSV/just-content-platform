from content.models import Title, Episode, WatchHistory, EpisodeWatchHistory


def update_episode_progress(
        user,
        episode: Episode,
        progress_ms: int,
        is_completed: bool,
        track_group=None,
        last_audio_asset_id=None,
        last_audio_track_name=None,
        last_quality_label=None,
        guest_id=None
) -> tuple[EpisodeWatchHistory, WatchHistory]:
    lookup_episode = {}
    lookup_title = {}

    if user and user.is_authenticated:
        lookup_episode['user'] = user
        lookup_title['user'] = user
    elif guest_id:
        lookup_episode['guest_id'] = guest_id
        lookup_title['guest_id'] = guest_id
    else:
        raise ValueError("Either user or guest_id must be provided to update watch history.")

    lookup_episode['episode'] = episode
    episode_history, _ = EpisodeWatchHistory.objects.update_or_create(
        **lookup_episode,
        defaults={
            'progress_ms': progress_ms,
            'is_completed': is_completed,
        }
    )

    lookup_title['title'] = episode.title
    title_history, _ = WatchHistory.objects.update_or_create(
        **lookup_title,
        defaults={
            'episode': episode,
            'track_group': track_group,
            'last_audio_asset_id': last_audio_asset_id,
            'last_audio_track_name': last_audio_track_name,
            'last_quality_label': last_quality_label,
            'progress_ms': progress_ms,
            'is_completed': is_completed,
        }
    )

    return episode_history, title_history


def update_title_progress(
        user,
        title: Title,
        progress_ms: int,
        is_completed: bool,
        track_group=None,
        last_audio_asset_id=None,
        last_audio_track_name=None,
        last_quality_label=None,
        guest_id=None
) -> WatchHistory:
    lookup_title = {}

    if user and user.is_authenticated:
        lookup_title['user'] = user
    elif guest_id:
        lookup_title['guest_id'] = guest_id
    else:
        raise ValueError("Either user or guest_id must be provided to update watch history.")

    lookup_title['title'] = title
    title_history, _ = WatchHistory.objects.update_or_create(
        **lookup_title,
        defaults={
            'episode': None,
            'track_group': track_group,
            'last_audio_asset_id': last_audio_asset_id,
            'last_audio_track_name': last_audio_track_name,
            'last_quality_label': last_quality_label,
            'progress_ms': progress_ms,
            'is_completed': is_completed,
        }
    )
    return title_history
