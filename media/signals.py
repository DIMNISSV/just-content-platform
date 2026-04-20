from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import RawMediaFile
from .tasks import analyze_raw_file

@receiver(post_save, sender=RawMediaFile)
def trigger_file_analysis(sender, instance, created, **kwargs):
    """
    Triggers the Celery task to analyze the file using ffprobe
    immediately after a new RawMediaFile is created and saved.
    """
    if created and instance.status == RawMediaFile.Status.PENDING:
        # transaction.on_commit ensures the task is sent to Celery ONLY
        # after the database transaction is successfully committed.
        transaction.on_commit(lambda: analyze_raw_file.delay(instance.id))