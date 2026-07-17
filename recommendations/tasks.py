import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from content.models import WatchHistory, EpisodeWatchHistory, TitleRating
from recommendations.services.profiler import build_profile_for_entity
from users.models import User

logger = logging.getLogger(__name__)


@shared_task
def aggregate_user_profiles_task():
    """
    Finds all users and guests who had any viewing or rating activity
    in the last 24 hours and recalculates their multidimensional interest profiles.
    """
    threshold = timezone.now() - timedelta(hours=24)

    active_histories = WatchHistory.objects.filter(updated_at__gte=threshold)
    users_to_update = set(active_histories.exclude(user__isnull=True).values_list('user_id', flat=True))
    guests_to_update = set(active_histories.exclude(guest_id__isnull=True).values_list('guest_id', flat=True))

    active_ratings = TitleRating.objects.filter(updated_at__gte=threshold)
    users_to_update.update(active_ratings.values_list('user_id', flat=True))

    processed_users = 0
    processed_guests = 0

    for u_id in users_to_update:
        user = User.objects.filter(id=u_id).first()
        if user:
            try:
                build_profile_for_entity(user=user)
                processed_users += 1
            except Exception as e:
                logger.error(f"Failed to build profile for user {u_id}: {e}")

    for g_id in guests_to_update:
        if g_id:
            try:
                build_profile_for_entity(guest_id=g_id)
                processed_guests += 1
            except Exception as e:
                logger.error(f"Failed to build profile for guest {g_id}: {e}")

    logger.info(f"Profile aggregation complete. Updated {processed_users} users and {processed_guests} guests.")


@shared_task
def cleanup_guest_history_task():
    """
    Deletes watch history records that are not associated with any authenticated user
    and are older than 30 days.
    """
    threshold = timezone.now() - timedelta(days=30)

    # Cleanup Title History
    deleted_titles, _ = WatchHistory.objects.filter(
        user__isnull=True,
        updated_at__lt=threshold
    ).delete()

    # Cleanup Episode History
    deleted_eps, _ = EpisodeWatchHistory.objects.filter(
        user__isnull=True,
        updated_at__lt=threshold
    ).delete()

    logger.info(f"Guest cleanup complete. Removed {deleted_titles} title records and {deleted_eps} episode records.")
