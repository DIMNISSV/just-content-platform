from content.models import Title, Episode, WatchHistory, EpisodeWatchHistory


def update_episode_progress(
        user,
        episode: Episode,
        progress_ms: int,
        is_completed: bool,
        track_group=None,
        last_audio_asset_id=None,
        last_audio_track_name=None,
        last_quality_label=None
) -> tuple[EpisodeWatchHistory, WatchHistory]:
    """
    Saves or updates the progress of a specific episode for a user.
    Also synchronizes the parent Title's WatchHistory to update the
    global "Continue watching" entry.
    """
    episode_history, _ = EpisodeWatchHistory.objects.update_or_create(
        user=user,
        episode=episode,
        defaults={
            'progress_ms': progress_ms,
            'is_completed': is_completed,
        }
    )

    title_history, _ = WatchHistory.objects.update_or_create(
        user=user,
        title=episode.title,
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
        last_quality_label=None
) -> WatchHistory:
    """
    Saves or updates the progress of a standalone title (e.g., Movie)
    for a user.
    """
    title_history, _ = WatchHistory.objects.update_or_create(
        user=user,
        title=title,
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
