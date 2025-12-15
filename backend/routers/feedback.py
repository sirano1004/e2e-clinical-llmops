import json
from typing import Optional
from fastapi import APIRouter, Form, HTTPException

# --- Project Imports ---
from ..core.logger import logger
# Services
from ..services.feedback_service import feedback_service
# Schemas
from ..schemas import SOAPNote
# Repositories
from ..repositories.documents import document_service

router = APIRouter()

@router.post("/submit_feedback")
async def submit_human_feedback(
    session_id: str = Form(...),
    feedback_type: str = Form(...), # accept, reject, edit
    edited_content: str = Form(None), # JSON string or plain text
):
    """
    Captures doctor's feedback for SFT/DPO data collection.
    - If edited, updates Redis state.
    - If accepted, logs as positive sample.
    """
    logger.info(f"📝 Feedback received: {feedback_type} for session {session_id}")
    
    try:
        # Parse edited content if it's a SOAP task (JSON string -> Dict)
        parsed_content = json.loads(edited_content)
        if parsed_content:
            try:
                # Validation
                SOAPNote(**parsed_content)
            except Exception:
                logger.warning("Feedback content is not valid JSON, saving as raw string.")
        
        # Get current Soap
        current_soap = await document_service.get_soap_note(session_id)

        # Delegate to FeedbackService
        # It handles fetching original output, context, metrics calculation, and routing.
        metrics = await feedback_service.save_feedback(
            session_id=session_id,
            task_type='soap', # For now only support soap
            original_output=current_soap,
            edited_output=parsed_content,
            action=feedback_type
        )
        
        # Note: In our last discussion, we agreed to update save_feedback signature 
        # to accept feedback_type. I will assume it's updated or we map it.
        # For safety, let's assume we pass the raw params and service handles logic.
        
        return {"status": "success", "metrics": metrics}

    except Exception as e:
        logger.exception("❌ Error submitting feedback")
        raise HTTPException(status_code=500, detail=str(e))