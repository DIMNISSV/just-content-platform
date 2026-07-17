import logging
from django.db.models import Q
from content.models import WatchHistory, TitleRating
from recommendations.models import UserInterestProfile

logger = logging.getLogger(__name__)


def get_year_bin(year: int) -> str:
    """
    Categorizes a release year into a specific epoch bin.
    """
    if not year:
        return 'unknown'
    if year >= 2020:
        return 'modern'
    if year >= 2010:
        return '2010s'
    if year >= 2000:
        return '2000s'
    if year >= 1990:
        return '1990s'
    if year >= 1980:
        return '1980s'
    return 'older'


def build_profile_for_entity(user=None, guest_id=None) -> UserInterestProfile:
    """
    Calculates the multidimensional interest profile for a given user or guest.
    Reads WatchHistory and TitleRating to build frequency histograms.
    """
    if not user and not guest_id:
        raise ValueError("Either user or guest_id must be provided to build a profile.")

    # 1. Fetch History & Ratings
    if user:
        history_qs = WatchHistory.objects.filter(user=user).select_related('title').prefetch_related(
            'title__taxonomy_items')
        ratings_qs = TitleRating.objects.filter(user=user)
    else:
        history_qs = WatchHistory.objects.filter(guest_id=guest_id).select_related('title').prefetch_related(
            'title__taxonomy_items')
        ratings_qs = TitleRating.objects.none()

    # 2. Accumulate Base Weights per Title
    title_weights = {}
    for h in history_qs:
        # Base weight: 1.0 for completed, 0.3 for started
        w = 1.0 if h.is_completed else 0.3
        title_weights[h.title.id] = {'weight': w, 'title': h.title}

    for r in ratings_qs:
        if r.title.id not in title_weights:
            title_weights[r.title.id] = {'weight': 0.0, 'title': r.title}

        # Rating is 1-10. Neutral is 5.5.
        # Range mapped to -1.5 to +1.5
        rating_bonus = ((r.score - 5.5) / 4.5) * 1.5
        title_weights[r.title.id]['weight'] += rating_bonus

    # 3. Build Distributions (Histograms)
    tax_dist = {}
    type_dist = {'MOVIE': 0.0, 'SERIES': 0.0}
    year_dist = {}

    for t_id, data in title_weights.items():
        w = max(0.0, data['weight'])
        if w == 0:
            continue

        t = data['title']

        # Type Distribution
        type_dist[t.type] += w

        # Year Distribution
        y_bin = get_year_bin(t.release_year)
        year_dist[y_bin] = year_dist.get(y_bin, 0.0) + w

        # Taxonomy Distribution
        for tax in t.taxonomy_items.all():
            tax_id_str = str(tax.id)
            tax_dist[tax_id_str] = tax_dist.get(tax_id_str, 0.0) + w

    # 4. Save to DB
    profile, created = UserInterestProfile.objects.get_or_create(user=user, guest_id=guest_id)
    profile.taxonomy_distribution = tax_dist
    profile.type_distribution = type_dist
    profile.year_distribution = year_dist
    profile.save(update_fields=['taxonomy_distribution', 'type_distribution', 'year_distribution', 'updated_at'])

    identifier = user.email if user else f"Guest {guest_id}"
    logger.debug(f"Successfully calculated and saved Interest Profile for {identifier}.")

    return profile
