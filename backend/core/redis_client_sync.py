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
        try:
            cls._instance = redis.Redis.from_url(
                url=settings.redis_url, 
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                max_connections=30, 
                retry_on_timeout=True
            )

            # Fail-fast (optional but recommended)
            cls._instance.ping()
            print("✅ Redis connection established successfully.")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to connect to Redis: {e}")
            # If Redis is down, the backend cannot function (stateful service).
            # We might want to raise error or exit, depending on policy.
            raise e

    @classmethod
    def get_instance(cls) -> redis.Redis:
        """
        Returns the active sync Redis client.
        If not connected yet, it will connect lazily.
        """
        if cls._instance is None:
            raise ConnectionError("Redis is not initialized. Ensure 'connect()' is called during startup.")
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