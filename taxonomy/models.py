import uuid

from django.db import models


class TaxonomyItem(models.Model):
    class TypeChoices(models.TextChoices):
        GENRE = 'GENRE', 'Жанр'
        TAG = 'TAG', 'Тег'
        TYPE = 'TYPE', 'Тип'
        CATEGORY = 'CATEGORY', 'Категория'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='Название')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Слаг')
    type = models.CharField(max_length=20, choices=TypeChoices.choices, verbose_name='Тип таксономии')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительский элемент'
    )
    description = models.TextField(blank=True, verbose_name='Описание')

    class Meta:
        ordering = ['type', 'name']
        verbose_name = 'Элемент таксономии'
        verbose_name_plural = 'Элементы таксономии'

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
    name = models.CharField(max_length=255, verbose_name='Название сырого термина')
    source_field = models.CharField(max_length=100, verbose_name='Источник поля', help_text="e.g., 'genre', 'type'")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    objects = RawTermManager()

    class Meta:
        unique_together = ('name', 'source_field')
        ordering = ['-created_at']
        verbose_name = 'Сырой термин'
        verbose_name_plural = 'Сырые термины'

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.source_field}] {self.name}"


class RawTermMapping(models.Model):
    raw_term = models.ForeignKey(RawTerm, on_delete=models.CASCADE, related_name='mappings',
                                 verbose_name='Сырой термин')
    taxonomy_item = models.ForeignKey(TaxonomyItem, on_delete=models.CASCADE, related_name='raw_mappings',
                                      verbose_name='Элемент таксономии')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата связи')

    class Meta:
        unique_together = ('raw_term', 'taxonomy_item')
        verbose_name = 'Связь сырого термина'
        verbose_name_plural = 'Связи сырых терминов'

    def __str__(self):
        return f"{self.raw_term.name} -> {self.taxonomy_item.name}"
