"""
Voice Ledger Voice Interface API Service

This FastAPI service provides voice input capability for Voice Ledger through:
- Audio transcription (ASR) using OpenAI Whisper
- Intent/entity extraction (NLU) using GPT-3.5
- Full voice command processing with database integration

Endpoints:
- POST /voice/transcribe - Transcribe audio to text
- POST /voice/process-command - Full voice command workflow (ASR + NLU + DB)
- POST /asr-nlu - Legacy endpoint (backward compatibility)
- GET /voice/health - Health check with service status
- GET / - Root health check
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path for database imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from voice.asr.asr_infer import run_asr
from voice.nlu.nlu_infer import infer_nlu_json
from voice.service.auth import verify_api_key
from voice.audio_utils import (
    validate_and_convert_audio,
    cleanup_temp_file,
    AudioValidationError,
    get_audio_metadata
)

# Import database and voice command integration
try:
    from database.connection import get_db
    from voice.command_integration import execute_voice_command, VoiceCommandError
    DATABASE_AVAILABLE = True
except ImportError as e:
    DATABASE_AVAILABLE = False
    print(f"⚠️  Database module not available - /voice/process-command will be disabled: {e}")

# Import IVR router (optional - only if Phase 3 is set up)
try:
    from voice.ivr.ivr_api import router as ivr_router
    IVR_AVAILABLE = True
except ImportError as e:
    IVR_AVAILABLE = False
    print(f"ℹ️  IVR module not available - Phase 3 endpoints disabled: {e}")

# Import Telegram router (optional - Phase 4 multi-channel)
try:
    from voice.telegram.telegram_api import router as telegram_router
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    TELEGRAM_AVAILABLE = False
    print(f"ℹ️  Telegram module not available - Phase 4 endpoints disabled: {e}")

# Import Verification router (Phase 5 - public credential verification)
try:
    from voice.verification.verify_api import router as verification_router
    VERIFICATION_AVAILABLE = True
except ImportError as e:
    VERIFICATION_AVAILABLE = False
    print(f"ℹ️  Verification module not available - Phase 5 endpoints disabled: {e}")

app = FastAPI(
    title="Voice Ledger Voice Interface API",
    description="Voice input capability for supply chain traceability",
    version="2.0.0"
)

# Include IVR router if available (Phase 3)
if IVR_AVAILABLE:
    app.include_router(ivr_router)
    print("✅ IVR endpoints registered at /voice/ivr/*")

# Include Telegram router if available (Phase 4)
if TELEGRAM_AVAILABLE:
    app.include_router(telegram_router)
    print("✅ Telegram endpoints registered at /voice/telegram/*")

# Include Verification router if available (Phase 5)
if VERIFICATION_AVAILABLE:
    app.include_router(verification_router)
    print("✅ Verification endpoints registered at /voice/verify/*")

# Allow local tools and UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class TranscriptionResponse(BaseModel):
    """Response for transcription-only endpoint."""
    transcript: str
    audio_metadata: dict
    

class NLUResponse(BaseModel):
    """Response for ASR+NLU endpoint."""
    transcript: str
    intent: str
    entities: dict
    audio_metadata: Optional[dict] = None


class CommandResponse(BaseModel):
    """Response for full command processing."""
    transcript: str
    intent: str
    entities: dict
    result: Optional[dict] = None
    error: Optional[str] = None
    audio_metadata: dict


class HealthResponse(BaseModel):
    """Health check response."""
    service: str
    status: str
    version: str
    openai_api_configured: bool
    database_available: bool
    ffmpeg_available: bool


@app.get("/", response_model=dict)
async def root():
    """Root health check endpoint."""
    return {
        "service": "Voice Ledger Voice Interface API",
        "status": "operational",
        "version": "2.1.0",
        "endpoints": [
            "GET /voice/health",
            "POST /voice/transcribe",
            "POST /voice/process-command (sync)",
            "POST /voice/upload-async (Phase 2)",
            "GET /voice/status/{task_id} (Phase 2)",
            "POST /asr-nlu (legacy)"
        ]
    }


@app.get("/voice/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Checks:
    - OpenAI API key configuration
    - Database availability
    - FFmpeg availability for audio conversion
    
    Returns:
        Health status with component availability
    """
    import shutil
    
    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    ffmpeg_installed = shutil.which("ffmpeg") is not None
    
    return {
        "service": "Voice Ledger Voice Interface API",
        "status": "operational",
        "version": "2.0.0",
        "openai_api_configured": openai_configured,
        "database_available": DATABASE_AVAILABLE,
        "ffmpeg_available": ffmpeg_installed
    }


@app.post("/voice/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Transcribe audio file to text using OpenAI Whisper.
    
    This endpoint only performs transcription (ASR), no intent extraction.
    Use this when you just need the text transcript.
    
    Args:
        file: Audio file (WAV, MP3, M4A, AAC, FLAC, OGG, WMA)
        
    Returns:
        {
            "transcript": str,
            "audio_metadata": {
                "duration_seconds": float,
                "sample_rate": int,
                "channels": int,
                "format": str,
                "file_size_mb": float
            }
        }
        
    Requires:
        X-API-Key header with valid API key
        
    Example:
        curl -X POST "http://localhost:8000/voice/transcribe" \\
             -H "X-API-Key: your-api-key" \\
             -F "file=@voice_command.mp3"
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Create temp directory for uploads
    temp_dir = Path("tests/samples/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename
    wav_path = None

    try:
        # Save uploaded file
        content = await file.read()
        with temp_path.open("wb") as f:
            f.write(content)

        # Validate and convert to WAV
        wav_path, metadata = validate_and_convert_audio(str(temp_path))
        
        # Run ASR (audio → text)
        transcript = run_asr(wav_path)
        
        return {
            "transcript": transcript,
            "audio_metadata": metadata
        }
        
    except AudioValidationError as e:
        raise HTTPException(status_code=400, detail=f"Audio validation failed: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temp files
        cleanup_temp_file(str(temp_path))
        if wav_path and wav_path != str(temp_path):
            cleanup_temp_file(wav_path)


@app.post("/voice/process-command", response_model=CommandResponse)
async def process_voice_command(
    file: UploadFile = File(...),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Full voice command processing pipeline:
    1. Transcribe audio (ASR)
    2. Extract intent and entities (NLU)
    3. Execute database operation based on intent
    4. Return complete result
    
    Supported intents:
    - record_shipment: Create EPCIS shipping event
    - record_commission: Create new coffee batch
    - record_receipt: Create EPCIS receiving event
    - record_transformation: Create EPCIS transformation event
    
    Args:
        file: Audio file (any supported format)
        
    Returns:
        {
            "transcript": str,
            "intent": str,
            "entities": dict,
            "result": dict (database object created),
            "error": str (if database operation failed),
            "audio_metadata": dict
        }
        
    Requires:
        X-API-Key header with valid API key
        Database must be available
        
    Example:
        curl -X POST "http://localhost:8000/voice/process-command" \\
             -H "X-API-Key: your-api-key" \\
             -F "file=@record_shipment.wav"
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not available - cannot process commands"
        )
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    temp_dir = Path("tests/samples/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename
    wav_path = None

    try:
        # Save uploaded file
        content = await file.read()
        with temp_path.open("wb") as f:
            f.write(content)

        # Validate and convert to WAV
        wav_path, metadata = validate_and_convert_audio(str(temp_path))
        
        # Run ASR (audio → text)
        transcript = run_asr(wav_path)
        
        # Run NLU (text → intent + entities)
        nlu_result = infer_nlu_json(transcript)
        intent = nlu_result.get("intent")
        entities = nlu_result.get("entities", {})
        
        # Execute database operation based on intent
        db_result = None
        error = None
        
        # Use database session to execute command
        with get_db() as db:
            try:
                message, db_result = execute_voice_command(db, intent, entities)
                
                return {
                    "transcript": transcript,
                    "intent": intent,
                    "entities": entities,
                    "result": db_result,
                    "message": message,
                    "error": None,
                    "audio_metadata": metadata
                }
                
            except VoiceCommandError as e:
                # Command execution failed with known error
                return {
                    "transcript": transcript,
                    "intent": intent,
                    "entities": entities,
                    "result": None,
                    "error": str(e),
                    "audio_metadata": metadata
                }
            except Exception as e:
                # Unexpected error during command execution
                return {
                    "transcript": transcript,
                    "intent": intent,
                    "entities": entities,
                    "result": None,
                    "error": f"Unexpected error: {str(e)}",
                    "audio_metadata": metadata
                }
        
    except AudioValidationError as e:
        raise HTTPException(status_code=400, detail=f"Audio validation failed: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command processing failed: {str(e)}")
    finally:
        # Clean up temp files
        cleanup_temp_file(str(temp_path))
        if wav_path and wav_path != str(temp_path):
            cleanup_temp_file(wav_path)


@app.post("/asr-nlu", response_model=NLUResponse)
async def asr_nlu_endpoint(
    file: UploadFile = File(...),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Legacy endpoint: Accept audio file, run ASR + NLU, return structured JSON.
    
    This endpoint is kept for backward compatibility.
    New code should use /voice/transcribe or /voice/process-command instead.
    
    Args:
        file: Audio file (WAV, MP3, M4A, etc.)
        
    Returns:
        {
            "transcript": str,
            "intent": str,
            "entities": dict
        }
        
    Requires:
        X-API-Key header with valid API key
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Create temp directory for uploads
    temp_dir = Path("tests/samples")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        # Save incoming file
        with temp_path.open("wb") as f:
            content = await file.read()
            f.write(content)

        # Run ASR (audio → text)
        transcript = run_asr(str(temp_path))
        
        # Run NLU (text → intent + entities)
        result = infer_nlu_json(transcript)
        
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


# ============================================================================
# PHASE 2: ASYNC PROCESSING ENDPOINTS
# ============================================================================

# Import Celery task
try:
    from voice.tasks.voice_tasks import process_voice_command_task
    from voice.tasks.celery_app import app as celery_app
    CELERY_AVAILABLE = True
except ImportError as e:
    CELERY_AVAILABLE = False
    print(f"⚠️  Celery not available - async endpoints will be disabled: {e}")


class AsyncTaskResponse(BaseModel):
    """Response for async task submission."""
    status: str
    task_id: str
    message: str
    status_url: str


class TaskStatusResponse(BaseModel):
    """Response for task status check."""
    task_id: str
    status: str  # PENDING, STARTED, VALIDATING, TRANSCRIBING, EXTRACTING, EXECUTING, SUCCESS, FAILURE
    progress: Optional[int] = None  # 0-100
    stage: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


@app.post("/voice/upload-async", response_model=AsyncTaskResponse)
async def upload_audio_async(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload audio file for async voice command processing.
    
    Returns task_id immediately, processes in background.
    
    Pipeline:
    1. Upload file → Validate format
    2. Queue Celery task → Return task_id
    3. Worker processes: ASR → NLU → Database
    4. Poll /voice/status/{task_id} for result
    
    Args:
        file: Audio file (WAV, MP3, M4A, OGG)
        api_key: API key for authentication
        
    Returns:
        {
            "status": "processing",
            "task_id": "abc123...",
            "message": "Voice command queued for processing",
            "status_url": "/voice/status/abc123..."
        }
        
    Raises:
        503: Celery not available
        400: Invalid audio format or too large
    """
    
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async processing not available. Celery workers not running."
        )
    
    # Validate file format
    allowed_formats = ['.wav', '.mp3', '.m4a', '.ogg', '.aiff']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio format. Supported: {', '.join(allowed_formats)}"
        )
    
    # Save uploaded file to temp location
    temp_path = Path(f"/tmp/voice_upload_{file.filename}")
    
    try:
        content = await file.read()
        
        # Check file size (max 25MB for Whisper API)
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Audio file too large (max 25MB)"
            )
        
        # Save to temp file
        with temp_path.open("wb") as f:
            f.write(content)
        
        # Queue Celery task
        task = process_voice_command_task.delay(
            str(temp_path),
            original_filename=file.filename
        )
        
        return {
            "status": "processing",
            "task_id": task.id,
            "message": "Voice command queued for processing. Check status at /voice/status/{task_id}",
            "status_url": f"/voice/status/{task.id}"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        if temp_path.exists():
            temp_path.unlink()
        raise
        
    except Exception as e:
        # Cleanup and return error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue task: {str(e)}"
        )


@app.get("/voice/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Check status of async voice processing task.
    
    States:
    - PENDING: Task queued, waiting for worker
    - STARTED: Worker picked up task
    - VALIDATING: Validating audio file (10%)
    - TRANSCRIBING: Running Whisper ASR (30%)
    - EXTRACTING: Running GPT-3.5 NLU (60%)
    - EXECUTING: Creating database record (80%)
    - SUCCESS: Complete (100%)
    - FAILURE: Task failed
    
    Args:
        task_id: Task ID from /voice/upload-async
        api_key: API key for authentication
        
    Returns:
        {
            "task_id": "abc123...",
            "status": "TRANSCRIBING",
            "progress": 30,
            "stage": "Transcribing audio with Whisper",
            "result": null  # Available when SUCCESS
        }
        
    Raises:
        503: Celery not available
        404: Task not found
    """
    
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async processing not available"
        )
    
    # Get task result from Celery
    task = celery_app.AsyncResult(task_id)
    
    # Handle different task states
    if task.state == 'PENDING':
        return {
            "task_id": task_id,
            "status": "PENDING",
            "progress": 0,
            "stage": "Task queued, waiting for worker",
            "result": None,
            "error": None
        }
    
    elif task.state == 'STARTED':
        return {
            "task_id": task_id,
            "status": "STARTED",
            "progress": 5,
            "stage": "Worker started processing",
            "result": None,
            "error": None
        }
    
    elif task.state in ['VALIDATING', 'TRANSCRIBING', 'EXTRACTING', 'EXECUTING']:
        # Custom states with progress
        info = task.info or {}
        return {
            "task_id": task_id,
            "status": task.state,
            "progress": info.get('progress', 0),
            "stage": info.get('stage', f'{task.state}...'),
            "result": None,
            "error": None
        }
    
    elif task.state == 'SUCCESS':
        # Task completed
        result = task.result
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "progress": 100,
            "stage": "Complete",
            "result": result,
            "error": result.get('error') if isinstance(result, dict) else None
        }
    
    elif task.state == 'FAILURE':
        # Task failed
        return {
            "task_id": task_id,
            "status": "FAILURE",
            "progress": 0,
            "stage": "Task failed",
            "result": None,
            "error": str(task.info)
        }
    
    else:
        # Unknown state
        return {
            "task_id": task_id,
            "status": task.state,
            "progress": 0,
            "stage": f"Unknown state: {task.state}",
            "result": None,
            "error": None
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
