import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def reapply_taxonomy_to_titles():
    from content.models import Title, Genre
    from taxonomy.models import TaxonomyItem
    logger.info("Starting background re-application of taxonomy to titles...")
    titles = Title.objects.prefetch_related('raw_terms').all().iterator(chunk_size=1000)
    processed_count = 0
    for title in titles:
        all_raw_terms = title.raw_terms.all()
        if not all_raw_terms:
            continue
        tax_items = list(TaxonomyItem.objects.filter(raw_mappings__raw_term__in=all_raw_terms).distinct())
        title.taxonomy_items.set(tax_items)
        updated_fields = []
        has_series = any(t.slug == 'type-series' for t in tax_items)
        has_movie = any(t.slug == 'type-movie' for t in tax_items)
        if has_series and title.type != Title.Type.SERIES:
            title.type = Title.Type.SERIES
            updated_fields.append('type')
        elif has_movie and not has_series and title.type != Title.Type.MOVIE:
            title.type = Title.Type.MOVIE
            updated_fields.append('type')
        if updated_fields:
            title.save(update_fields=updated_fields)
        genre_tax_items = [t for t in tax_items if t.type == TaxonomyItem.TypeChoices.GENRE]
        if genre_tax_items:
            genre_objs = []
            for gt in genre_tax_items:
                g_obj, _ = Genre.objects.get_or_create(slug=gt.slug, defaults={'name': gt.name})
                genre_objs.append(g_obj)
            title.genres.set(genre_objs)
        processed_count += 1
    logger.info(f"Re-application task completed. Titles processed: {processed_count}.")
