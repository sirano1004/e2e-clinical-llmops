import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, Depends

# --- Project Imports ---
from ..core.logger import logger
# Services
from ..services.feedback_service import feedback_service
# Repositories
from ..core.redis_client import redis_client
from ..repositories.conversation import ConversationRepositoryAsync
from ..repositories.notification import NotificationServiceAsync
from ..repositories.documents import DocumentServiceAsync
from ..repositories.session import SessionRepositoryAsync
router = APIRouter()

def get_document_service() -> DocumentServiceAsync:
    return DocumentServiceAsync(redis_client.get_instance())

def get_session_service() -> SessionRepositoryAsync:
    return SessionRepositoryAsync(redis_client.get_instance())

def get_conversation_service() -> ConversationRepositoryAsync:
    return ConversationRepositoryAsync(redis_client.get_instance())

def get_notification_service() -> NotificationServiceAsync:
    return NotificationServiceAsync(redis_client.get_instance())

@router.get("/check_notifications")
async def check_notifications(
    session_id: str, 
    chunk_index: Optional[int] = None, # Frontend sends this to get specific alerts
    notification_service: NotificationServiceAsync = Depends(get_notification_service)
):
    """
    Frontend calls this to poll for warnings.
    - If chunk_index is sent: Checks only for that chunk (Fast).
    - If chunk_index is omitted: Checks all pending warnings.
    """
    # Fetch from Redis Hash
    results = await asyncio.gather(
        notification_service.get_warnings(session_id, chunk_index),
        notification_service.get_safety_alerts(session_id)
    )
    
    warnings = results[0]
    safety_alerts = results[1]

    response = {
        "warnings": warnings,        # Frontend: Show generally (Yellow/Toast)
        "safety_alerts": safety_alerts # Frontend: Show prominently (Red/Modal)
    }
    
    if warnings or safety_alerts:
        logger.info(f"🔔 Retrieved notifications for {session_id}: {len(warnings)} warnings, {len(safety_alerts)} alerts")
        
    return response

@router.get("/get_transcript")
async def get_transcript(session_id: str, conversation_service: ConversationRepositoryAsync = Depends(get_conversation_service)):
    """
    poll for transcribed conversation
    """
    return await conversation_service.get_ui_segments(session_id)

@router.get("/get_soap_note")
async def get_soap_note(
    session_id: str,
    document_service: DocumentServiceAsync = Depends(get_document_service)
    ):
    """
    poll for current SOAP note state
    """
    return await document_service.get_soap_note(session_id)

@router.post("/stop_session")
async def stop_session(session_id: str = Form(...), session_service: SessionRepositoryAsync = Depends(get_session_service)):
    """
    Ends the consultation.
    - Flushes metrics to long-term storage.
    - Could trigger a final cleanup or snapshot if needed.
    """
    logger.info(f"🛑 Stopping session: {session_id}")
    
    try:
        # 1. Save Session Metrics (Persistence)
        await feedback_service.save_session_metrics(session_id)
        
        # 2. (Optional) Clear Redis if you want immediate cleanup
        await session_service.clear_session(session_id)
        
        return {"status": "session_stopped"}
        
    except Exception as e:
        logger.exception("❌ Error stopping session")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start_session")
async def start_session(
        doctor_id: str = Form(...),
        mrn: str = Form(...),
        session_service: SessionRepositoryAsync = Depends(get_session_service)
):
    """
    Initializes a new consultation session.
    - Creates a new session ID.
    - Sets up initial Redis keys and TTLs.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"🚀 Starting new session {session_id} for Doctor {doctor_id}, MRN {mrn}")
    
    try:
        # Initialize any required Redis structures here
        await session_service.create_session(session_id, doctor_id, mrn)

        return {
            "status": "session_started",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.exception("❌ Error starting session")
        raise HTTPException(status_code=500, detail=str(e))