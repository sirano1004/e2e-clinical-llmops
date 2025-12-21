import sys
import os
from celery.signals import worker_process_init, worker_ready
from .core.logger import logger
from .core.celery_app import celery_app

# 1. Wrap services in try-except for Import (Fail Fast)
# If errors occur during model loading (GPU OOM, missing keys), terminate worker immediately.
try:
    logger.info("⏳ [Worker] Importing Tasks & Services...")
    
    # Tasks
    from .tasks.ingest import process_audio_chunk
    from .tasks.documents import generate_document_task

    # Services (Singleton instantiation + model loading happens here)
    from .services.transcriber import transcriber_service
    from .services.role_service import role_service
    from .services.llm_handler import llm_service
    from .services.pii_handler import pii_service
    from .services.guardrail_service import guardrail_service
    from .services.safety import safety_service

    logger.info("✅ [Worker] All modules imported successfully.")

except ImportError as e:
    logger.critical(f"❌ [Worker] Import Failed: {e}")
    sys.exit(1) # Terminate worker immediately on error (induce restart)
except Exception as e:
    logger.critical(f"❌ [Worker] Model Loading Failed (OOM?): {e}")
    sys.exit(1)


# 2. Worker Initialization Signal (Sanity Check)
# Runs exactly once when worker process starts.
# Performs 'inspection' to ensure objects are created properly, even without warm_up function.
@worker_process_init.connect
def check_services_health(**kwargs):
    logger.info("🏥 [Worker] Performing Health Checks...")

    # Check that required services are not None
    required_services = {
        "LLM Service": llm_service,
        "Transcriber": transcriber_service,
        "PII Handler": pii_service,
        "Safety Service": safety_service,
        "Role Service": role_service,
        "Guardrail Service": guardrail_service
    }

    failed = []
    for name, service in required_services.items():
        if service is None:
            failed.append(name)
        else:
            # If service has a model attribute, check if it's None
            if hasattr(service, 'model') and service.model is None:
                failed.append(f"{name} (Model is None)")

    if failed:
        logger.critical(f"❌ [Worker] Health Check Failed for: {', '.join(failed)}")
        sys.exit(1)
    
    logger.info(f"✅ [Worker] Health Check Passed. GPU Memory Active.")


# 3. Worker Ready Signal
# When all preparation is complete and connected to Celery queue
@worker_ready.connect
def on_worker_ready(**kwargs):
    logger.info("""
    🚀 ===================================================
    🚀  Worker is READY and LISTENING for tasks
    🚀  - Mode: Thread Pool (Shared Memory)
    🚀  - GPU: Active (LLM + Whisper)
    🚀 ===================================================
    """)