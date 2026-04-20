from django.db.models import Avg, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

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
