import logging
from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

LOCK_PREFIX = "lock:title_refresh:"


def acquire_refresh_lock(title_id: str, expire_seconds: int = 900) -> bool:
    """
    Attempts to acquire a unique lock for refreshing a specific title.
    Returns True if the lock was successfully acquired, False otherwise.
    """
    try:
        r = get_redis_client()
        key = f"{LOCK_PREFIX}{title_id}"
        acquired = r.set(key, "active", ex=expire_seconds, nx=True)
        return bool(acquired)
    except Exception as e:
        logger.error(f"Failed to acquire lock for title {title_id} due to Redis error: {e}")
        return True


def release_refresh_lock(title_id: str) -> None:
    """
    Releases the refresh lock for a specific title.
    """
    try:
        r = get_redis_client()
        key = f"{LOCK_PREFIX}{title_id}"
        r.delete(key)
    except Exception as e:
        logger.error(f"Failed to release lock for title {title_id} due to Redis error: {e}")


def is_refresh_locked(title_id: str) -> bool:
    """
    Checks if a refresh task is currently active/locked for a specific title.
    """
    try:
        r = get_redis_client()
        key = f"{LOCK_PREFIX}{title_id}"
        return bool(r.exists(key))
    except Exception as e:
        logger.error(f"Failed to check lock status for title {title_id} due to Redis error: {e}")
        return False
