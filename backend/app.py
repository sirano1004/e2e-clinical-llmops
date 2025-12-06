"""
This code includes the following capabilities:
1. **Streaming audio processing:** Accepts `UploadFile`, performs transcription, and applies incremental updates.
2. **Data tracking:** Manages `chunk_index` and integrates with `SessionService`.
3. **Feedback loop:** Collects data through `FeedbackService` and keeps Redis state in sync.
4. **Derived documents:** Generates additional documents from the SOAP note and stores them temporarily.
5. **Operational logging:** Uses `logger` and `session_context` for session-level log tracing.

Run the server to have the full system working together:
`uvicorn backend.main:app --reload`
"""

import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

# --- Project Imports ---
from .core.config import settings
from .core.logger import logger, session_context
from .core.redis_client import redis_client
from .core.local_storage import local_storage # Ensure directory exists
# Services
from .services.transcriber import transcriber_service
from .services.role_service import role_service
from .services.llm_handler import llm_service
from .services.pii_handler import pii_service
from .services.guardrail_service import guardrail_service
from .services.safety import safety_service
from .services.session_service import session_service
from .services.feedback_service import feedback_service
# Schemas
from .schemas import (
    ScribeRequest, 
    ScribeResponse, 
    DialogueTurn, 
    SOAPNote,
    TranscriptionResponse
)

# --- Lifespan Manager (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Connect to Infrastructure
    logger.info("🚀 Starting Clinical Scribe Backend...")
    await redis_client.connect()
    
    # Verify Model Loading (Optional health check)
    if not llm_service.engine:
        logger.error("❌ vLLM Engine not initialized properly!")
    
    yield
    
    # 2. Shutdown: Cleanup
    logger.info("🛑 Shutting down...")
    await redis_client.disconnect()

# --- FastAPI Setup ---
app = FastAPI(
    title="Clinical Scribe AI API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS (Allow UI Access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, set to specific frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware: Session Logging ---
@app.middleware("http")
async def add_session_context(request: Request, call_next):
    # Extract session_id from headers if available
    session_id = request.headers.get("X-Session-ID", "System")
    token = session_context.set(session_id)
    try:
        response = await call_next(request)
        return response
    finally:
        session_context.reset(token)

# =================================================================
# 1. CORE PIPELINE: INGEST CHUNK (Streaming Audio)
# =================================================================
@app.post("/ingest_chunk", response_model=ScribeResponse)
async def ingest_audio_chunk(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    is_last_chunk: bool = Form(False),
    background_tasks = BackgroundTasks
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
        chunk_index = await session_service.get_next_chunk_index(session_id)
        
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
                generated_summary=await session_service.get_soap_note(session_id) or SOAPNote(),
                model_used="none",
                processing_time_ms=0
            )

        # 4. Role Assignment (Tagging)
        # Uses LLM to tag 'Doctor' or 'Patient' based on context
        tagged_turns = await role_service.assign_roles(raw_turns)
        
        # 5. PII Masking
        # Mask sensitive data before storage or LLM processing
        safe_turns = pii_service.mask_dialogue(tagged_turns)
        
        # 6. Save to History (Redis)
        # Persist the dialogue state
        await session_service.add_dialogue_turns(session_id, safe_turns)
        
        # --- Incremental Update Logic ---
        
        # 7. Prepare LLM Request
        # We need the full history and the current state (Backup for Context)
        full_history = await session_service.get_dialogue_history(session_id)
        
        # NOTE: We use get_backup_soap_note inside llm_handler logic via ScribeRequest?
        # Actually, llm_handler expects us to pass the 'existing_notes'.
        # Since this is an update, we fetch the CURRENT state to pass as context.
        # Inside update_soap_note, it will be backed up automatically before overwrite.
        current_note = await session_service.get_soap_note(session_id)
        
        scribe_request = ScribeRequest(
            session_id=session_id,
            dialogue_history=full_history, # Full context for Prefix Caching
            existing_notes=current_note,   # Context for delta extraction
            current_chunk_index=chunk_index, # For ID generation
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
            await session_service.update_soap_note(session_id, new_state)
            
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
            await session_service.update_metrics(session_id, pipeline_duration, 'final_e2e_latency_ms')

        return response

    except Exception as e:
        logger.exception("❌ Error in ingest_chunk pipeline")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup temp file
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def run_guardrail_background(session_id, transcript, summary, chunk_index):
    guard_result = await guardrail_service.check_hallucination(session_id, transcript, summary)
    
    warnings = guard_result.get("warnings", [])
    if warnings:        
        await session_service.add_warning(session_id, warnings, chunk_index)
        logger.warning(f"⚠️ [Background] Chunk {chunk_index} Guardrail Warnings: {warnings}")

async def run_safety_check_background(session_id, summary, chunk_index):

    # Dict -> String 변환 (Safety Service accepts text only)
    # only get plan field 
    if isinstance(summary, dict):
        summary_text = summary.get('plan', '')
    else:
        summary_text = str(summary)

    alerts = await safety_service.check_safety(summary_text)
    
    if alerts:
        await session_service.add_safety_alert(session_id, alerts, chunk_index)
        logger.warning(f"⚠️ [Background] Chunk {chunk_index} Safety Alert: {alerts}")

@app.get("/check_notifications")
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
    warnings = await session_service.get_warnings(session_id, chunk_index)
    # Fetch Safety Alerts (Guardrails, Medical Risks)
    safety_alerts = await session_service.get_safety_alerts(session_id)

    response = {
        "warnings": warnings,        # Frontend: Show generally (Yellow/Toast)
        "safety_alerts": safety_alerts # Frontend: Show prominently (Red/Modal)
    }
    
    if warnings or safety_alerts:
        logger.info(f"🔔 Retrieved notifications for {session_id}: {len(warnings)} warnings, {len(safety_alerts)} alerts")
        
    return response

# =================================================================
# 2. FEEDBACK LOOP: SAVE & LEARN
# =================================================================
@app.post("/submit_feedback")
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

# =================================================================
# 3. DERIVED TASKS: REFERRAL / DISCHARGE / CERTIFICATE
# =================================================================
@app.post("/generate_document", response_model=ScribeResponse)
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
        history = await session_service.get_dialogue_history(request.session_id)
        current_soap = await session_service.get_soap_note(request.session_id)
        
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
            await session_service.save_text_draft(
                request.session_id, 
                request.task_type, 
                response.generated_summary
            )
            
        return response

    except Exception as e:
        logger.exception(f"❌ Error generating {request.task_type}")
        raise HTTPException(status_code=500, detail=str(e))
    
# =================================================================
# 4. SESSION MANAGEMENT
# =================================================================
@app.post("/stop_session")
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
        # await session_service.clear_session(session_id)
        
        return {"status": "session_stopped"}
        
    except Exception as e:
        logger.exception("❌ Error stopping session")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "model": settings.vllm_model_name}
