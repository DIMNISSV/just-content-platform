import logging

from django.utils import timezone

from content.models import Title, WatchHistory
from recommendations.models import UserInterestProfile
from recommendations.services.profiler import get_year_bin

logger = logging.getLogger(__name__)


def normalize_dist(dist: dict) -> dict:
    """Нормализует веса гистограммы в диапазоне от 0.0 до 1.0"""
    if not dist:
        return {}
    max_val = max(dist.values()) if dist.values() else 0
    if max_val == 0:
        return {}
    return {k: v / max_val for k, v in dist.items()}


def get_recommendations(user=None, guest_id=None, limit=10) -> list:
    """
    Генерирует персональные рекомендации на основе многомерного профиля-гистограммы.
    """
    if user:
        watched_ids = WatchHistory.objects.filter(user=user).values_list('title_id', flat=True)
        profile = UserInterestProfile.objects.filter(user=user).first()
    elif guest_id:
        watched_ids = WatchHistory.objects.filter(guest_id=guest_id).values_list('title_id', flat=True)
        profile = UserInterestProfile.objects.filter(guest_id=guest_id).first()
    else:
        watched_ids = []
        profile = None

    current_year = timezone.now().year

    # 1. Fallback для новых пользователей/гостей без истории
    if not profile or not profile.taxonomy_distribution:
        candidates = list(Title.objects.exclude(id__in=watched_ids)
                          .filter(release_year__gte=current_year - 2)
                          .order_by('-rating_score', '-votes_count')[:limit])
        if len(candidates) < limit:
            extra = list(Title.objects.exclude(id__in=watched_ids)
                         .exclude(id__in=[c.id for c in candidates])
                         .order_by('-rating_score')[:limit - len(candidates)])
            candidates.extend(extra)
        return candidates

    # 2. Нормализация гистограмм
    tax_dist = normalize_dist(profile.taxonomy_distribution)
    type_dist = normalize_dist(profile.type_distribution)
    year_dist = normalize_dist(profile.year_distribution)

    # 3. Выделение пиков (top N taxonomy items) для формирования пула кандидатов
    top_tax_ids = sorted(tax_dist.keys(), key=lambda k: tax_dist[k], reverse=True)[:10]

    candidates_qs = Title.objects.exclude(id__in=watched_ids).prefetch_related('taxonomy_items')
    if top_tax_ids:
        candidates_qs = candidates_qs.filter(taxonomy_items__id__in=top_tax_ids).distinct()

    candidates = list(candidates_qs.order_by('-rating_score')[:500])

    # Паддинг, если кандидатов слишком мало
    if len(candidates) < limit:
        extra = Title.objects.exclude(id__in=watched_ids).exclude(id__in=[c.id for c in candidates]).order_by(
            '-rating_score')[:100]
        candidates.extend(extra)

    # 4. Расчет TotalScore
    scored_candidates = []
    is_sparse_profile = len(watched_ids) < 5  # Профиль недостаточно заполнен

    # Весовые коэффициенты компонентов
    W_TAX = 2.0
    W_TYPE = 1.0
    W_YEAR = 1.0
    W_FRESH = 1.5

    for c in candidates:
        # TaxMatch: Совпадение с пиками жанров/тегов
        tax_match = sum(tax_dist.get(str(t.id), 0.0) for t in c.taxonomy_items.all())

        # TypeMatch: Совпадение типа (Movie/Series)
        type_match = type_dist.get(c.type, 0.0)

        # YearMatch: Попадание в любимую эпоху
        y_bin = get_year_bin(c.release_year)
        year_match = year_dist.get(y_bin, 0.0)

        # Freshness Bonus: Подталкиваем новинки для пользователей с малой историей
        freshness_bonus = 0.0
        if is_sparse_profile and c.release_year and c.release_year >= current_year - 2:
            freshness_bonus = 1.0

        total_score = (tax_match * W_TAX) + (type_match * W_TYPE) + (year_match * W_YEAR) + (freshness_bonus * W_FRESH)

        # Легкий модификатор базового рейтинга, чтобы плохой контент не всплывал слишком высоко
        total_score *= (1.0 + (c.rating_score / 20.0))

        scored_candidates.append((total_score, c))

    # 5. Сортировка и выдача
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return [c for score, c in scored_candidates[:limit]]
