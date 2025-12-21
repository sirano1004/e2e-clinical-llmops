
import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

# --- Project Imports ---
from ..repositories.conversation import conversation_service
from ..core.logger import logger
from ..worker import process_audio_chunk

router = APIRouter()

UPLOAD_DIR = "temp_audio_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/ingest_chunk", status_code=status.HTTP_202_ACCEPTED)
async def ingest_audio_chunk(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    is_last_chunk: bool = Form(False)
):
    """
    Receives an audio chunk (30s-1m), processes it, and updates the SOAP note.
    Flow: Transcribe -> Role Tag -> PII Mask -> Guardrail (Async) -> LLM Update.
    """
    logger.info(f"🎤 Received audio chunk for session: {session_id}")

    # 1. Save Temp File
    # Whisper requires a file path on disk
    filename = f"{session_id}_{int(time.time())}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)    
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Get Chunk Index (Atomic Counter from Redis)
        # Required for data lineage (SOAPItem tracking)
        chunk_index = await conversation_service.get_next_chunk_index(session_id)
        logger.info(f"🎫 [Ingest] Assigned Ticket #{chunk_index} to Session {session_id}")

        # 3. Celery Task
        process_audio_chunk.delay(
            file_path=file_path,
            session_id=session_id,
            chunk_index=chunk_index,
            is_last_chunk=is_last_chunk
        )

        # 4. Immediate Response
        return {
            "status": "queued",
            "session_id": session_id,
            "chunk_index": chunk_index,
            "message": "Successfully sent to worker"
        }

    except Exception as e:
        logger.exception("❌ Error in ingest_chunk pipeline")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))   