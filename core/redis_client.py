import redis
from django.conf import settings

_redis_pool = None


def get_redis_client() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
        _redis_pool = redis.ConnectionPool.from_url(url)
    return redis.Redis(connection_pool=_redis_pool)
