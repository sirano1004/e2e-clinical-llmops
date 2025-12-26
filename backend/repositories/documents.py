from typing import Optional

# --- Project Imports ---
from ..core.config import settings
from ..schemas import SOAPNote

# Session TimeOUt
SESSION_TTL = settings.session_ttl

get_soap_note_key = lambda session_id: f"session:{session_id}:soap"
get_draft_key = lambda session_id, task_type: f"session:{session_id}:{task_type}:draft"

# Async Redis Document Service
class DocumentServiceAsync:
    
    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()
    
    async def get_soap_note(self, session_id: str) -> Optional[SOAPNote]:
        """
        Retrieves the current SOAP note state. Returns None if empty.
        """
        key = get_soap_note_key(session_id)

        data = await self.redis_client.get(key)
        
        if data:
            return SOAPNote.model_validate_json(data)
        return None

    async def get_text_draft(self, session_id: str, task_type: str) -> Optional[str]:
        """
        Retrieves a plain text draft.
        """
        key = get_draft_key(session_id, task_type)
        return await self.redis_client.get(key)
    

class DocumentServiceSync:
    """
    Synchronous wrapper for DocumentServiceAsync.
    """

    def __init__(self, redis_client):
        self.redis_client = redis_client.get_instance()

    def update_soap_note(self, session_id: str, note: SOAPNote):
        """
        Overwrites the current SOAP note state.
        """
        key = get_soap_note_key(session_id)

        # Save as JSON string
        self.redis_client.set(key, note.model_dump_json(), ex=SESSION_TTL)

    def get_soap_note(self, session_id: str) -> Optional[SOAPNote]:
        """
        Retrieves the current SOAP note state. Returns None if empty.
        """
        key = get_soap_note_key(session_id)

        data = self.redis_client.get(key)
        
        if data:
            return SOAPNote.model_validate_json(data)
        return None

    def save_text_draft(self, session_id: str, task_type: str, raw_text: str):
        """
        Saves a plain text draft (e.g., Referral, Certificate) temporarily.
        """
        key = get_draft_key(session_id, task_type)
        self.redis_client.set(key, raw_text, ex=SESSION_TTL)
    