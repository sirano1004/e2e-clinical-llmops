from fastapi import APIRouter, HTTPException

# --- Project Imports ---
from ..core.logger import logger
# Services
from ..services.llm_handler import llm_service
# Repositories
from ..repositories.conversation import conversation_service
from ..repositories.documents import document_service
# Schemas
from ..schemas import (
    ScribeRequest, 
    ScribeResponse
)

router = APIRouter()

@router.post("/generate_document", response_model=ScribeResponse)
async def generate_derived_document(
    request: ScribeRequest
):
    """
    Generates derived documents (Referral, Certificate) based on the FINAL SOAP note.
    Does NOT update the SOAP note state in Redis.
    """
    logger.info(f"📄 Generating {request.task_type} for session {request.session_id}")
    
    try:
        # 1. Fetch Full Context
        # We need the full history and the finalized SOAP note
        history = await conversation_service.get_dialogue_history(request.session_id)
        current_soap = await document_service.get_soap_note(request.session_id)
        
        if not current_soap:
            raise HTTPException(status_code=400, detail="No SOAP note found. Complete consultation first.")
            
        # 2. Update Request Context
        request.dialogue_history = history
        request.existing_notes = current_soap # Used as reference context
        
        # 3. Generate (LLM)
        response = await llm_service.generate_scribe(request)
        
        # 4. Save Draft to Redis (Text Draft)
        # We save this so we can retrieve it later as 'original_output' for feedback
        if isinstance(response.generated_summary, str):
            await document_service.save_text_draft(
                request.session_id, 
                request.task_type, 
                response.generated_summary
            )
            
        return response

    except Exception as e:
        logger.exception(f"❌ Error generating {request.task_type}")
        raise HTTPException(status_code=500, detail=str(e))
    