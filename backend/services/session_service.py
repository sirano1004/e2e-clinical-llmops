import json
from typing import List, Optional, Dict

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..schemas import DialogueTurn, SOAPNote

# Session TimeOUt
SESSION_TTL = 3600

class SessionService:
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

    async def update_soap_note(self, session_id: str, note: SOAPNote):
        """
        Overwrites the current SOAP note state.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:soap"

        # Save as JSON string
        await client.set(key, note.model_dump_json(), ex=SESSION_TTL)

    async def get_soap_note(self, session_id: str) -> Optional[SOAPNote]:
        """
        Retrieves the current SOAP note state. Returns None if empty.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:soap"

        data = await client.get(key)
        
        if data:
            return SOAPNote.model_validate_json(data)
        return None
    
    # 💡 Metrics Management (Atomic Increments)
    async def update_metrics(self, session_id: str, metrics: Dict[str, int]):
        """
        Aggregates new chunk metrics into the session totals using Redis Hash.
        Using HINCRBY ensures atomic updates without race conditions.
        """
        if not metrics:
            return

        client = redis_client.get_instance()
        key = f"session:{session_id}:metrics"

        # Iterate over each metric (e.g., matched_count, transcript_count) and increment
        # This adds the new values to the existing totals automatically.
        for field, value in metrics.items():
            if value > 0:
                await client.hincrby(key, field, value)
        
        # Refresh TTL for the metrics key as well
        await client.expire(key, SESSION_TTL)

    async def get_metrics(self, session_id: str) -> Dict[str, int]:
        """
        Retrieves the aggregated session metrics.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:metrics"
        
        # Fetch all fields from the hash
        data = await client.hgetall(key)
        
        # Redis returns dict values as strings, so we convert them back to integers
        # Example: {'hallucination_count': '2'} -> {'hallucination_count': 2}
        return {k: int(v) for k, v in data.items()}

    async def save_text_draft(self, session_id: str, task_type: str, raw_text: str):
        """
        Saves a plain text draft (e.g., Referral, Certificate) temporarily.
        """
        client = redis_client.get_instance()
        # Key: session:referral:draft
        key = f"session:{session_id}:{task_type}:draft" 
        await client.set(key, raw_text, ex=SESSION_TTL)

    async def get_text_draft(self, session_id: str, task_type: str) -> Optional[str]:
        """
        Retrieves a plain text draft.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:{task_type}:draft"
        return await client.get(key)

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

    async def clear_session(self, session_id: str):
        """
        Manually deletes session data (e.g., when a doctor clicks 'Finish').
        """
        client = redis_client.get_instance()
        keys = [
            f"session:{session_id}:history", 
            f"session:{session_id}:soap",
            f"session:{session_id}:metrics",
            f"session:{session_id}:chunk_count"
        ]

        # 2. Define dynamic keys (unstructured text drafts)
        # We must explicitly list all possible tasks that use the 'draft' pattern.
        # This list should match the Litreal types in schemas.py that use save_text_draft.
        text_draft_tasks = ["referral", "certificate"]
        
        for task in text_draft_tasks:
            keys.append(f"session:{session_id}:{task}:draft")

        await client.delete(*keys)

# Singleton Instance
session_service = SessionService()