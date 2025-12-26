from typing import Optional, Dict, Union

# --- Project Imports ---
from ..core.config import settings
from ..core.logger import logger

# Session TimeOUt
SESSION_TTL = settings.session_ttl
get_metrics_key = lambda session_id: f"session:{session_id}:metrics"

class MetricsServiceSync:
    """
    Synchronous wrapper for MetricsServiceAsync.
    """

    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()
    
    # 💡 Metrics Management (Atomic Increments)
    def update_metrics(self, session_id: str, metrics: Union[Dict[str, int], float, int], field: Optional[str] = None):
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

        key = get_metrics_key(session_id)

        if isinstance(metrics, dict):
            # Iterate over each metric (e.g., matched_count, transcript_count) and increment
            # This adds the new values to the existing totals automatically.
            for f, v in metrics.items():
                if v != 0: 
                    if isinstance(v, float):
                        self.redis_client.hincrbyfloat(key, f, v)
                    elif isinstance(v, int):
                        self.redis_client.hincrby(key, f, v)
        
        elif field:
            if isinstance(metrics, int):
                self.redis_client.hincrby(key, field, metrics)
            elif isinstance(metrics, float):
                self.redis_client.hincrbyfloat(key, field, metrics)

        # Refresh TTL for the metrics key as well
        self.redis_client.expire(key, SESSION_TTL)

class MetricsServiceAsync:
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()
    
    def _parse_redis_value(self, v: str) -> Union[int, float, str]:
        """Intelligently convert Redis string to int or float"""
        try:
            f_val = float(v)
            # If it's a whole number like 3.0, convert to int; otherwise keep as float like 3.5
            return int(f_val) if f_val.is_integer() else f_val
        except (ValueError, TypeError):
            return v  # If not a number, return as string

    async def get_metrics(self, session_id: str) -> Dict[str, int]:
        """
        Retrieves the aggregated session metrics.
        """
        key = get_metrics_key(session_id)

        # Fetch all fields from the hash
        data = await self.redis_client.hgetall(key)
        
        # Redis returns dict values as strings, so we convert them back to integers
        # Example: {'hallucination_count': '2'} -> {'hallucination_count': 2}
        return {k: self._parse_redis_value(v) for k, v in data.items()}
            
    async def update_feedback_stats(self, session_id: str, similarity: Optional[float], distance: Optional[int], action: str):
        """
        Aggregates human feedback metrics into Redis atomically.
        """
        key = get_metrics_key(session_id)

        # 1. Indicator that feedback received.
        await self.redis_client.hincrby(key, "feedback_indc", 1)
        
        # 2. Rating accumulation
        if action == "accept":
            await self.redis_client.hincrby(key, "accept_count", 1)
        elif action == "reject":
            await self.redis_client.hincrby(key, "reject_count", 1)
        elif action == "edit":
            if similarity is not None and distance is not None:
                await self.redis_client.hincrbyfloat(key, "total_similarity", similarity)
                await self.redis_client.hincrby(key, "total_edit_distance", distance)
                await self.redis_client.hincrby(key, "edit_count", 1)
            else:
                logger.warning(f"⚠️ Edit feedback received without metrics for session {session_id}")
            
        # Refresh TTL
        await self.redis_client.expire(key, SESSION_TTL)
