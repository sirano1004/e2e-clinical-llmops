import json
from typing import List, Dict, Any

# --- Project Imports ---
from ..core.config import settings
from ..schemas import (
    DialogueTurn, 
    SegmentInfo
)
# Session TimeOUt
SESSION_TTL = settings.session_ttl

def get_dialogue_key(session_id: str) -> str:
    return f"session:{session_id}:history"

def get_ui_transcript_key(session_id: str) -> str:
    return f"session:{session_id}:ui_transcript"

def get_chunk_count_key(session_id: str) -> str:
    return f"session:{session_id}:chunk_count"

def get_next_chunk_key(session_id: str) -> str:
    return f"session:{session_id}:next_chunk"

class ConversationRepositorySync:
    """
    Synchronous wrapper for ConversationService.
    Used in non-async contexts.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()
    
    def add_dialogue_turns(self, session_id: str, turns: List[DialogueTurn]):
        """
        Appends new dialogue turns to the session history.
        """
        if not turns:
            return

        key = get_dialogue_key(session_id)

        # Serialize Pydantic objects to JSON strings
        # Redis rpush accepts multiple arguments, so we unpack the list
        turn_data = [turn.model_dump_json() for turn in turns]
        
        self.redis_client.rpush(key, *turn_data)
        
        # Reset Expiration (Extend session life)
        self.redis_client.expire(key, SESSION_TTL)        

    def get_dialogue_history(self, session_id: str) -> List[DialogueTurn]:
        """
        Retrieves the full dialogue history for a session.
        """
        key = get_dialogue_key(session_id)

        # Range 0 to -1 means "everything"
        raw_list = self.redis_client.lrange(key, 0, -1)
        
        # Deserialize JSON strings back to Pydantic objects
        return [DialogueTurn.model_validate_json(item) for item in raw_list]
    
    def add_ui_segments(self, session_id: str, segments: List[SegmentInfo]):
        """
        Appends raw UI segments (rich metadata like red underlines) to Redis.
        These are used by the frontend for real-time rendering.
        """
        if not segments:
            return
        
        key = get_ui_transcript_key(session_id)

        # Serialize to JSON strings
        serialized_segs = [segment.model_dump_json() for segment in segments]
            
        self.redis_client.rpush(key, *serialized_segs)
        self.redis_client.expire(key, SESSION_TTL)
    

    def get_expected_chunk_index(self, session_id: str) -> int:
        """
        Retrieves the expected next chunk index for ordering purposes.
        Used by the worker to determine if it's their turn to process.
        """

        key = get_next_chunk_key(session_id)
        
        value = self.redis_client.get(key)
        
        if value is None:
            return 0
        return int(value)
    
    def increment_expected_chunk_index(self, session_id: str):
        """
        Increments the expected chunk index by 1.
        Called by the worker after successfully processing a chunk.
        """
        key = get_next_chunk_key(session_id)        
        next_chunk_index = self.redis_client.incr(key)
        self.redis_client.expire(key, SESSION_TTL)

        return next_chunk_index
    
class ConversationRepositoryAsync:
    """
    Asynchronous wrapper for ConversationService.
    Used in async contexts.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()

    async def get_dialogue_history(self, session_id: str) -> List[DialogueTurn]:
        """
        Retrieves the full dialogue history for a session.
        """
        key = get_dialogue_key(session_id)

        # Range 0 to -1 means "everything"
        raw_list = await self.redis_client.lrange(key, 0, -1)
        
        # Deserialize JSON strings back to Pydantic objects
        return [DialogueTurn.model_validate_json(item) for item in raw_list]

    async def get_ui_segments(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the full list of UI segments for the frontend.
        """
        key = get_ui_transcript_key(session_id)
        
        # Get all items (0 to -1)
        raw_data = await self.redis_client.lrange(key, 0, -1)

        # Deserialize JSON strings back to dicts
        return [json.loads(seg) for seg in raw_data]

    async def get_next_chunk_index(self, session_id: str) -> int:
        """
        Atomically increments the chunk counter and returns the 0-based index 
        for the chunk currently being processed.
        
        This should be called by the API endpoint before calling TranscriberService.
        """
        key = get_chunk_count_key(session_id)
        
        # INCR atomically increments the value (1, 2, 3, ...)
        # It returns the *new* count (1-based).
        new_count = await self.redis_client.incr(key)
        await self.redis_client.expire(key, SESSION_TTL)
        
        # We return the 0-based index (0, 1, 2, ...)
        return new_count - 1
    