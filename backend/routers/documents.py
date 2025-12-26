from fastapi import APIRouter, HTTPException, status, Depends
from celery.result import AsyncResult
# --- Project Imports ---
from ..core.celery_app import celery_app
from ..core.logger import logger
from ..core.redis_client import redis_client
from ..repositories.conversation import ConversationRepositoryAsync
from ..repositories.documents import DocumentServiceAsync

router = APIRouter()

def get_document_service() -> DocumentServiceAsync:
    return DocumentServiceAsync(redis_client)
def get_conversation_service() -> ConversationRepositoryAsync:
    return ConversationRepositoryAsync(redis_client)

@router.post("/generate_document", status_code=status.HTTP_202_ACCEPTED)
async def generate_derived_document(
    session_id: str,
    task_type: str,
    conversation_service: ConversationRepositoryAsync = Depends(get_conversation_service),
    document_service: DocumentServiceAsync = Depends(get_document_service)
):
    """
    Generates derived documents (Referral, Certificate) based on the FINAL SOAP note.
    Does NOT update the SOAP note state in Redis.
    """
    logger.info(f"📄 Generating {task_type} for session {session_id}")
    
    try:
        # Update Request Context

        # 1. Fetch Data
        history = await conversation_service.get_dialogue_history(session_id)
        current_soap = await document_service.get_soap_note(session_id)

        # 2. Celery Task
        task = celery_app.send_task(
            "generate_document_task", # task 이름 (worker @task 데코레이터의 name과 일치해야 함)
            kwargs={
                "session_id": session_id,
                "task_type": task_type,
                "history": history,
                "current_soap": current_soap.model_dump_json()
            }
        )

        return {
                "status": "queued",
                "task_id": task.id,
                "message": f"Generating {task_type} started..."
            }

    except Exception as e:
        logger.exception(f"❌ Error generating {task_type}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    
    # 1. When Celery is still processing or pending
    # STARTED may not appear if not configured, but safe to include
    if task_result.state in ['PENDING', 'STARTED', 'RETRY']:
        return {"status": "processing"}
        
    # 2. When Celery reports task completion (success)
    elif task_result.state == 'SUCCESS':
        # Open the box
        output = task_result.result 
        
        # [Important] Check if the result content indicates failure
        # Catches cases where worker returned {"status": "failed"}
        if isinstance(output, dict) and output.get("status") == "failed":
             return {
                 "status": "failed",
                 "error": output.get("error", "Unknown logic error")
             }
        
        # True success
        return {
            "status": "completed",
            "result": output # {"status": "success", "data": ...}
        }
        
    # 3. When Celery task itself failed (e.g., OOM, code exceptions)
    elif task_result.state == 'FAILURE':
        return {"status": "failed", "error": str(task_result.info)}
    
    return {"status": "processing"} # Treat other states as processing