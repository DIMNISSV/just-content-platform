import redis
from django.conf import settings

_redis_client = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
        _redis_client = redis.Redis.from_url(url)
    return _redis_client
