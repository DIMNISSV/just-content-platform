import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def reapply_taxonomy_to_titles():
    """
    Background task to reapply taxonomy mappings to all titles.
    На этапе 3 модель Title получит поле M2M к RawTerm,
    что позволит эффективно пересчитывать taxonomy_items.
    """
    logger.info("Starting background re-application of taxonomy to titles...")
    # TODO: На этапе 3 здесь будет логика перебора Title, связанных с обновленными RawTerm,
    # и переопределение их Title.taxonomy_items на основе новых правил.
    logger.info("Re-application task completed.")
