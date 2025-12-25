import json
from datetime import datetime
from typing import List, Optional, Dict, Any

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..core.config import settings
import hashlib

# Session TimeOUt
SESSION_TTL = settings.session_ttl

def hash_mrn(mrn: str) -> str:
    """Hash MRN using SHA-256 for secure storage."""
    return hashlib.sha256(mrn.encode()).hexdigest()[:32]

class SessionRepository:

    async def create_session(self, session_id: str, doctor_id: str, mrn: str) -> str:
        """
        Creates a new session and stores its metadata in Redis.
        Returns the generated session ID.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:metadata"

        metadata = {
            "doctor_id": doctor_id,
            "patient_id": hash_mrn(mrn),
            "session_start": datetime.now().astimezone().isoformat()
        }

        await client.hset(key, mapping=metadata)
        await client.expire(key, SESSION_TTL)

        return session_id

    async def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves session metadata from Redis.
        Returns None if session does not exist.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:metadata"

        raw_metadata = await client.hgetall(key)
        if not raw_metadata:
            return None

        return raw_metadata    

    async def clear_session(self, session_id: str):
        """
        Completely wipes ALL data related to a session.
        Uses SCAN to find all keys matching 'session:{id}:*' instead of a hardcoded list.
        """
        client = redis_client.get_instance()
        pattern = f"session:{session_id}:*"
        
        # 1. Find all keys belonging to this session
        # scan_iter is non-blocking and efficient for finding matching keys
        keys_to_delete = [key async for key in client.scan_iter(match=pattern)]
        
        # 2. Delete them all in one go
        if keys_to_delete:
            await client.delete(*keys_to_delete)
            # Optional: Log strictly for debugging
            # print(f"🧹 Cleared session {session_id}. Deleted keys: {keys_to_delete}")

session_service = SessionRepository()