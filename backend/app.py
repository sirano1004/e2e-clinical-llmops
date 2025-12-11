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

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# --- Project Imports ---
from .core.config import settings
from .core.logger import logger, session_context
from .core.redis_client import redis_client
# Services
from .services.llm_handler import llm_service
# Routers (Import the new routers)
from .routers import ingest, session, documents, feedback

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

# --- Register Routers ---
app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(session.router, tags=["Session"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(feedback.router, tags=["Feedback"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "model": settings.vllm_model_name}
