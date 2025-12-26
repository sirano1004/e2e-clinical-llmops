import redis
from typing import Optional

from .config import settings

class RedisClientSync:
    """
    Sync Redis client singleton (Celery threads용).
    Usage:
        from backend.core.redis_client_sync import redis_client
        r = redis_client.get_instance()
        r.hset(...)
    """

    _instance: Optional[redis.Redis] = None

    @classmethod
    def connect(cls) -> None:
        """
        Initialize the client (safe to call multiple times).
        Optional: call once at Celery worker start.
        """
        if cls._instance is not None:
            return

        cls._instance = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        # Fail-fast (optional but recommended)
        cls._instance.ping()

    @classmethod
    def get_instance(cls) -> redis.Redis:
        """
        Returns the active sync Redis client.
        If not connected yet, it will connect lazily.
        """
        if cls._instance is None:
            cls.connect()
        return cls._instance

    @classmethod
    def disconnect(cls) -> None:
        """
        Optional cleanup. Usually not required for Celery workers.
        """
        if cls._instance is not None:
            try:
                cls._instance.close()
            finally:
                cls._instance = None


# Global Access Point (same naming as async version)
redis_client = RedisClientSync