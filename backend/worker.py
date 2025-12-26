import sys
import os
from celery.signals import worker_process_init, worker_ready
from .core.logger import logger
from .core.celery_app import celery_app
from .core.async_runtime import start_background_loop
from .core.redis_client_sync import redis_client
# 1. Wrap services in try-except for Import (Fail Fast)
# If errors occur during model loading (GPU OOM, missing keys), terminate worker immediately.
try:
    logger.info("⏳ [Worker] Importing Tasks & Services...")
    
    # Tasks
    from .tasks.ingest import process_audio_chunk
    from .tasks.documents import generate_document_task

    logger.info("✅ [Worker] All tasks imported successfully.")

except ImportError as e:
    logger.critical(f"❌ [Worker] Import Failed: {e}")
    sys.exit(1) # Terminate worker immediately on error (induce restart)
except Exception as e:
    logger.critical(f"❌ [Worker] Model Loading Failed (OOM?): {e}")
    sys.exit(1)

# 2. Worker Ready Signal
# When all preparation is complete and connected to Celery queue
@worker_ready.connect
def on_worker_ready(**kwargs):
    logger.info("🔧 [Worker] Initializing Services...")
    start_background_loop()  # Ensure async runtime is started
    redis_client.connect()  # Ensure Redis connection is established

    logger.info("""
    🚀 ===================================================
    🚀  Worker is READY and LISTENING for tasks
    🚀  - Mode: Thread Pool (Shared Memory)
    🚀  - GPU: Active (LLM + Whisper)
    🚀 ===================================================
    """)