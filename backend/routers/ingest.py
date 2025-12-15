
import os
import shutil
import tempfile
import time

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks

# --- Project Imports ---
# Services
from ..services.transcriber import transcriber_service
from ..services.role_service import role_service
from ..services.llm_handler import llm_service
from ..services.pii_handler import pii_service
from ..services.guardrail_service import guardrail_service
from ..services.safety import safety_service
# Repositories
from ..repositories.conversation import conversation_service
from ..repositories.documents import document_service
from ..repositories.metrics import metrics_service
from ..repositories.notification import notification_service
# Cores
from ..core.logger import logger
# Schemas
from ..schemas import (
    ScribeRequest, 
    ScribeResponse, 
    SOAPNote
)

router = APIRouter()

@router.post("/ingest_chunk", response_model=ScribeResponse)
async def ingest_audio_chunk(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    file: UploadFile = File(...),
    is_last_chunk: bool = Form(False)
):
    """
    Receives an audio chunk (30s-1m), processes it, and updates the SOAP note.
    Flow: Transcribe -> Role Tag -> PII Mask -> Guardrail (Async) -> LLM Update.
    """
    logger.info(f"🎤 Received audio chunk for session: {session_id}")
    
    # timer start
    pipeline_start = time.time()

    # 1. Save Temp File
    # Whisper requires a file path on disk
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{session_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Get Chunk Index (Atomic Counter from Redis)
        # Required for data lineage (SOAPItem tracking)
        chunk_index = await conversation_service.get_next_chunk_index(session_id)
        
        # 3. Transcribe (ASR)
        # Returns raw text with timestamps and assigns chunk_index to turns
        transcribe_result = transcriber_service.transcribe_audio(
            file_path, 
            chunk_index=chunk_index
        )
        raw_turns = transcribe_result["conversation"] # List[DialogueTurn] with TBD roles
        
        if not raw_turns:
            logger.warning("⚠️ No speech detected in chunk.")
            return ScribeResponse(
                session_id=session_id,
                interaction_id="empty",
                generated_summary=await document_service.get_soap_note(session_id) or SOAPNote(),
                chunk_index=chunk_index
            )

        # 4. Role Assignment (Tagging)
        # Uses LLM to tag 'Doctor' or 'Patient' based on context
        tagged_turns = await role_service.assign_roles(raw_turns)
        
        if "raw_segments" in transcribe_result:
            for i, turn in enumerate(tagged_turns):
                # Ensure we don't go out of bounds (they should be 1:1)
                if i < len(transcribe_result["raw_segments"]):
                    transcribe_result["raw_segments"][i].speaker = turn.role

        # 5. PII Masking
        # Mask sensitive data before storage or LLM processing
        safe_turns = pii_service.mask_dialogue(tagged_turns)
        
        # 6. Save to History (Redis)
        # Persist the dialogue state
        await conversation_service.add_ui_segments(session_id, transcribe_result["raw_segments"])
        await conversation_service.add_dialogue_turns(session_id, safe_turns)
        
        # --- Incremental Update Logic ---
        
        # 7. Prepare LLM Request
        # We need the full history and the current state (Backup for Context)
        full_history = await conversation_service.get_dialogue_history(session_id)
        
        # NOTE: We use get_backup_soap_note inside llm_handler logic via ScribeRequest?
        # Actually, llm_handler expects us to pass the 'existing_notes'.
        # Since this is an update, we fetch the CURRENT state to pass as context.
        # Inside update_soap_note, it will be backed up automatically before overwrite.
        current_note = await document_service.get_soap_note(session_id)
        
        scribe_request = ScribeRequest(
            session_id=session_id,
            dialogue_history=full_history, # Full context for Prefix Caching
            existing_notes=current_note,   # Context for delta extraction
            chunk_index=chunk_index, # For ID generation
            task_type="soap" # Incremental Update Mode
        )
        
        # 8. Generate Update (LLM)
        # Returns a SOAPNote containing only NEW/UPDATED items (Delta)
        response = await llm_service.generate_scribe(scribe_request)
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
            await document_service.update_soap_note(session_id, new_state)
            
            # Update response with the FULL merged note for UI display
            response.generated_summary = new_state
            
        # 10. Run Guardrails (Safety Check) - (Background)
        # We check the NEW chunk against the NEW delta to find hallucinations.
        # Since this is CPU bound, we assume guardrail_service handles run_in_executor.
        # We convert delta_note to dict for the check.
        delta_dict = delta_note.model_dump() if isinstance(delta_note, SOAPNote) else {}
        
        background_tasks.add_task(
            run_guardrail_background, 
            session_id, 
            safe_turns, 
            delta_dict,
            chunk_index 
        )
        
        background_tasks.add_task(
            run_safety_check_background,
            session_id,
            delta_dict,
            chunk_index
        )
        # 11. end of pipeline
        pipeline_duration = (time.time() - pipeline_start) * 1000 # ms
        
        if is_last_chunk:
            logger.info(f"🏁 Final Chunk Processed! Latency: {pipeline_duration:.2f}ms")    
            await metrics_service.update_metrics(session_id, pipeline_duration, 'final_e2e_latency_ms')

        return response

    except Exception as e:
        logger.exception("❌ Error in ingest_chunk pipeline")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup temp file
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def run_guardrail_background(session_id, transcript, summary, chunk_index):
    warnings = await guardrail_service.check_hallucination(session_id, transcript, summary)
    
    if warnings:        
        await notification_service.add_warning(session_id, warnings, chunk_index)
        logger.warning(f"⚠️ [Background] Chunk {chunk_index} Guardrail Warnings: {warnings}")

async def run_safety_check_background(session_id, summary, chunk_index):

    # Dict -> String (Safety Service accepts text only)
    # only get plan field 
    if isinstance(summary, dict):
        # assume element follows SOAPItem schema.
        summary_text = ', '.join([item.get('text', '') for item in summary.get('plan', [])])
    else:
        summary_text = str(summary)

    alerts = await safety_service.check_safety(summary_text)
    
    if alerts:
        await notification_service.add_safety_alert(session_id, alerts, chunk_index)
        logger.warning(f"⚠️ [Background] Chunk {chunk_index} Safety Alert: {alerts}")
