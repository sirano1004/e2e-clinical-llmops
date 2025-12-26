import json
from datetime import datetime
from typing import List, Optional, Dict, Any

# --- Project Imports ---
from ..core.config import settings

# Session TimeOUt
SESSION_TTL = settings.session_ttl

def get_warnings_key(session_id: str) -> str:
    return f"session:{session_id}:warnings"

def get_safety_key(session_id: str) -> str:
    return f"session:{session_id}:safety"

class NotificationServiceAsync:
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()

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
        key = get_warnings_key(session_id)

        parsed_notifications = []

        if chunk_index is not None:
            # Case 1: Specific Chunk (Fastest)
            # Useful when UI just wants to check "Did this specific chunk fail?"
            field = str(chunk_index)
            raw_item = await self.redis_client.hget(key, field)
            
            if raw_item:
                try:
                    parsed_notifications.append(json.loads(raw_item))
                except json.JSONDecodeError:
                    pass
        else:
            # Case 2: Fetch ALL (Sync Mode)
            # Useful for initial load, refresh, or full polling.
            # hgetall retrieves the entire hash map efficiently.
            all_items = await self.redis_client.hgetall(key)
            
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

    async def get_safety_alerts(self, session_id: str, chunk_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all safety alerts.
        Using hgetall to fetch everything at once.
        """
        key = get_safety_key(session_id)
        
        parsed_alerts = []

        if chunk_index is None:
            all_items = await self.redis_client.hgetall(key)
            
            if not all_items:
                return []
                
            for _, raw_item in all_items.items():
                try:
                    parsed_alerts.append(json.loads(raw_item))
                except json.JSONDecodeError:
                    continue
        else:
            field = str(chunk_index)
            raw_item = await self.redis_client.hget(key, field)

            if not raw_item:
                return []

            try:
                parsed_alerts.append(json.loads(raw_item))        
            except json.JSONDecodeError:
                pass

        return parsed_alerts


class NotificationServiceSync:    
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()


    def add_warning(self, session_id: str, warnings: List[str], chunk_index: int):
        """
        Saves warnings into a Redis Hash mapped by chunk_index.
        Structure: session:{id}:warnings -> { "chunk_idx": JSON }
        
        Using HSET allows us to overwrite/update warnings for a specific chunk 
        if re-processed, and allows O(1) retrieval.
        """
        if not warnings:
            return
            
        key = get_warnings_key(session_id)
        
        # Construct structured data with Timezone-Aware Timestamp
        notification_data = {
            "chunk_index": chunk_index,
            # Use astimezone() to include timezone info (e.g., +09:00), safer than naive now()
            "timestamp": datetime.now().astimezone().isoformat(),
            "warnings": warnings
        }
        
        # O(1) Operation: Map chunk_index (field) to the warning data (value)
        self.redis_client.hset(key, str(chunk_index), json.dumps(notification_data))
        self.redis_client.expire(key, SESSION_TTL)

    def add_safety_alert(self, session_id: str, alerts: List[str], chunk_index: int):
        """
        Saves CRITICAL safety/guardrail alerts.
        Key Structure: session:{id}:safety -> { "chunk_idx": JSON }
        
        Distinct from 'warnings' because these represent clinical risks 
        (e.g., missed contraindications, dangerous advice).
        """
        if not alerts:
            return
            
        key = get_safety_key(session_id)
        
        alert_data = {
            "chunk_index": chunk_index,
            "timestamp": datetime.now().astimezone().isoformat(),
            "alerts": alerts
        }
        
        # Save to Redis
        self.redis_client.hset(key, str(chunk_index), json.dumps(alert_data))
        self.redis_client.expire(key, SESSION_TTL)