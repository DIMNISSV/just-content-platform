import logging
import os
import shutil

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .tasks import analyze_raw_file
from .models import RawMediaFile, Asset, AssetVariant

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=RawMediaFile)
def delete_raw_file_from_disk(sender, instance, **kwargs):
    """Удаляет исходный загруженный файл."""
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            logger.info(f"Deleted raw file: {instance.file.path}")


@receiver(post_delete, sender=AssetVariant)
def delete_variant_folder(sender, instance, **kwargs):
    """
    Удаляет папку конкретного варианта (со всеми HLS сегментами).
    Путь: media/assets/<asset_id>/<variant_id>/
    """
    variant_path = os.path.join(settings.MEDIA_ROOT, 'assets', str(instance.asset.id), str(instance.id))
    if os.path.exists(variant_path):
        shutil.rmtree(variant_path)
        logger.info(f"Deleted variant directory: {variant_path}")


@receiver(post_delete, sender=Asset)
def delete_asset_root_folder(sender, instance, **kwargs):
    """
    Удаляет корневую папку ассета, если она пуста после удаления вариантов.
    """
    asset_path = os.path.join(settings.MEDIA_ROOT, 'assets', str(instance.id))
    if os.path.exists(asset_path):
        # Если после удаления вариантов папка пуста (или остались только системные файлы), удаляем её
        try:
            if not os.listdir(asset_path):
                os.rmdir(asset_path)
            else:
                # Если вдруг что-то осталось, сносим всё под корень
                shutil.rmtree(asset_path)
            logger.info(f"Cleaned up asset directory: {asset_path}")
        except Exception as e:
            logger.error(f"Error cleaning up asset folder: {e}")


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
