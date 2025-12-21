from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult
# --- Project Imports ---
from ..tasks.documents import generate_document_task
from ..core.celery_app import celery_app
from ..core.logger import logger


router = APIRouter()

@router.post("/generate_document", status_code=status.HTTP_202_ACCEPTED)
async def generate_derived_document(
    session_id: str,
    task_type: str
):
    """
    Generates derived documents (Referral, Certificate) based on the FINAL SOAP note.
    Does NOT update the SOAP note state in Redis.
    """
    logger.info(f"📄 Generating {task_type} for session {session_id}")
    
    try:
        # Update Request Context
        
        task = celery_app.send_task(
            "generate_document_task", # task 이름 (worker @task 데코레이터의 name과 일치해야 함)
            kwargs={
                "session_id": session_id,
                "task_type": task_type,
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