import logging

from aggregator.models import ViewingSession
from aggregator.services.session_manager import SessionManager
from content.services.history_service import update_episode_progress, update_title_progress

logger = logging.getLogger(__name__)


class TelemetryProcessor:
    @staticmethod
    def process_session_telemetry(session_token: str, payload: dict) -> tuple[dict, int]:
        """
        Processes telemetry data received via a viewing session token.
        Validates the session and updates watch history for the associated user.
        """
        if not SessionManager.is_session_valid(session_token):
            return {"error": "Invalid or expired session token"}, 403

        try:
            session = ViewingSession.objects.get(id=session_token)
        except ViewingSession.DoesNotExist:
            return {"error": "Session not found"}, 404

        user = session.user
        content_type = session.content_type
        object_id = session.object_id

        # Extract telemetry data from payload
        progress_ms = payload.get('progress_ms', 0)
        is_completed = payload.get('is_completed', False)
        track_group_id = payload.get('track_group_id')
        audio_asset_id = payload.get('audio_asset_id')
        audio_track_name = payload.get('audio_track_name')
        quality_label = payload.get('quality_label')

        # Resolve track group if provided
        from content.models import TrackGroup
        track_group = None
        if track_group_id:
            try:
                track_group = TrackGroup.objects.get(id=track_group_id)
            except TrackGroup.DoesNotExist:
                pass

        # Determine if it's an episode or a title and update progress
        from content.models import Title, Episode
        if content_type.model == 'episode':
            try:
                episode = Episode.objects.get(id=object_id)
                episode_history, _ = update_episode_progress(
                    user=user,
                    episode=episode,
                    progress_ms=progress_ms,
                    is_completed=is_completed,
                    track_group=track_group,
                    last_audio_asset_id=audio_asset_id,
                    last_audio_track_name=audio_track_name,
                    last_quality_label=quality_label
                )
                return {
                    "status": "saved",
                    "progress_ms": episode_history.progress_ms,
                    "type": "episode"
                }, 200
            except Episode.DoesNotExist:
                return {"error": "Episode not found"}, 404

        elif content_type.model == 'title':
            try:
                title = Title.objects.get(id=object_id)
                title_history = update_title_progress(
                    user=user,
                    title=title,
                    progress_ms=progress_ms,
                    is_completed=is_completed,
                    track_group=track_group,
                    last_audio_asset_id=audio_asset_id,
                    last_audio_track_name=audio_track_name,
                    last_quality_label=quality_label
                )
                return {
                    "status": "saved",
                    "progress_ms": title_history.progress_ms,
                    "type": "title"
                }, 200
            except Title.DoesNotExist:
                return {"error": "Title not found"}, 404

        return {"error": "Unsupported content type for session telemetry"}, 400
