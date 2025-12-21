import asyncio
from typing import Optional
from fastapi import APIRouter, Form, HTTPException

# --- Project Imports ---
from ..core.logger import logger
# Services
from ..services.feedback_service import feedback_service
# Repositories
from ..repositories.conversation import conversation_service
from ..repositories.notification import notification_service
from ..repositories.documents import document_service
router = APIRouter()

@router.get("/check_notifications")
async def check_notifications(

    session_id: str, 
    chunk_index: Optional[int] = None # Frontend sends this to get specific alerts
):
    """
    Frontend calls this to poll for warnings.
    - If chunk_index is sent: Checks only for that chunk (Fast).
    - If chunk_index is omitted: Checks all pending warnings.
    """
    # Fetch from Redis Hash
    results = asyncio.gather(
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
async def get_transcript(session_id: str):
    """
    poll for transcribed conversation
    """
    return await conversation_service.get_ui_segments(session_id)

@router.get("/get_soap_note")
async def get_soap_note(session_id: str):
    """
    poll for current SOAP note state
    """
    return await document_service.get_soap_note(session_id)

@router.post("/stop_session")
async def stop_session(session_id: str = Form(...)):
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
        # await conversation_service.clear_session(session_id)
        
        return {"status": "session_stopped"}
        
    except Exception as e:
        logger.exception("❌ Error stopping session")
        raise HTTPException(status_code=500, detail=str(e))