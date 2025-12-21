import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Retrieve Redis URL from environment variables
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery application
# 'backend.worker' is the module where tasks are defined (important for auto-discovery)
celery_app = Celery(
    "clinical_scribe",
    broker=redis_url,
    backend=redis_url,
    include=["backend.worker"]  # Explicitly tell Celery where to find @task decorators
)

# Configure Celery settings for ML/AI Heavy Workloads
celery_app.conf.update(
    # 1. Serialization (Security)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # 2. Timezone (Australia/Sydney)
    timezone="Australia/Sydney",
    enable_utc=True,
    
    # 3. Memory & Result Management
    # Delete results from Redis after 24 hours (86400s) to save memory
    result_expires=86400,
    
    # 4. Reliability (Data Safety)
    # Acknowledge the task ONLY after the function returns successfully.
    # If the worker crashes mid-task, the task is re-queued for another worker.
    task_acks_late=True,
    
    # Retry connecting to Redis on startup if it's not ready
    broker_connection_retry_on_startup=True,
    
    # 5. Visibility Timeout
    broker_transport_options={
        "visibility_timeout": 90
    },
    
    # 6. Performance & Distribution (Optimized for Heavy AI Tasks)
    # Prefetch=1: Worker takes only 1 task at a time.
    # Prevents one worker from hogging tasks while others are idle.
    worker_prefetch_multiplier=1,
    
    # 7. Monitoring
    # Report "STARTED" state so frontend knows the task is processing, not just pending.
    task_track_started=True,
    
    # 8. Safety Limits (Zombie Killer)
    # Hard limit
    task_time_limit=70,
    # Soft limit
    task_soft_time_limit=60,
)

if __name__ == "__main__":
    celery_app.start()