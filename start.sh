#!/bin/bash
# Railway entrypoint - routes to web server or Celery worker
# based on SERVICE_TYPE env var (set per-service in Railway dashboard)

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "🔧 Starting Celery worker..."
    exec celery -A voice.tasks.celery_app worker --loglevel=info --concurrency=2
elif [ "$SERVICE_TYPE" = "livekit-agent" ]; then
    echo "🎙️ Starting LiveKit Voice Agent..."
    exec python -m voice.livekit_agent start
else
    echo "🌐 Starting web server..."
    exec uvicorn voice.service.api:app --host 0.0.0.0 --port ${PORT:-8080}
fi
