import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client():
    """Return a shared Redis client, or None when Redis is not configured/available."""
    global _redis_client
    redis_url = (settings.REDIS_URL or "").strip()
    if not redis_url:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        _redis_client = redis.Redis.from_url(redis_url, socket_connect_timeout=3)
        _redis_client.ping()
        logger.info(f"Connected to Redis job queue at {redis_url}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}). Falling back to in-process background tasks.")
        _redis_client = None
        return None


def is_redis_available() -> bool:
    return get_redis_client() is not None


def enqueue_audio_job(note_id: str) -> bool:
    """Push a note_id onto the durable Redis queue. Returns True if queued."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        payload = json.dumps({"note_id": note_id})
        client.rpush(settings.JOB_QUEUE_NAME, payload)
        logger.info(f"Enqueued note {note_id} on Redis queue {settings.JOB_QUEUE_NAME}")
        return True
    except Exception as e:
        logger.warning(f"Failed to enqueue note {note_id} on Redis ({e}). Using fallback.")
        return False


def get_queue_depth() -> Optional[int]:
    client = get_redis_client()
    if client is None:
        return None
    try:
        return int(client.llen(settings.JOB_QUEUE_NAME))
    except Exception:
        return None
