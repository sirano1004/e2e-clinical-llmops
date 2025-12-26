import json
from datetime import datetime
from typing import List, Optional, Dict, Any

# --- Project Imports ---
from ..core.config import settings
import hashlib

# Session TimeOUt
SESSION_TTL = settings.session_ttl

def hash_mrn(mrn: str) -> str:
    """Hash MRN using SHA-256 for secure storage."""
    return hashlib.sha256(mrn.encode()).hexdigest()[:32]

get_metadata_key = lambda session_id: f"session:{session_id}:metadata"

class SessionRepositoryAsync:
    """
    Manages session creation, metadata retrieval, and deletion using Redis.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()

    async def create_session(self, session_id: str, doctor_id: str, mrn: str) -> str:
        """
        Creates a new session and stores its metadata in Redis.
        Returns the generated session ID.
        """
        key = get_metadata_key(session_id)

        metadata = {
            "doctor_id": doctor_id,
            "patient_id": hash_mrn(mrn),
            "session_start": datetime.now().astimezone().isoformat()
        }

        await self.redis_client.hset(key, mapping=metadata)
        await self.redis_client.expire(key, SESSION_TTL)

        return session_id

    async def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves session metadata from Redis.
        Returns None if session does not exist.
        """
        key = get_metadata_key(session_id)

        raw_metadata = await self.redis_client.hgetall(key)
        if not raw_metadata:
            return None

        return raw_metadata    

    async def clear_session(self, session_id: str):
        """
        Completely wipes ALL data related to a session.
        Uses SCAN to find all keys matching 'session:{id}:*' instead of a hardcoded list.
        """
        pattern = f"session:{session_id}:*"
        
        # 1. Find all keys belonging to this session
        # scan_iter is non-blocking and efficient for finding matching keys
        keys_to_delete = [key async for key in self.redis_client.scan_iter(match=pattern)]
        
        # 2. Delete them all in one go
        if keys_to_delete:
            await self.redis_client.delete(*keys_to_delete)
            # Optional: Log strictly for debugging
            # print(f"🧹 Cleared session {session_id}. Deleted keys: {keys_to_delete}")
