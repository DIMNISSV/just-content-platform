from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from aggregator.models import ViewingSession


class SessionManager:
    SESSION_DURATION_MINUTES = 15

    @staticmethod
    def create_session(user, content_type, object_id) -> ViewingSession:
        expires_at = timezone.now() + timedelta(minutes=SessionManager.SESSION_DURATION_MINUTES)
        session = ViewingSession.objects.create(
            user=user,
            content_type=content_type,
            object_id=str(object_id),
            expires_at=expires_at
        )
        return session

    @staticmethod
    def extend_session(session_id: str) -> ViewingSession:
        try:
            session = ViewingSession.objects.get(id=session_id)
            session.expires_at = timezone.now() + timedelta(minutes=SessionManager.SESSION_DURATION_MINUTES)
            session.save(update_fields=['expires_at'])
            return session
        except ViewingSession.DoesNotExist:
            raise ObjectDoesNotExist(f"ViewingSession {session_id} not found.")

    @staticmethod
    def is_session_valid(session_id: str) -> bool:
        return ViewingSession.objects.filter(
            id=session_id,
            expires_at__gt=timezone.now()
        ).exists()
