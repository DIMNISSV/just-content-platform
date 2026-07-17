import logging
from datetime import timedelta

from django.utils import timezone

from content.models import Title
from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


def log_title_view(title_id: str, viewer_id: str) -> None:
    """
    Логирует уникальный просмотр произведения. 
    Использует Redis для дедупликации (один просмотр в 2 часа от одного пользователя/гостя)
    и сохранения в суточные бакеты (Sorted Sets).
    """
    if not title_id or not viewer_id:
        return
    try:
        r = get_redis_client()
        debounce_key = f"view_debounce:{title_id}:{viewer_id}"
        if r.exists(debounce_key):
            return
        r.setex(debounce_key, 7200, "1")
        today = timezone.now().strftime('%Y-%m-%d')
        daily_key = f"views:daily:{today}"
        r.zincrby(daily_key, 1.0, title_id)
        r.expire(daily_key, 86400 * 35)
    except Exception as e:
        logger.error(f"Failed to log view in Redis for title {title_id}: {e}")


def get_trending_titles(limit: int = 12) -> list[Title]:
    """
    Извлекает произведения, набирающие популярность за последние 72 часа, 
    с поправкой на общую статистику просмотров за 30 дней и рейтинг.
    """
    try:
        r = get_redis_client()
        now = timezone.now()
        keys_72h = [f"views:daily:{(now - timedelta(days=i)).strftime('%Y-%m-%d')}" for i in range(3)]
        keys_30d = [f"views:daily:{(now - timedelta(days=i)).strftime('%Y-%m-%d')}" for i in range(30)]
        temp_72h = "views:temp:72h"
        temp_30d = "views:temp:30d"
        r.zunionstore(temp_72h, keys_72h)
        r.zunionstore(temp_30d, keys_30d)
        r.expire(temp_72h, 60)
        r.expire(temp_30d, 60)
        top_72h = r.zrevrange(temp_72h, 0, 199, withscores=True)
        if not top_72h:
            return list(Title.objects.order_by('-rating_score', '-votes_count')[:limit])
        title_scores = []
        title_ids = [t[0].decode('utf-8') for t in top_72h]
        scores_30d_raw = {tid.decode('utf-8'): score for tid, score in r.zscan_iter(temp_30d)}
        titles_db = {str(t.id): t for t in Title.objects.filter(id__in=title_ids)}
        for tid_bytes, v_72h in top_72h:
            tid = tid_bytes.decode('utf-8')
            title = titles_db.get(tid)
            if not title:
                continue
            v_30d = scores_30d_raw.get(tid, v_72h)
            trend_score = (v_72h / (v_30d + 1)) * max(1.0, title.rating_score)
            title_scores.append((trend_score, title))
        title_scores.sort(key=lambda x: x[0], reverse=True)
        return [t[1] for t in title_scores[:limit]]
    except Exception as e:
        logger.error(f"Failed to calculate trending titles: {e}")
        return list(Title.objects.order_by('-rating_score', '-votes_count')[:limit])
