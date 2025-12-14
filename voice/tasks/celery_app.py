"""
Celery Application Configuration

Sets up Celery task queue with Redis broker for async voice processing.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Celery app configuration
app = Celery(
    'voice_ledger_tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['voice.tasks.voice_tasks']
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store task args, kwargs, result
    
    # Task execution settings
    task_track_started=True,  # Track when task starts
    task_time_limit=300,  # 5 minute hard timeout
    task_soft_time_limit=240,  # 4 minute soft timeout (raises exception)
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time (ASR is slow)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
    
    # Retry settings
    task_acks_late=True,  # Only ack after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
)

# Optional: Task routes (for future scaling with dedicated workers)
app.conf.task_routes = {
    'voice.tasks.voice_tasks.process_voice_command_task': {'queue': 'voice_processing'},
}

if __name__ == '__main__':
    app.start()
