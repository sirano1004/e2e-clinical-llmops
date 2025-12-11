from typing import Optional

# --- Project Imports ---
from ..core.redis_client import redis_client
from ..core.config import settings
from ..schemas import SOAPNote
from ..core.logger import logger

# Session TimeOUt
SESSION_TTL = settings.session_ttl

class DocumentService:
    """
    Manages session state (Dialogue History & SOAP Note) using Redis.
    Acts as the 'Memory Manager' for the application.
    """

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

# Singleton Instance
document_service = DocumentService()