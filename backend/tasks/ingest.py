import os
import time
import json
from celery import Task
from ..core.celery_app import celery_app
# Exception Imports
from celery.exceptions import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from requests.exceptions import RequestException
from pydantic import ValidationError
# Services
from ..services.transcriber import transcriber_service
from ..services.role_service import role_service
from ..services.llm_handler import llm_service
from ..services.pii_handler import pii_service
from ..services.guardrail_service import guardrail_service
from ..services.safety import safety_service
# Repositories
from ..repositories.conversation import ConversationRepositorySync
from ..repositories.documents import DocumentServiceSync
from ..repositories.metrics import MetricsServiceSync
from ..repositories.notification import NotificationServiceSync
from ..repositories.buffer import BufferServiceSync
# Cores
from ..core.redis_client_sync import redis_client
from ..core.logger import logger
from ..core.async_runtime import run_async
# Schemas
from ..schemas import (
    ScribeRequest, 
    ScribeResponse, 
    SOAPNote
)

@celery_app.task(bind=True, max_retries=3, name="process_audio_chunk")
def process_audio_chunk(self: Task, file_path: str, session_id: str, chunk_index: int, is_last_chunk: bool, current_note: str):
    """
    Core Logic:
    1. Check if it is the turn of this chunk (Ordering).
    2. If not, retry later.
    3. If yes, run ASR and LLM.
    4. Save to DB and increment the index.
    """
    RETRYABLE_ERRORS = (
        RedisConnectionError, 
        RedisTimeoutError, 
        RequestException, 
        ConnectionError, 
        TimeoutError
    )

    r = redis_client.get_instance()

    conversation_service = ConversationRepositorySync(r)
    document_service = DocumentServiceSync(r)
    metrics_service = MetricsServiceSync(r)
    notification_service = NotificationServiceSync(r)
    buffer_service = BufferServiceSync(r)

    try:
        current_note = SOAPNote.model_validate_json(current_note)
    except (ValidationError, TypeError):
        current_note = SOAPNote()

    try:
        # ------------------------------------------------------
        # Ordering Logic (The "Ticket Number" System)
        # ------------------------------------------------------
        # Fetch the current ticket number (default to 0)
        current_expected_index = conversation_service.get_expected_chunk_index(session_id)
        # Measure how long the entire pipeline takes
        pipeline_start = time.time()

        logger.info(f"👀 [Task] Checking Order: My Index={chunk_index}, Expected={current_expected_index}")

        # Case 1: Too early (It's not my turn yet)
        if chunk_index > current_expected_index:
            logger.warning(f"✋ [Task] Wait! It is chunk {current_expected_index}'s turn. I am {chunk_index}. Retrying...")
            # Retry after 2 seconds. This pushes the task back to the queue.
            logger.info(f"🅿️ [Buffer] Chunk {chunk_index} stored. Waiting for {current_expected_index}.")
            
            payload = json.dumps({
                "file_path": file_path, 
                "session_id": session_id,
                "chunk_index": chunk_index,
                "is_last_chunk": is_last_chunk
            })
            buffer_service.save_chunk(session_id, chunk_index, json.loads(payload))
            return {"status": "buffered"} # 태스크 여기서 완전 종료!

        # Case 2: Duplicate/Old (Already processed)
        if chunk_index < current_expected_index:
            logger.warning(f"🗑️ [Task] Old chunk detected ({chunk_index} < {current_expected_index}). Skipping.")
            return {"status": "skipped", "reason": "already_processed"}

        # ------------------------------------------------------
        # Heavy Processing (ASR + LLM) - "Ingest Logic"
        # ------------------------------------------------------
        logger.info(f"🚀 [Task] Processing Chunk {chunk_index} for Session {session_id}...")
            
        # 1. Run Whisper (ASR)
        # Returns raw text with timestamps and assigns chunk_index to turns
        transcribe_result = transcriber_service._transcribe_audio(
            file_path, 
            chunk_index=chunk_index
        )
        raw_turns = transcribe_result["conversation"] # List[DialogueTurn] with TBD roles
        
        if not raw_turns:
            logger.warning("⚠️ No speech detected in chunk.")
            return ScribeResponse(
                session_id=session_id,
                interaction_id="empty",
                generated_summary=current_note or SOAPNote(),
                chunk_index=chunk_index
            )

        # 2. Role Assignment (Tagging)
        # Uses LLM to tag 'Doctor' or 'Patient' based on context
        tagged_turns = run_async(role_service.assign_roles(raw_turns))
        
        if "raw_segments" in transcribe_result:
            for i, turn in enumerate(tagged_turns):
                # Ensure we don't go out of bounds (they should be 1:1)
                if i < len(transcribe_result["raw_segments"]):
                    transcribe_result["raw_segments"][i].speaker = turn.role

        # 3. PII Masking
        # Mask sensitive data before storage or LLM processing
        safe_turns = pii_service._mask_dialogue(tagged_turns)
        
        # 6. Save to History (Redis)
        # Persist the dialogue state
        conversation_service.add_ui_segments(session_id, transcribe_result["raw_segments"])
        conversation_service.add_dialogue_turns(session_id, safe_turns)

        # 7. Run vLLM (Summary/Extraction)
        full_history = conversation_service.get_dialogue_history(session_id)
        
        # We use get_backup_soap_note inside llm_handler logic via ScribeRequest?
        # Actually, llm_handler expects us to pass the 'existing_notes'.
        # Since this is an update, we fetch the CURRENT state to pass as context.
        # Inside update_soap_note, it will be backed up automatically before overwrite.
        
        
        scribe_request = ScribeRequest(
            session_id=session_id,
            dialogue_history=full_history, # Full context for Prefix Caching
            existing_notes=current_note,   # Context for delta extraction
            chunk_index=chunk_index, # For ID generation
            task_type="soap" # Incremental Update Mode
        )
        
        # 8. Generate Update (LLM)
        # Returns a SOAPNote containing only NEW/UPDATED items (Delta)
        response = run_async(llm_service.generate_scribe(scribe_request))
        delta_note = response.generated_summary
        
        # 9. Merge & Update State
        if isinstance(delta_note, SOAPNote):
            # If it's the first note, initialize it
            if not current_note:
                new_state = delta_note
            else:
                # Merge Delta into Current
                # Note: We should probably create a new object to avoid mutation issues
                new_state = current_note.model_copy()
                new_state.merge(delta_note)
            
            # Commit to Redis (This triggers Backup logic internally)
            document_service.update_soap_note(session_id, new_state)
            
            # Update response with the FULL merged note for UI display
            response.generated_summary = new_state

        # 8. Run Safety Checks
        delta_dict = delta_note.model_dump() if isinstance(delta_note, SOAPNote) else {}

        warnings = guardrail_service.check_hallucination(session_id, safe_turns, delta_dict)

        if warnings:        
            notification_service.add_warning(session_id, warnings, chunk_index)
            logger.warning(f"⚠️ [Background] Chunk {chunk_index} Guardrail Warnings: {warnings}")

        # Dict -> String (Safety Service accepts text only)
        # only get plan field 
        if isinstance(delta_dict, dict):
            # assume element follows SOAPItem schema.
            summary_text = ', '.join([item.get('text', '') for item in delta_dict.get('plan', [])])
        else:
            summary_text = str(delta_dict)

        alerts = safety_service._detect_rule_violations(summary_text)
        
        if alerts:
            notification_service.add_safety_alert(session_id, alerts, chunk_index)
            logger.warning(f"⚠️ [Background] Chunk {chunk_index} Safety Alert: {alerts}")

        # 9. end of pipeline
        pipeline_duration = (time.time() - pipeline_start) * 1000 # ms
        
        if is_last_chunk:
            logger.info(f"🏁 Final Chunk Processed! Latency: {pipeline_duration:.2f}ms")    
            metrics_service.update_metrics(session_id, pipeline_duration, 'final_e2e_latency_ms')

        # 10. Clean up Temp File
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass  # Already cleaned up             

        # ------------------------------------------------------
        # Order Increment
        # ------------------------------------------------------
        # Increment the expected index so the next chunk can proceed
        next_chunk_index = conversation_service.increment_expected_chunk_index(session_id)
        logger.info(f"✅ [Task] Ticket number incremented. Next expected: {next_chunk_index}")

        # Check if there are buffered chunks waiting
        next_chunk_payload = buffer_service.get_chunk(session_id, next_chunk_index)
        if next_chunk_payload:
            logger.info(f"▶️ [Buffer] Found buffered chunk {next_chunk_index}. Re-queuing...")
            buffer_service.del_chunk(session_id, next_chunk_index)
            celery_app.send_task(
                "process_audio_chunk",
                kwargs={
                    "file_path": next_chunk_payload["file_path"],
                    "session_id": next_chunk_payload["session_id"],
                    "chunk_index": next_chunk_payload["chunk_index"],
                    "is_last_chunk": next_chunk_payload["is_last_chunk"]
                }
            )

        return {
            "status": "success",
            "session_id": session_id,
            "chunk_index": chunk_index
        }

    except Retry:
        # Retries raised by self.retry() should be propagated
        raise

    except Exception as e:
        logger.warning(f"⚠️ [Task] Error processing chunk {chunk_index}: {e}")
        
        current_retry_count = self.request.retries
        max_retries = self.max_retries or 2

        # ------------------------------------------------------
        # Case 1: When retries are still available (Retry)
        # ------------------------------------------------------
        if current_retry_count < max_retries and isinstance(e, RETRYABLE_ERRORS):
            logger.info(f"🔄 [Task] Transient error. Retrying... ({current_retry_count + 1}/{max_retries})")
            
            # [Core] Raise the retry.
            # This function stops here, and Celery will re-execute it after N seconds.
            # Importantly, do not delete the file here!
            raise self.retry(exc=e, countdown=5)

        # ------------------------------------------------------
        # Case 2: When all retries are exhausted (Max Retries Reached)
        # ------------------------------------------------------
        logger.error(f"💀 [Task] Max retries reached for Chunk {chunk_index}. Giving up.")

        # 1. Unblock the pipeline (call the next ticket number)
        conversation_service.increment_expected_chunk_index(session_id)
        
        # 2. Clean up the file (now it's really over, so it's okay to delete)
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass  # Already cleaned up             

        return {
            "status": "failed",
            "error": str(e),
            "chunk_index": chunk_index,
            "handled": True
        }