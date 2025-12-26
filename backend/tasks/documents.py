import os
import time
from celery import Task
# Exception Imports
from celery.exceptions import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from requests.exceptions import RequestException
from pydantic import ValidationError
# --- Project Imports ---
from ..core.celery_app import celery_app
from ..core.decorators import async_worker_task
from ..core.logger import logger
from ..core.redis_client_sync import redis_client
from ..core.async_runtime import run_async
# Services
from ..services.llm_handler import llm_service
# Repositories
from ..repositories.documents import DocumentServiceSync
from ..repositories.metrics import MetricsServiceSync
# Schemas
from ..schemas import (
    ScribeRequest, 
    SOAPNote
)

RETRYABLE_ERRORS = (
    RedisConnectionError, 
    RedisTimeoutError, 
    RequestException, 
    ConnectionError, 
    TimeoutError
)

@celery_app.task(bind=True, max_retries=2, name="generate_document_task")
def generate_document_task(self, session_id: str, task_type: str, history: list, current_soap: str):
    """
    [GPU Task] Generate documents (Referral/Certificate)
    """
    metrics_service = MetricsServiceSync(redis_client)
    document_service = DocumentServiceSync(redis_client)

    try:
        current_soap = SOAPNote.model_validate_json(current_soap)
    except (ValidationError, TypeError):
        current_soap = SOAPNote()
    try:
        logger.info(f"📄 [Task] Generating {task_type} for session {session_id}")
        
        if not current_soap:
            return {"status": "failed", "error": "No SOAP note found"}
            
        # 1. Prepare Request
        request = ScribeRequest(
            session_id=session_id,
            dialogue_history=history,
            existing_notes=current_soap,
            task_type=task_type
        )
        
        # 2. GPU Inference
        response = run_async(llm_service.generate_scribe(request))
        
        # 3. Save Duration Metric
        metrics_service.update_metrics(request.session_id, response.duration, 'total_latency_ms')

        # 4. Save Draft
        if isinstance(response.generated_summary, str):
            document_service.save_text_draft(
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
