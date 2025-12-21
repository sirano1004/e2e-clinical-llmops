import asyncio
import functools
from backend.core.redis_client import redis_client

def async_worker_task(func):
    """
    Async wrapper for Celery tasks.
    1. Automatically executes asyncio.run().
    2. Automatically establishes Redis connection.
    3. Automatically closes Redis connection when task completes.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        async def _runner():
            await redis_client.connect()
            try:
                return await func(*args, **kwargs)
            finally:
                await redis_client.disconnect()
        return asyncio.run(_runner())
    
    return wrapper
