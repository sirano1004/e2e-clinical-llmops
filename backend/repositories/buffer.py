import json
from typing import Optional, Dict, Any
# --- Project Imports ---
from ..core.config import settings

# Session TimeOUt
SESSION_TTL = settings.session_ttl

class BufferServiceSync:
    """
    Manages temporary buffers in Redis.
    Used for storing intermediate
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()

    def save_chunk(self, session_id: str, chunk_index: int, payload: Dict[str, Any]):
        """
        Saves a chunk of data in a Redis hash.
        Each chunk is stored under a field named by its index.
        """
        key = f"session:{session_id}:buffer"

        # Store the chunk as a JSON string
        self.redis_client.hset(key, str(chunk_index), json.dumps(payload))

        # Reset Expiration (Extend session life)
        self.redis_client.expire(key, SESSION_TTL)

    def get_chunk(self, session_id: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific chunk of data from the Redis hash.
        Returns None if the chunk does not exist.
        """
        key = f"session:{session_id}:buffer"

        raw_data = self.redis_client.hget(key, str(chunk_index))
        if raw_data is None:
            return None
        
        return json.loads(raw_data)

    def del_chunk(self, session_id: str, chunk_index: int):
        """
        Deletes a specific chunk from the Redis hash.
        """
        key = f"session:{session_id}:buffer"

        self.redis_client.hdel(key, str(chunk_index))

