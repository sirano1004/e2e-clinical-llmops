import asyncio
import functools
# --- Project Imports ---
from ..core.redis_client import RedisClient, redis_client

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
            # 1. Kill existing connection (if any) 
            if RedisClient._instance:
                RedisClient._instance = None

            # 2. Establish new connection
            print(f"🔄 [Task] Forcing new Redis connection for Event Loop...")
            await redis_client.connect()

            try:
                return await func(*args, **kwargs)
            finally:
                await redis_client.disconnect()
            
        return asyncio.run(_runner())
    
    return wrapper
