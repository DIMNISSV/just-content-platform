# Generated manually to merge duplicate capitalized raw terms

from django.db import migrations


def normalize_raw_terms(apps, schema_editor):
    RawTerm = apps.get_model('taxonomy', 'RawTerm')
    RawTermMapping = apps.get_model('taxonomy', 'RawTermMapping')
    Title = apps.get_model('content', 'Title')

    TitleRawTerms = Title.raw_terms.through

    all_terms = list(RawTerm.objects.all())

    groups = {}
    for term in all_terms:
        key = (term.name.strip().lower(), term.source_field)
        groups.setdefault(key, []).append(term)

    for (lowered_name, source_field), terms in groups.items():
        if not terms:
            continue

        # Choose canonical term - preferably the one that is already lowercase
        canonical = next((t for t in terms if t.name == lowered_name), terms[0])

        # Force save canonical as lowercase if it isn't already
        if canonical.name != lowered_name:
            canonical.name = lowered_name
            canonical.save(update_fields=['name'])

        duplicates = [t for t in terms if t.id != canonical.id]

        for dup in duplicates:
            # Re-map taxonomy bindings
            for mapping in RawTermMapping.objects.filter(raw_term=dup):
                if not RawTermMapping.objects.filter(raw_term=canonical, taxonomy_item_id=mapping.taxonomy_item_id).exists():
                    mapping.raw_term = canonical
                    mapping.save(update_fields=['raw_term'])
                else:
                    mapping.delete()

            # Re-map title relationships
            dup_links = TitleRawTerms.objects.filter(rawterm_id=dup.id)
            for link in dup_links:
                if not TitleRawTerms.objects.filter(title_id=link.title_id, rawterm_id=canonical.id).exists():
                    link.rawterm_id = canonical.id
                    link.save(update_fields=['rawterm_id'])
                else:
                    link.delete()

            # Safely remove the duplicated entry
            dup.delete()


def reverse_normalize(apps, schema_editor):
    # This migration is irreversible because duplicates are destroyed
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('taxonomy', '0001_initial'),
        ('content', '0010_title_raw_terms'),
    ]

    operations = [
        migrations.RunPython(normalize_raw_terms, reverse_normalize),
    ]