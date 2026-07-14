import uuid
from django.db import migrations


def migrate_data(apps, schema_editor):
    Title = apps.get_model('content', 'Title')
    Genre = apps.get_model('content', 'Genre')
    TaxonomyItem = apps.get_model('taxonomy', 'TaxonomyItem')
    RawTerm = apps.get_model('taxonomy', 'RawTerm')
    RawTermMapping = apps.get_model('taxonomy', 'RawTermMapping')

    movie_type, _ = TaxonomyItem.objects.get_or_create(
        slug='type-movie',
        defaults={'name': 'Movie', 'type': 'TYPE'}
    )
    series_type, _ = TaxonomyItem.objects.get_or_create(
        slug='type-series',
        defaults={'name': 'Series', 'type': 'TYPE'}
    )

    raw_movie, _ = RawTerm.objects.get_or_create(name='movie', source_field='type')
    raw_series, _ = RawTerm.objects.get_or_create(name='series', source_field='type')

    RawTermMapping.objects.get_or_create(raw_term=raw_movie, taxonomy_item=movie_type)
    RawTermMapping.objects.get_or_create(raw_term=raw_series, taxonomy_item=series_type)

    genres = list(Genre.objects.all())

    existing_tax_items = {t.slug: t for t in TaxonomyItem.objects.filter(type='GENRE')}
    existing_raw_terms = {r.name.strip().lower(): r for r in RawTerm.objects.filter(source_field='genre')}

    new_tax_items = []
    new_raw_terms = []

    for genre in genres:
        if genre.slug not in existing_tax_items:
            new_tax_items.append(TaxonomyItem(
                id=uuid.uuid4(),
                slug=genre.slug,
                name=genre.name,
                type='GENRE'
            ))
            existing_tax_items[genre.slug] = True

        genre_name_lower = genre.name.strip().lower()
        if genre_name_lower not in existing_raw_terms:
            new_raw_terms.append(RawTerm(
                name=genre_name_lower,
                source_field='genre'
            ))
            existing_raw_terms[genre_name_lower] = True

    if new_tax_items:
        TaxonomyItem.objects.bulk_create(new_tax_items, ignore_conflicts=True)
    if new_raw_terms:
        RawTerm.objects.bulk_create(new_raw_terms, ignore_conflicts=True)

    tax_items_by_slug = {t.slug: t for t in TaxonomyItem.objects.filter(type='GENRE')}
    raw_terms_by_name = {r.name.strip().lower(): r for r in RawTerm.objects.filter(source_field='genre')}

    existing_mappings = set(RawTermMapping.objects.values_list('raw_term_id', 'taxonomy_item_id'))
    new_mappings = []
    genre_id_to_tax_id = {}

    for genre in genres:
        tax_item = tax_items_by_slug.get(genre.slug)
        raw_term = raw_terms_by_name.get(genre.name.strip().lower())

        if tax_item:
            genre_id_to_tax_id[genre.id] = tax_item.id
            if raw_term and (raw_term.id, tax_item.id) not in existing_mappings:
                new_mappings.append(RawTermMapping(raw_term=raw_term, taxonomy_item=tax_item))
                existing_mappings.add((raw_term.id, tax_item.id))

    if new_mappings:
        RawTermMapping.objects.bulk_create(new_mappings, ignore_conflicts=True)

    TitleTaxonomyThrough = Title.taxonomy_items.through
    m2m_objects = []

    title_types = Title.objects.values_list('id', 'type')
    for title_id, t_type in title_types.iterator(chunk_size=10000):
        if t_type == 'MOVIE':
            m2m_objects.append(TitleTaxonomyThrough(title_id=title_id, taxonomyitem_id=movie_type.id))
        elif t_type == 'SERIES':
            m2m_objects.append(TitleTaxonomyThrough(title_id=title_id, taxonomyitem_id=series_type.id))

    TitleGenreThrough = Title.genres.through
    for title_id, genre_id in TitleGenreThrough.objects.values_list('title_id', 'genre_id').iterator(chunk_size=10000):
        tax_item_id = genre_id_to_tax_id.get(genre_id)
        if tax_item_id:
            m2m_objects.append(TitleTaxonomyThrough(title_id=title_id, taxonomyitem_id=tax_item_id))

    if m2m_objects:
        TitleTaxonomyThrough.objects.bulk_create(m2m_objects, batch_size=5000, ignore_conflicts=True)


def reverse_migrate(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0008_title_taxonomy_items'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_migrate)
    ]
