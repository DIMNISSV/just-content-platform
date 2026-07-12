from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .models import TitleRating, TrackGroupRating, Title, Episode

@receiver([post_save, post_delete], sender=TitleRating)
def update_title_rating(sender, instance, **kwargs):
    title = instance.title
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

@receiver(pre_save, sender=Title)
def set_title_manual_priority(sender, instance, **kwargs):
    if getattr(instance, '_is_webhook_update', False):
        return
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.metadata_priority_level != instance.metadata_priority_level:
                return
        except sender.DoesNotExist:
            pass
    instance.metadata_priority_level = 9999

@receiver(pre_save, sender=Episode)
def set_episode_manual_priority(sender, instance, **kwargs):
    if getattr(instance, '_is_webhook_update', False):
        return
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.metadata_priority_level != instance.metadata_priority_level:
                return
        except sender.DoesNotExist:
            pass
    instance.metadata_priority_level = 9999
