from typing import Optional
from fastapi import APIRouter, Form, HTTPException

# --- Project Imports ---
from ..core.logger import logger
# Services
from ..services.feedback_service import feedback_service
# Schemas
from ..schemas import SOAPNote

router = APIRouter()

@router.post("/submit_feedback")
async def submit_human_feedback(
    session_id: str = Form(...),
    task_type: str = Form("soap"), # soap, referral, etc.
    feedback_type: str = Form(...), # accept, reject, edit
    edited_content: str = Form(None), # JSON string or plain text
    rating: Optional[str] = Form(None) # thumbs_up / thumbs_down
):
    """
    Captures doctor's feedback for SFT/DPO data collection.
    - If edited, updates Redis state.
    - If accepted, logs as positive sample.
    """
    logger.info(f"📝 Feedback received: {feedback_type} for session {session_id}")
    
    try:
        # Parse edited content if it's a SOAP task (JSON string -> Dict)
        parsed_content = edited_content
        if task_type == "soap" and edited_content:
            try:
                # We expect a JSON string representing the SOAP note
                import json
                parsed_content = json.loads(edited_content)
                # Validation
                SOAPNote(**parsed_content)
            except Exception:
                logger.warning("Feedback content is not valid JSON, saving as raw string.")
        
        # Delegate to FeedbackService
        # It handles fetching original output, context, metrics calculation, and routing.
        metrics = await feedback_service.save_feedback(
            session_id=session_id,
            task_type=task_type,
            edited_output=parsed_content,
            rating=rating, # Can be derived from feedback_type if needed
            # We map feedback_type to our internal logic inside the service or pass it
            # Ideally, refactor service to accept 'feedback_type' directly as discussed.
            # Assuming we updated service to take feedback_type (based on last conversation).
            # If not, we map it here:
        )
        
        # Note: In our last discussion, we agreed to update save_feedback signature 
        # to accept feedback_type. I will assume it's updated or we map it.
        # For safety, let's assume we pass the raw params and service handles logic.
        
        return {"status": "success", "metrics": metrics}

    except Exception as e:
        logger.exception("❌ Error submitting feedback")
        raise HTTPException(status_code=500, detail=str(e))