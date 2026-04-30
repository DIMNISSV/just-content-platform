from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Title, Episode
from .models import TitleRating, TrackGroupRating


@receiver([post_save, post_delete], sender=TitleRating)
def update_title_rating(sender, instance, **kwargs):
    title = instance.title
    # Агрегируем среднее значение и количество через БД
    stats = title.ratings.aggregate(avg_score=Avg('score'), count=Count('id'))

    title.rating_score = stats['avg_score'] or 0.0
    title.votes_count = stats['count'] or 0
    title.save(update_fields=['rating_score', 'votes_count'])


@receiver([post_save, post_delete], sender=TrackGroupRating)
def update_track_group_rating(sender, instance, **kwargs):
    track_group = instance.track_group
    stats = track_group.ratings.aggregate(avg_score=Avg('score'), count=Count('id'))

    track_group.rating_score = stats['avg_score'] or 0.0
    track_group.votes_count = stats['count'] or 0
    track_group.save(update_fields=['rating_score', 'votes_count'])


@receiver(post_save, sender=Title)
def sync_title_to_hub(sender, instance, created, **kwargs):
    # Только если мы Node и это не системное зеркалирование (avoid loops)
    if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'NODE' and not getattr(instance, '_mirrored', False):
        from .tasks import push_metadata_to_hub
        push_metadata_to_hub.delay('title', str(instance.id))


@receiver(post_save, sender=Episode)
def sync_episode_to_hub(sender, instance, created, **kwargs):
    if getattr(settings, 'PLATFORM_ROLE', 'NODE') == 'NODE' and not getattr(instance, '_mirrored', False):
        from .tasks import push_metadata_to_hub
        push_metadata_to_hub.delay('episode', str(instance.id))
