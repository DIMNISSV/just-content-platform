import json
import logging
import os

from django.conf import settings

from .models import TaxonomyItem, RawTerm, RawTermMapping

logger = logging.getLogger(__name__)


def sync_taxonomy_presets() -> dict:
    """
    Reads the JSON presets file and idempotently creates TaxonomyItems, RawTerms, and RawTermMappings.
    """
    file_path = os.path.join(settings.BASE_DIR, 'taxonomy', 'taxonomy_presets.json')
    if not os.path.exists(file_path):
        logger.warning(f"Presets file not found at {file_path}")
        return {"status": "error", "message": "Presets file not found."}

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return {"status": "error", "message": "Invalid JSON format."}

    items_data = data.get('taxonomy_items', [])
    mappings_data = data.get('mappings', [])

    item_objects = {}

    # First pass: Create all items
    for item in items_data:
        obj, _ = TaxonomyItem.objects.update_or_create(
            slug=item['slug'],
            defaults={
                'name': item['name'],
                'type': item['type'],
                'description': item.get('description', '')
            }
        )
        item_objects[item['slug']] = obj

    # Second pass: Assign parents if they exist in the preset
    for item in items_data:
        parent_slug = item.get('parent_slug')
        if parent_slug and parent_slug in item_objects:
            obj = item_objects[item['slug']]
            obj.parent = item_objects[parent_slug]
            obj.save(update_fields=['parent'])

    for mapping in mappings_data:
        raw_term_name = mapping['raw_term'].strip().lower()
        source_field = mapping['source_field']
        maps_to_slugs = mapping.get('maps_to', [])

        raw_term, _ = RawTerm.objects.get_or_create(
            name=raw_term_name,
            source_field=source_field
        )

        for slug in maps_to_slugs:
            if slug in item_objects:
                RawTermMapping.objects.get_or_create(
                    raw_term=raw_term,
                    taxonomy_item=item_objects[slug]
                )

    # Запуск фоновой задачи для пересчета таксономий у существующих тайтлов
    from .tasks import reapply_taxonomy_to_titles
    reapply_taxonomy_to_titles.delay()

    return {"status": "success", "message": "Presets synchronized successfully."}
