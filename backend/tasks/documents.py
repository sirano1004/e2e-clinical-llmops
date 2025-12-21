import os
import time
from celery import Task
# Exception Imports
from celery.exceptions import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from requests.exceptions import RequestException
# --- Project Imports ---
from ..core.celery_app import celery_app
from ..core.decorators import async_worker_task
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

RETRYABLE_ERRORS = (
    RedisConnectionError, 
    RedisTimeoutError, 
    RequestException, 
    ConnectionError, 
    TimeoutError
)

@celery_app.task(bind=True, max_retries=2)
@async_worker_task
async def generate_document_task(self, session_id: str, task_type: str):
    """
    [GPU Task] Generate documents (Referral/Certificate)
    """

    try:
        logger.info(f"📄 [Task] Generating {task_type} for session {session_id}")
        
        # 1. Fetch Data
        history = await conversation_service.get_dialogue_history(session_id)
        current_soap = await document_service.get_soap_note(session_id)
        
        if not current_soap:
            return {"status": "failed", "error": "No SOAP note found"}
            
        # 2. Prepare Request
        request = ScribeRequest(
            session_id=session_id,
            dialogue_history=history,
            existing_notes=current_soap,
            task_type=task_type
        )
        
        # 3. GPU Inference
        response = await llm_service.generate_scribe(request)
        
        # 4. Save Draft
        if isinstance(response.generated_summary, str):
            await document_service.save_text_draft(
                request.session_id, 
                request.task_type, 
                response.generated_summary
            )
            
        return {
            "status": "success",
            "task_type": task_type,
            "data": response.generated_summary
        }

    except Retry:
        raise
    
    except Exception as e:
        current_retry = self.request.retries
        max_retries = self.max_retries

        if current_retry < max_retries and isinstance(e, RETRYABLE_ERRORS):
            logger.warning(f"🔄 [Task] Transient error in doc gen. Retrying... ({current_retry + 1}/{max_retries})")
            raise self.retry(exc=e, countdown=3)
        
        logger.exception(f"❌ Error generating {task_type} for session {session_id}: {e}")
        return {"status": "failed", "error": str(e)}
