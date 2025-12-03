import redis.asyncio as redis
from typing import Optional
import sys

# --- Project Imports ---
from .config import settings

class RedisClient:
    """
    Singleton wrapper for the Async Redis Connection.
    Responsible for establishing and closing the connection pool.
    """
    
    _instance: Optional[redis.Redis] = None

    @classmethod
    async def connect(cls):
        """
        Initializes the Redis connection pool on application startup.
        Should be called in the FastAPI lifespan event.
        """
        if cls._instance:
            return

        print(f"🔌 Connecting to Redis at {settings.redis_host}:{settings.redis_port}...")
        
        try:
            # Initialize Async Redis Client
            # decode_responses=True ensures we get 'str' instead of 'bytes'
            cls._instance = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=0, # Default database
                decode_responses=True, 
                socket_timeout=5.0,
                retry_on_timeout=True
            )
            
            # Ping to verify connection
            await cls._instance.ping()
            print("✅ Redis connection established successfully.")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to connect to Redis: {e}")
            # If Redis is down, the backend cannot function (stateful service).
            # We might want to raise error or exit, depending on policy.
            raise e

    @classmethod
    async def disconnect(cls):
        """
        Closes the Redis connection cleanly on application shutdown.
        """
        if cls._instance:
            print("🔌 Closing Redis connection...")
            await cls._instance.close()
            cls._instance = None
            print("✅ Redis connection closed.")

    @classmethod
    def get_instance(cls) -> redis.Redis:
        """
        Returns the active Redis client instance.
        Raises an error if accessed before 'connect()' is called.
        """
        if cls._instance is None:
            raise ConnectionError("Redis is not initialized. Ensure 'connect()' is called during startup.")
        return cls._instance

# Global Access Point
redis_client = RedisClient