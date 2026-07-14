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

    raw_movie, _ = RawTerm.objects.get_or_create(name='MOVIE', source_field='type')
    raw_series, _ = RawTerm.objects.get_or_create(name='SERIES', source_field='type')

    RawTermMapping.objects.get_or_create(raw_term=raw_movie, taxonomy_item=movie_type)
    RawTermMapping.objects.get_or_create(raw_term=raw_series, taxonomy_item=series_type)

    for genre in Genre.objects.all():
        tax_item, _ = TaxonomyItem.objects.get_or_create(
            slug=genre.slug,
            defaults={'name': genre.name, 'type': 'GENRE'}
        )
        raw_term, _ = RawTerm.objects.get_or_create(
            name=genre.name,
            source_field='genre'
        )
        RawTermMapping.objects.get_or_create(raw_term=raw_term, taxonomy_item=tax_item)

    for title in Title.objects.prefetch_related('genres').all():
        if title.type == 'MOVIE':
            title.taxonomy_items.add(movie_type)
        elif title.type == 'SERIES':
            title.taxonomy_items.add(series_type)

        for genre in title.genres.all():
            try:
                tax_item = TaxonomyItem.objects.get(slug=genre.slug)
                title.taxonomy_items.add(tax_item)
            except TaxonomyItem.DoesNotExist:
                continue


def reverse_migrate(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0008_title_taxonomy_items'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_migrate)
    ]
