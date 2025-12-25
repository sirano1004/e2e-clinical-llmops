import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..schemas import (
    DialogueTurn, 
    SOAPNote, 
    SegmentInfo,
    WordInfo
)
from ..core.logger import logger

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
    async def update_metrics(self, session_id: str, metrics: Union[Dict[str, int], float, int], field: Optional[str] = None):
        """
        Aggregates new chunk metrics into the session totals using Redis Hash.
        Using HINCRBY ensures atomic updates without race conditions.
        """
        if not metrics:
            return

        # Single value update requires a field name
        if field is None and not isinstance(metrics, dict):
            logger.error(f"❌ update_metrics error: Field name missing for single value update.")
            return

        client = redis_client.get_instance()
        key = f"session:{session_id}:metrics"

        if isinstance(metrics, dict):
            # Iterate over each metric (e.g., matched_count, transcript_count) and increment
            # This adds the new values to the existing totals automatically.
            for f, v in metrics.items():
                if v != 0: 
                    if isinstance(v, float):
                        await client.hincrbyfloat(key, f, v)
                    elif isinstance(v, int):
                        await client.hincrby(key, f, v)
        
        elif field:
            if isinstance(metrics, int):
                await client.hincrby(key, field, metrics)
            elif isinstance(metrics, float):
                await client.hincrbyfloat(key, field, metrics)
        
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

    async def update_feedback_stats(self, session_id: str, similarity: Optional[float], distance: Optional[int], action: str):
        """
        Aggregates human feedback metrics into Redis atomically.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:metrics"

        # 1. Indicator that feedback received.
        await client.hincrby(key, "feedback_indc", 1)
        
        # 2. Rating accumulation
        if action == "accept":
            await client.hincrby(key, "accept_count", 1)
        elif action == "reject":
            await client.hincrby(key, "reject_count", 1)
        elif action == "edit":
            if similarity is not None and distance is not None:
                await client.hincrbyfloat(key, "total_similarity", similarity)
                await client.hincrby(key, "total_edit_distance", distance)
                await client.hincrby(key, "edit_count", 1)
            else:
                logger.warning(f"⚠️ Edit feedback received without metrics for session {session_id}")
            
        # Refresh TTL
        await client.expire(key, SESSION_TTL)

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
    
    async def add_warning(self, session_id: str, warnings: List[str], chunk_index: int):
        """
        Saves warnings into a Redis Hash mapped by chunk_index.
        Structure: session:{id}:warnings -> { "chunk_idx": JSON }
        
        Using HSET allows us to overwrite/update warnings for a specific chunk 
        if re-processed, and allows O(1) retrieval.
        """
        if not warnings:
            return
            
        client = redis_client.get_instance()
        key = f"session:{session_id}:warnings"
        
        # Construct structured data with Timezone-Aware Timestamp
        notification_data = {
            "chunk_index": chunk_index,
            # Use astimezone() to include timezone info (e.g., +09:00), safer than naive now()
            "timestamp": datetime.now().astimezone().isoformat(),
            "warnings": warnings
        }
        
        # O(1) Operation: Map chunk_index (field) to the warning data (value)
        await client.hset(key, str(chunk_index), json.dumps(notification_data))
        await client.expire(key, SESSION_TTL)

    async def get_warnings(self, session_id: str, chunk_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves warnings from Redis.
        
        Strategy:
        - If chunk_index is provided: Fetch ONLY that specific chunk (Pinpoint check).
        - If chunk_index is None: Fetch ALL warnings (Global sync).
        
        Why not a loop?
        - Looping hget() N times causes N network round-trips (Slow).
        - hgetall() gets everything in 1 round-trip (Fast).
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:warnings"
        
        parsed_notifications = []

        if chunk_index is not None:
            # Case 1: Specific Chunk (Fastest)
            # Useful when UI just wants to check "Did this specific chunk fail?"
            field = str(chunk_index)
            raw_item = await client.hget(key, field)
            
            if raw_item:
                try:
                    parsed_notifications.append(json.loads(raw_item))
                except json.JSONDecodeError:
                    pass
        else:
            # Case 2: Fetch ALL (Sync Mode)
            # Useful for initial load, refresh, or full polling.
            # hgetall retrieves the entire hash map efficiently.
            all_items = await client.hgetall(key)
            
            if not all_items:
                return []
                
            for _, raw_item in all_items.items():
                try:
                    parsed_notifications.append(json.loads(raw_item))
                except json.JSONDecodeError:
                    continue
        
        # Note: We do NOT delete items here (Persistence).
        # This allows the frontend to refresh the page without losing warnings.
        
        return parsed_notifications

    async def add_safety_alert(self, session_id: str, alerts: List[str], chunk_index: int):
        """
        Saves CRITICAL safety/guardrail alerts.
        Key Structure: session:{id}:safety -> { "chunk_idx": JSON }
        
        Distinct from 'warnings' because these represent clinical risks 
        (e.g., missed contraindications, dangerous advice).
        """
        if not alerts:
            return
            
        client = redis_client.get_instance()
        # Different Key for Safety Alerts
        key = f"session:{session_id}:safety"
        
        alert_data = {
            "chunk_index": chunk_index,
            "timestamp": datetime.now().astimezone().isoformat(),
            "alerts": alerts
        }
        
        # Save to Redis
        await client.hset(key, str(chunk_index), json.dumps(alert_data))
        await client.expire(key, SESSION_TTL)

    async def get_safety_alerts(self, session_id: str, chunk_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all safety alerts.
        Using hgetall to fetch everything at once.
        """
        client = redis_client.get_instance()
        key = f"session:{session_id}:safety"
        
        parsed_alerts = []

        if chunk_index is None:
            all_items = await client.hgetall(key)
            
            if not all_items:
                return []
                
            for _, raw_item in all_items.items():
                try:
                    parsed_alerts.append(json.loads(raw_item))
                except json.JSONDecodeError:
                    continue
        else:
            field = str(chunk_index)
            raw_item = await client.hget(key, field)

            if not raw_item:
                return []

            try:
                parsed_alerts.append(json.loads(raw_item))        
            except json.JSONDecodeError:
                pass

        return parsed_alerts

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
session_service = SessionService()