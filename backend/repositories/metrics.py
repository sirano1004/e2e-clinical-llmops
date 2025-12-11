from typing import Optional, Dict, Union

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..core.config import settings
from ..core.logger import logger

# Session TimeOUt
SESSION_TTL = settings.session_ttl

class MetricsService:
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """

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

# Singleton Instance
metrics_service = MetricsService()