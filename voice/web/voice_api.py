"""
Web Voice API

Provides voice recording and conversation endpoints for web interface:
- Upload audio for processing
- Poll task status
- Get voice responses (TTS audio)

Integrates with existing Celery voice processing pipeline and conversation management.

Date: December 24, 2025
Lab 17: Bilingual Voice UI - Track 2
"""

import os
import tempfile
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from pathlib import Path
from celery.result import AsyncResult
import json

from database.models import UserIdentity
from database.connection import get_db
from voice.web.auth import get_current_user
from voice.providers.tts_provider import generate_speech
from voice.asr.asr_infer import run_asr_with_user_preference_async
from voice.integrations import process_english_conversation, process_amharic_conversation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/voice/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice processing with progress updates.
    
    Client sends:
        - Initial connection with optional JWT token as query param
        - Binary audio data
        - JSON message with {"language": "en" or "am"}
    
    Server sends progress updates:
        {"status": "transcribing", "progress": 20}
        {"status": "transcribed", "transcript": "..."}
        {"status": "processing", "progress": 50}
        {"status": "generating_audio", "progress": 80}
        {"status": "complete", "data": {...}}
        {"status": "error", "error": "..."}
    """
    await websocket.accept()
    
    try:
        # Get auth token from query params
        token = websocket.query_params.get('token')
        user = None
        
        if token:
            try:
                from voice.web.auth import verify_jwt_token
                from sqlalchemy.orm import Session
                from database.connection import get_db
                
                payload = verify_jwt_token(token)
                user_id = payload.get("user_id")
                
                # Get user from database
                db = next(get_db())
                user = db.query(UserIdentity).filter(UserIdentity.id == user_id).first()
            except Exception as auth_error:
                logger.warning(f"WebSocket auth failed: {auth_error}")
        
        # Receive initial message with language preference
        data = await websocket.receive_json()
        language = data.get('language', 'en')
        user_language = user.preferred_language if user else language
        user_id = user.id if user else 0
        
        logger.info(f"WebSocket voice session started for {'user ' + str(user.id) if user else 'anonymous'} ({user_language})")
        
        # Receive audio data
        await websocket.send_json({"status": "ready", "message": "Ready to receive audio"})
        audio_data = await websocket.receive_bytes()
        
        if len(audio_data) > 25 * 1024 * 1024:
            await websocket.send_json({"status": "error", "error": "Audio file too large (max 25MB)"})
            await websocket.close()
            return
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
            temp_file.write(audio_data)
            audio_path = temp_file.name
        
        # Step 1: Transcribe audio (STT)
        await websocket.send_json({"status": "transcribing", "progress": 20})
        
        try:
            asr_result = await run_asr_with_user_preference_async(audio_path, user_language)
            transcript = asr_result['text']
            await websocket.send_json({
                "status": "transcribed",
                "transcript": transcript,
                "progress": 40
            })
            logger.info(f"WebSocket transcript: {transcript[:100]}...")
        except Exception as asr_error:
            logger.error(f"WebSocket STT failed: {asr_error}")
            await websocket.send_json({"status": "error", "error": f"Speech recognition failed: {str(asr_error)}"})
            Path(audio_path).unlink(missing_ok=True)
            await websocket.close()
            return
        
        # Step 2: Process conversation
        await websocket.send_json({"status": "processing", "progress": 60})
        
        try:
            if user_language == 'am':
                conv_result = await process_amharic_conversation(user_id, transcript)
            else:
                import asyncio
                from functools import partial
                loop = asyncio.get_event_loop()
                # Bind all parameters in partial for correct execution
                conv_result = await loop.run_in_executor(
                    None,
                    partial(process_english_conversation, user_id, transcript, use_rag=True)
                )
            
            if isinstance(conv_result, str):
                try:
                    conv_result = json.loads(conv_result)
                except:
                    conv_result = {"message": "Sorry, I encountered a formatting error.", "ready_to_execute": False}
            
            logger.info(f"WebSocket conversation processed, keys: {list(conv_result.keys())}")
            logger.info(f"WebSocket message value: {conv_result.get('message', 'NO MESSAGE KEY')}")
            
        except Exception as conv_error:
            logger.error(f"WebSocket conversation failed: {conv_error}")
            await websocket.send_json({"status": "error", "error": f"Processing failed: {str(conv_error)}"})
            Path(audio_path).unlink(missing_ok=True)
            await websocket.close()
            return
        
        # Step 3: Generate TTS
        await websocket.send_json({"status": "generating_audio", "progress": 80})
        
        audio_url = None
        try:
            message_for_tts = conv_result.get('message_spoken') or conv_result.get('message_text') or conv_result.get('message', '')
            audio_bytes = await generate_speech(message_for_tts, user_language)
            
            tts_filename = f"tts_{user_id}_{hash(message_for_tts)}.mp3"
            tts_path = Path(tempfile.gettempdir()) / "voice_ledger_tts" / tts_filename
            tts_path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(tts_path, 'wb') as f:
                f.write(audio_bytes)
            
            audio_url = f"/api/voice/audio/{tts_filename}"
            logger.info(f"WebSocket TTS generated: {audio_url}")
        except Exception as tts_error:
            logger.warning(f"WebSocket TTS failed: {tts_error}")
        
        # Clean up
        Path(audio_path).unlink(missing_ok=True)
        
        # Send final result
        result = {
            "status": "complete",
            "progress": 100,
            "data": {
                "transcript": transcript,
                "message": conv_result.get('message') or conv_result.get('amharic_response', ''),
                "message_text": conv_result.get('message_text'),
                "message_spoken": conv_result.get('message_spoken'),
                "audio_url": audio_url,
                "ready_to_execute": conv_result.get('ready_to_execute', False),
                "needs_auth": conv_result.get('needs_auth', False),
                "telegram_bot_url": conv_result.get('telegram_bot_url')
            }
        }
        
        await websocket.send_json(result)
        logger.info(f"WebSocket session completed successfully")
        
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"status": "error", "error": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# Helper function to get optional user
async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[UserIdentity]:
    """Get user if authenticated, otherwise return None for anonymous access."""
    if not authorization:
        return None
    try:
        from voice.web.auth import verify_jwt_token
        from sqlalchemy.orm import joinedload
        
        # Remove "Bearer " prefix
        token = authorization.replace("Bearer ", "")
        payload = verify_jwt_token(token)
        user_id = payload.get("user_id")
        
        with get_db() as db:
            user = db.query(UserIdentity).options(
                joinedload(UserIdentity.organization)
            ).filter_by(id=user_id).first()
            
            if user:
                db.expunge_all()
                return user
    except Exception:
        pass
    return None


# ============================================================
# PYDANTIC MODELS
# ============================================================

class VoiceUploadResponse(BaseModel):
    task_id: Optional[str] = None
    status: str  # "processing" | "conversation" | "success" | "error"
    transcript: Optional[str] = None
    message: Optional[str] = None
    message_text: Optional[str] = None  # Full text with links/emojis (for display)
    message_spoken: Optional[str] = None  # Natural spoken version (for TTS)
    audio_url: Optional[str] = None
    needs_clarification: bool = False
    needs_auth: bool = False  # True if user needs to register/login
    telegram_bot_url: Optional[str] = None  # Registration link
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class VoiceStatusResponse(BaseModel):
    status: str  # "processing" | "conversation" | "success" | "error"
    stage: Optional[str] = None
    progress: Optional[int] = None
    transcript: Optional[str] = None
    message: Optional[str] = None
    audio_url: Optional[str] = None
    needs_clarification: bool = False
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================
# VOICE UPLOAD - INSTANT PROCESSING (NO CELERY)
# ============================================================

@router.post("/api/voice/upload", response_model=VoiceUploadResponse)
async def upload_voice(
    file: UploadFile = File(...),
    language: str = 'en',
    user: Optional[UserIdentity] = Depends(get_optional_user)
):
    """
    Upload voice audio for instant conversational processing.
    
    Now supports anonymous users! No authentication required.
    
    For authenticated users: Uses their stored language preference and user ID
    For anonymous users: Uses language from request, creates temporary session
    
    This endpoint processes voice immediately (no Celery queue) for real-time
    conversational experience:
    
    1. Transcribe audio (STT)
    2. Process with conversational AI
    3. Generate voice response (TTS)
    4. Return transcript + audio URL
    
    Flow:
    - User records voice → Upload
    - Server transcribes → Processes conversation → Generates TTS
    - Returns JSON with transcript, message, and audio_url
    - Frontend plays audio and displays message
    
    Args:
        file: Audio file (WAV, WebM, MP3, M4A, OGG)
        user: Authenticated user from JWT
        
    Returns:
        {
            "status": "conversation" | "success",
            "transcript": "What user said",
            "message": "AI response text",
            "audio_url": "/api/voice/audio/{audio_id}",
            "needs_clarification": true/false,
            "intent": "record_commission" (if ready),
            "entities": {...} (if ready)
        }
    """
    try:
        # Validate file size (max 25MB like Telegram)
        contents = await file.read()
        if len(contents) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Audio file too large (max 25MB)"
            )
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(
            suffix=Path(file.filename).suffix or '.webm',
            delete=False
        ) as temp_file:
            temp_file.write(contents)
            audio_path = temp_file.name
        
        # Determine language preference
        user_language = user.preferred_language if user else language
        user_id = user.id if user else 0  # Use 0 for anonymous users
        
        logger.info(
            f"Processing voice for {'user ' + str(user.id) if user else 'anonymous'} "
            f"({user_language}), file: {file.filename}, size: {len(contents)} bytes"
        )
        
        # Step 1: Transcribe audio (STT)
        try:
            asr_result = await run_asr_with_user_preference_async(
                audio_path,
                user_language
            )
            transcript = asr_result['text']
            logger.info(f"Transcript: {transcript[:100]}...")
        except Exception as asr_error:
            logger.error(f"STT failed: {asr_error}")
            # Clean up temp file
            Path(audio_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"Speech recognition failed: {str(asr_error)}"
            )
        
        # Step 2: Process conversation
        try:
            if user_language == 'am':
                conv_result = await process_amharic_conversation(user_id, transcript)
            else:
                # process_english_conversation is sync, need to handle
                import asyncio
                from functools import partial
                loop = asyncio.get_event_loop()
                # Bind all parameters in partial for correct execution
                conv_result = await loop.run_in_executor(
                    None,
                    partial(process_english_conversation, user_id, transcript, use_rag=True)
                )
            
            # Debug: Check if conv_result is a dict or string
            if isinstance(conv_result, str):
                logger.error(f"CRITICAL: conv_result is a string, not dict: {conv_result[:100]}")
                # Try to parse it as JSON
                try:
                    import json
                    conv_result = json.loads(conv_result)
                    logger.info("Successfully parsed conv_result string as JSON")
                except:
                    logger.error("Failed to parse conv_result as JSON")
                    conv_result = {
                        "message": "Sorry, I encountered a formatting error.",
                        "ready_to_execute": False
                    }
            
            assistant_message = conv_result.get('message') or conv_result.get('amharic_response', '')
            ready_to_execute = conv_result.get('ready_to_execute', False)
            
            logger.info(
                f"Conversation result: ready={ready_to_execute}, "
                f"message={assistant_message[:50]}..."
            )
            
        except Exception as conv_error:
            logger.error(f"Conversation processing failed: {conv_error}")
            # Clean up temp file
            Path(audio_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"Conversation processing failed: {str(conv_error)}"
            )
        
        # Step 3: Generate voice response (TTS)
        audio_url = None
        try:
            # Use spoken version for TTS (if available), otherwise use regular message
            message_for_tts = conv_result.get('message_spoken') or conv_result.get('message_text') or assistant_message
            
            audio_bytes = await generate_speech(
                message_for_tts,
                user_language
            )
            
            # Save TTS audio to temp location for serving
            # Use a simple in-memory cache or temp directory
            tts_filename = f"tts_{user_id}_{hash(message_for_tts)}.mp3"
            tts_path = Path(tempfile.gettempdir()) / "voice_ledger_tts" / tts_filename
            tts_path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(tts_path, 'wb') as f:
                f.write(audio_bytes)
            
            audio_url = f"/api/voice/audio/{tts_filename}"
            logger.info(f"Generated TTS audio: {audio_url}")
            
        except Exception as tts_error:
            logger.warning(f"TTS generation failed: {tts_error}")
            # Non-fatal - can still return text response
            audio_url = None
        
        # Clean up input audio temp file
        Path(audio_path).unlink(missing_ok=True)
        
        # Step 4: Return response
        if ready_to_execute:
            # Command is ready to execute
            # In a full implementation, would call execute_voice_command here
            # For now, just return the intent and entities
            return VoiceUploadResponse(
                status="success",
                transcript=transcript,
                message=assistant_message,
                message_text=conv_result.get('message_text', assistant_message),
                message_spoken=conv_result.get('message_spoken', assistant_message),
                audio_url=audio_url,
                needs_clarification=False,
                needs_auth=conv_result.get('needs_auth', False),
                telegram_bot_url=conv_result.get('telegram_bot_url'),
                intent=conv_result.get('intent'),
                entities=conv_result.get('entities'),
                result=None  # Would contain database operation result
            )
        else:
            # Need more information - continue conversation
            return VoiceUploadResponse(
                status="conversation",
                transcript=transcript,
                message=assistant_message,
                message_text=conv_result.get('message_text', assistant_message),
                message_spoken=conv_result.get('message_spoken', assistant_message),
                audio_url=audio_url,
                needs_clarification=True,
                needs_auth=conv_result.get('needs_auth', False),
                telegram_bot_url=conv_result.get('telegram_bot_url')
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Voice processing failed: {str(e)}"
        )


# ============================================================
# SERVE TTS AUDIO
# ============================================================

@router.get("/api/voice/audio/{audio_filename}")
async def get_voice_audio(
    audio_filename: str,
    user: Optional[UserIdentity] = Depends(get_optional_user)
):
    """
    Serve generated TTS audio file.
    
    Now publicly accessible (no auth required).
    
    Args:
        audio_filename: TTS audio filename
        user: Optional authenticated user
        
    Returns:
        Audio file (MP3)
    """
    tts_path = Path(tempfile.gettempdir()) / "voice_ledger_tts" / audio_filename
    
    if not tts_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Read audio bytes
    with open(tts_path, 'rb') as f:
        audio_bytes = f.read()
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"inline; filename={audio_filename}",
            "Cache-Control": "max-age=3600"
        }
    )


# ============================================================
# LANGUAGE PREFERENCE (already in user_profile_api.py)
# ============================================================

# Language preference endpoints are in voice/web/user_profile_api.py:
# - GET /api/users/me/profile - Get current language
# - PATCH /api/users/me/language - Update language
