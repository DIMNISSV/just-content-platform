import uuid

from django.db import models


class TaxonomyItem(models.Model):
    class TypeChoices(models.TextChoices):
        GENRE = 'GENRE', 'Genre'
        TAG = 'TAG', 'Tag'
        TYPE = 'TYPE', 'Type'
        CATEGORY = 'CATEGORY', 'Category'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=TypeChoices.choices)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['type', 'name']

    def __str__(self):
        return f"{self.get_type_display()}: {self.name}"


class RawTermManager(models.Manager):
    def get_or_create(self, defaults=None, **kwargs):
        if 'name' in kwargs:
            kwargs['name'] = kwargs['name'].strip().lower()
        if defaults and 'name' in defaults:
            defaults['name'] = defaults['name'].strip().lower()
        return super().get_or_create(defaults=defaults, **kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        if 'name' in kwargs:
            kwargs['name'] = kwargs['name'].strip().lower()
        if defaults and 'name' in defaults:
            defaults['name'] = defaults['name'].strip().lower()
        return super().update_or_create(defaults=defaults, **kwargs)


class RawTerm(models.Model):
    name = models.CharField(max_length=255)
    source_field = models.CharField(max_length=100, help_text="e.g., 'genre', 'type'")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RawTermManager()

    class Meta:
        unique_together = ('name', 'source_field')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.source_field}] {self.name}"


class RawTermMapping(models.Model):
    raw_term = models.ForeignKey(RawTerm, on_delete=models.CASCADE, related_name='mappings')
    taxonomy_item = models.ForeignKey(TaxonomyItem, on_delete=models.CASCADE, related_name='raw_mappings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('raw_term', 'taxonomy_item')

    def __str__(self):
        return f"{self.raw_term.name} -> {self.taxonomy_item.name}"
