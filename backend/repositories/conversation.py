import json
from typing import List, Dict, Any

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..core.config import settings
from ..schemas import (
    DialogueTurn, 
    SegmentInfo,
    WordInfo
)

# Session TimeOUt
from ..core.config import settings
SESSION_TTL = settings.session_ttl

class ConversationService:
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """

    async def add_dialogue_turns(self, session_id: str, turns: List[DialogueTurn]):
        """
        Appends new dialogue turns to the session history.
        """
        if not turns:
            return

        client = redis_client.get_instance()
        key = f"session:{session_id}:history"

        # Serialize Pydantic objects to JSON strings
        # Redis rpush accepts multiple arguments, so we unpack the list
        turn_data = [turn.model_dump_json() for turn in turns]
        
        await client.rpush(key, *turn_data)
        
        # Reset Expiration (Extend session life)
        await client.expire(key, SESSION_TTL)

    async def get_dialogue_history(self, session_id: str) -> List[DialogueTurn]:
        """
        Retrieves the full dialogue history for a session.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:history"

        # Range 0 to -1 means "everything"
        raw_list = await client.lrange(key, 0, -1)
        
        # Deserialize JSON strings back to Pydantic objects
        return [DialogueTurn.model_validate_json(item) for item in raw_list]

    async def add_ui_segments(self, session_id: str, segments: List[SegmentInfo]):
        """
        Appends raw UI segments (rich metadata like red underlines) to Redis.
        These are used by the frontend for real-time rendering.
        """
        if not segments:
            return
        
        client = redis_client.get_instance()
        key = f"session:{session_id}:ui_transcript"

        # Serialize to JSON strings
        serialized_segs = [segment.model_dump_json() for segment in segments]
            
        await client.rpush(key, *serialized_segs)
        await client.expire(key, SESSION_TTL)

    async def get_ui_segments(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the full list of UI segments for the frontend.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:ui_transcript"
        
        # Get all items (0 to -1)
        raw_data = await client.lrange(key, 0, -1)
        
        # Deserialize JSON strings back to dicts
        return [json.loads(seg) for seg in raw_data]

    async def get_next_chunk_index(self, session_id: str) -> int:
        """
        Atomically increments the chunk counter and returns the 0-based index 
        for the chunk currently being processed.
        
        This should be called by the API endpoint before calling TranscriberService.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:chunk_count"
        
        # INCR atomically increments the value (1, 2, 3, ...)
        # It returns the *new* count (1-based).
        new_count = await client.incr(key)
        
        # We return the 0-based index (0, 1, 2, ...)
        return new_count - 1
    
    async def get_expected_chunk_index(self, session_id: str) -> int:
        """
        Retrieves the expected next chunk index for ordering purposes.
        Used by the worker to determine if it's their turn to process.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:next_chunk"
        
        value = await client.get(key)
        if value is None:
            return 0
        return int(value)
    
    async def increment_expected_chunk_index(self, session_id: str):
        """
        Increments the expected chunk index by 1.
        Called by the worker after successfully processing a chunk.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:next_chunk"
        
        await client.incr(key)
    
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

# Singleton Instance
conversation_service = ConversationService()