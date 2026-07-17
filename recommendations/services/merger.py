import logging
from django.db import transaction
from content.models import WatchHistory, EpisodeWatchHistory
from recommendations.services.profiler import build_profile_for_entity

logger = logging.getLogger(__name__)


def merge_guest_profile(user, guest_id: str) -> int:
    """
    Transfers all watch history from a guest profile to an authenticated user.
    Returns the number of transferred records.
    """
    if not guest_id:
        return 0

    try:
        with transaction.atomic():
            # 1. Merge Title History
            title_history = WatchHistory.objects.filter(guest_id=guest_id)
            count_titles = title_history.count()
            title_history.update(user=user, guest_id=None)

            # 2. Merge Episode History
            ep_history = EpisodeWatchHistory.objects.filter(guest_id=guest_id)
            count_eps = ep_history.count()
            ep_history.update(user=user, guest_id=None)

            # 3. Update the multi-dimensional profile for the user
            build_profile_for_entity(user=user)

            logger.info(f"Merged guest profile {guest_id} into user {user.email}. "
                        f"Transferred {count_titles} title records and {count_eps} episode records.")

            return count_titles + count_eps

    except Exception as e:
        logger.error(f"Failed to merge guest profile {guest_id} into user {user.email}: {e}")
        raise e
