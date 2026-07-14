from django.db import transaction, IntegrityError
from django.db.models import Q
from content.models import Genre


def get_or_create_genre_safe(slug: str, name: str) -> Genre:
    genre = Genre.objects.filter(slug=slug).first()
    if genre:
        return genre

    genre = Genre.objects.filter(name=name).first()
    if genre:
        return genre

    try:
        with transaction.atomic():
            return Genre.objects.create(slug=slug, name=name)
    except IntegrityError:
        genre = Genre.objects.filter(Q(slug=slug) | Q(name=name)).first()
        if genre:
            return genre
        raise
