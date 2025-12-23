import json
from typing import Optional, Dict, Any
# --- Project Imports ---
from ..core.redis_client import redis_client
from ..core.config import settings

# Session TimeOUt
SESSION_TTL = settings.session_ttl

class BufferService:
    """
    Manages temporary buffers in Redis.
    Used for storing intermediate
    """

    async def save_chunk(self, session_id: str, chunk_index: int, payload: Dict[str, Any]):
        """
        Saves a chunk of data in a Redis hash.
        Each chunk is stored under a field named by its index.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:buffer"

        # Store the chunk as a JSON string
        await client.hset(key, str(chunk_index), json.dumps(payload))
        
        # Reset Expiration (Extend session life)
        await client.expire(key, SESSION_TTL)

    async def get_chunk(self, session_id: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific chunk of data from the Redis hash.
        Returns None if the chunk does not exist.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:buffer"

        raw_data = await client.hget(key, str(chunk_index))
        if raw_data is None:
            return None
        
        return json.loads(raw_data)
    
    async def del_chunk(self, session_id: str, chunk_index: int):
        """
        Deletes a specific chunk from the Redis hash.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:buffer"

        await client.hdel(key, str(chunk_index))

# singleton instance
buffer_service = BufferService()