#!/bin/bash
# Voice Ledger IVR System Startup Script
# Starts API, Celery worker, and ngrok tunnel

echo "🚀 Starting Voice Ledger IVR System..."
echo ""

# Check if ngrok is authenticated
if ! ngrok config check 2>/dev/null; then
    echo "❌ ngrok not configured!"
    echo "Please run: ngrok config add-authtoken YOUR_TOKEN"
    echo "Get token from: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Start Redis (if not running)
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis not running. Start it with: brew services start redis"
fi

echo "1️⃣  Starting API server on port 8000..."
pkill -f "uvicorn voice.service.api" 2>/dev/null || true
nohup python -m uvicorn voice.service.api:app --host 0.0.0.0 --port 8000 > voice_api.log 2>&1 &
sleep 3

echo "2️⃣  Starting Celery worker..."
pkill -f "celery.*voice.tasks" 2>/dev/null || true
nohup celery -A voice.tasks.celery_app worker --loglevel=info > celery_worker.log 2>&1 &
sleep 2

echo "3️⃣  Starting ngrok tunnel..."
pkill ngrok 2>/dev/null || true
nohup ngrok http 8000 --log=stdout > ngrok.log 2>&1 &
sleep 3

# Extract ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*' | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Failed to get ngrok URL. Check ngrok.log"
    exit 1
fi

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service Status:"
echo "   API:    http://localhost:8000"
echo "   ngrok:  $NGROK_URL"
echo "   Dashboard: http://localhost:4040"
echo ""
echo "🔗 Update your .env file:"
echo "   NGROK_URL=$NGROK_URL"
echo ""
echo "📱 Configure Twilio webhook (when phone number ready):"
echo "   $NGROK_URL/voice/ivr/incoming"
echo ""
echo "📝 Logs:"
echo "   API:    tail -f voice_api.log"
echo "   Celery: tail -f celery_worker.log"
echo "   ngrok:  tail -f ngrok.log"
echo ""
