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
from voice.tts import generate_speech
from voice.asr.asr_infer import run_asr_with_user_preference_async


def is_maintenance_mode() -> bool:
    """Check if system is in maintenance mode."""
    try:
        maintenance_file = Path(__file__).parent.parent.parent / ".maintenance"
        if maintenance_file.exists():
            content = maintenance_file.read_text().strip()
            # Check if MAINTENANCE_MODE=True
            for line in content.split('\n'):
                if line.startswith('MAINTENANCE_MODE='):
                    value = line.split('=')[1].strip()
                    return value.lower() in ('true', '1', 'yes')
        return False
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        return False
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
        
        # Check maintenance mode
        if is_maintenance_mode():
            await websocket.send_json({
                "status": "maintenance",
                "message": "🔧 System Under Maintenance",
                "details": "The Voice Ledger system is currently undergoing maintenance. Please try again later."
            })
            await websocket.close()
            return
        
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
    # VOICE-FIRST ARCHITECTURE: Action execution and workflow support
    action: Optional[Dict[str, Any]] = None  # Executable action for frontend
    workflow: Optional[Dict[str, Any]] = None  # Workflow state info
    session_id: Optional[str] = None  # Workflow session ID
    workflow_completed: bool = False  # True when workflow finishes
    # Observability — fallback visibility
    response_source: Optional[str] = None  # "agent" | "fallback_nlu" | "fallback_failed"
    agent_error: Optional[str] = None  # Error string when agent fails
    fallback_error: Optional[str] = None  # Error string when fallback also fails


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
    context: Optional[str] = None,
    session_id: Optional[str] = None,
    user: Optional[UserIdentity] = Depends(get_optional_user)
):
    """
    Upload voice audio for instant conversational processing.
    
    VOICE-FIRST ARCHITECTURE:
    - Context-aware: Accepts app context to understand what user is viewing/doing
    - Workflow support: Manages multi-turn conversations via session_id
    - Action execution: Returns executable actions for frontend
    
    Now supports anonymous users! No authentication required.
    
    For authenticated users: Uses their stored language preference and user ID
    For anonymous users: Uses language from request, creates temporary session
    
    This endpoint processes voice immediately (no Celery queue) for real-time
    conversational experience:
    
    1. Transcribe audio (STT)
    2. Process with conversational AI (with context)
    3. Generate voice response (TTS)
    4. Return transcript + audio URL + actions
    
    Flow:
    - User records voice → Upload with context
    - Server transcribes → Processes conversation with context → Generates TTS
    - Returns JSON with transcript, message, audio_url, and executable actions
    - Frontend plays audio, displays message, executes actions
    
    Args:
        file: Audio file (WAV, WebM, MP3, M4A, OGG)
        language: User's preferred language ('en' or 'am')
        context: JSON string with app context (which app, visible data, user role, etc.)
        session_id: Workflow session ID for multi-turn conversations
        user: Authenticated user from JWT
        
    Returns:
        {
            "status": "conversation" | "success",
            "transcript": "What user said",
            "message": "AI response text",
            "audio_url": "/api/voice/audio/{audio_id}",
            "needs_clarification": true/false,
            "intent": "record_commission" (if ready),
            "entities": {...} (if ready),
            "action": {"type": "share_batch", "params": {...}},
            "workflow": {"type": "batch_recording", "state": "COLLECTING_ORIGIN"},
            "session_id": "workflow_12345",
            "workflow_completed": false
        }
    """
    try:
        # Parse context from mini app
        context_data = {}
        if context:
            try:
                context_data = json.loads(context)
                logger.info(f"Voice upload with context: {context_data.get('app', 'unknown')}")
            except json.JSONDecodeError:
                logger.warning("Failed to parse context JSON")
        
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
        
        # Step 2: Process with AI Agent or legacy conversation
        try:
            import os as _os
            agent_handled = False
            conv_result = None
            agent_error_detail = None  # Observability: track agent errors

            # =================================================================
            # AI AGENT PATH for Mini App voice (mirrors voice_tasks.py)
            # Requires authenticated user (user_id != 0) and AGENT_ENABLED
            # =================================================================
            if _os.getenv("AGENT_ENABLED", "false").lower() == "true" and user_id:
                try:
                    from voice.agent import AgentExecutor

                    agent_user_did = user.did if user else None

                    logger.info(f"🤖 Agent processing Mini App voice from user {user_id}: {transcript[:50]}")

                    executor = AgentExecutor()
                    # Run sync executor in thread pool to avoid blocking
                    # the async event loop (OpenAI SDK calls are blocking).
                    import asyncio
                    from functools import partial as _partial
                    _loop = asyncio.get_event_loop()
                    agent_result = await _loop.run_in_executor(
                        None,
                        _partial(
                            executor.run,
                            transcript=transcript,
                            user_id=user_id,
                            user_did=agent_user_did,
                            language=user_language,
                        ),
                    )

                    logger.info(
                        f"🤖 Agent Mini App completed: {len(agent_result.tool_calls)} tool call(s), "
                        f"write={agent_result.performed_write}, "
                        f"tokens={agent_result.total_tokens}, "
                        f"time={agent_result.duration_ms:.0f}ms"
                    )

                    if agent_result.response:
                        conv_result = {
                            'message': agent_result.response,
                            'message_text': agent_result.response,
                            'message_spoken': agent_result.response_spoken or agent_result.response,
                            'ready_to_execute': agent_result.performed_write,
                            'intent': agent_result.intent,
                            'entities': agent_result.entities,
                            'response_source': 'agent',
                        }
                        # Attach batch data (incl. QR code) for commission so
                        # the frontend can render the verification QR.
                        if (
                            agent_result.performed_write
                            and agent_result.intent == "record_commission"
                        ):
                            for _tc in agent_result.tool_calls:
                                if _tc.tool_name == "record_commission" and _tc.success:
                                    conv_result["batch_data"] = _tc.result_data
                                    break
                        agent_handled = True

                except Exception as agent_err:
                    agent_error_detail = f"{type(agent_err).__name__}: {agent_err}"
                    logger.error(f"🤖 Agent failed for Mini App, falling back: {agent_err}", exc_info=True)
                    logger.warning(f"⚠️ FALLBACK ACTIVE for voice from user {user_id}: {type(agent_err).__name__}")

            # =================================================================
            # LEGACY PATH — conversational AI (fallback for anonymous or
            # when AGENT_ENABLED=false or agent fails/returns no response)
            # =================================================================
            if not agent_handled:
                fallback_error_detail = None
                try:
                    if user_language == 'am':
                        conv_result = await process_amharic_conversation(
                            user_id, 
                            transcript,
                            context=context_data
                        )
                    else:
                        # process_english_conversation is sync, need to handle
                        import asyncio
                        from functools import partial
                        loop = asyncio.get_event_loop()
                        # Bind all parameters in partial for correct execution
                        conv_result = await loop.run_in_executor(
                            None,
                            partial(
                                process_english_conversation, 
                                user_id, 
                                transcript, 
                                use_rag=True,
                                context=context_data
                            )
                        )
                    # Tag with observability fields
                    if isinstance(conv_result, dict):
                        conv_result['response_source'] = 'fallback_nlu' if agent_error_detail else 'legacy'
                        if agent_error_detail:
                            conv_result['agent_error'] = agent_error_detail
                except Exception as fallback_err:
                    fallback_error_detail = f"{type(fallback_err).__name__}: {fallback_err}"
                    logger.error(f"Fallback also failed: {fallback_err}", exc_info=True)
                    conv_result = {
                        'message': 'Sorry, I encountered an error processing your message.',
                        'ready_to_execute': False,
                        'response_source': 'fallback_failed',
                        'agent_error': agent_error_detail,
                        'fallback_error': fallback_error_detail,
                    }
            
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
        response_data = {
            "transcript": transcript,
            "message": assistant_message,
            "message_text": conv_result.get('message_text', assistant_message),
            "message_spoken": conv_result.get('message_spoken', assistant_message),
            "audio_url": audio_url,
            "needs_clarification": not ready_to_execute,
            "needs_auth": conv_result.get('needs_auth', False),
            "telegram_bot_url": conv_result.get('telegram_bot_url'),
            # Observability — fallback visibility
            "response_source": conv_result.get('response_source'),
            "agent_error": conv_result.get('agent_error'),
            "fallback_error": conv_result.get('fallback_error'),
        }
        
        # Add action if available
        if conv_result.get('action'):
            response_data["action"] = conv_result['action']
        
        # Add workflow info if in workflow
        if conv_result.get('workflow_state'):
            response_data["workflow"] = {
                "type": conv_result.get('workflow_type'),
                "state": conv_result.get('workflow_state')
            }
            response_data["session_id"] = conv_result.get('session_id', session_id)
            response_data["workflow_completed"] = False
        
        if conv_result.get('workflow_completed'):
            response_data["workflow_completed"] = True
        
        if ready_to_execute:
            # Command is ready to execute
            response_data["status"] = "success"
            response_data["intent"] = conv_result.get('intent')
            response_data["entities"] = conv_result.get('entities')
            response_data["result"] = None  # Would contain database operation result
        else:
            # Need more information - continue conversation
            response_data["status"] = "conversation"
        
        return VoiceUploadResponse(**response_data)
    
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
# RAG TEST ENDPOINT
# ============================================================

class ConversationTestRequest(BaseModel):
    text: str
    language: Literal['en', 'am'] = 'en'
    use_rag: bool = True

class AmharicTestRequest(BaseModel):
    text: str
    user_id: int = 0

@router.post("/api/voice/test/conversation")
async def test_conversation(
    request: ConversationTestRequest
):
    """
    Test conversation processing with RAG (for testing purposes).
    
    Args:
        request: Test request with text and language
        
    Returns:
        Conversation result with RAG metadata
    """
    try:
        user_id = 0  # Anonymous user for testing
        
        if request.language == 'am':
            result = await process_amharic_conversation(user_id, request.text)
        else:
            import asyncio
            from functools import partial
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                partial(process_english_conversation, user_id, request.text, use_rag=request.use_rag)
            )
        
        # Add metadata about RAG usage
        if isinstance(result, dict):
            result['rag_used'] = request.use_rag
            result['language'] = request.language
        
        return result
        
    except Exception as e:
        logger.error(f"Test conversation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Conversation processing failed: {str(e)}"
        )

@router.post("/api/voice/test/amharic")
async def test_amharic_conversation(
    request: AmharicTestRequest
):
    """
    Test Amharic conversation with RAG integration.
    
    This endpoint:
    - Translates Amharic to English (OpenAI)
    - Searches documentation if applicable (RAG)
    - Returns Amharic response (AddisAI)
    
    Args:
        request: Amharic text and user_id
        
    Returns:
        Conversation result with translation metadata
    """
    try:
        result = await process_amharic_conversation(request.user_id, request.text)
        
        # Add test metadata
        if isinstance(result, dict):
            result['rag_used'] = True  # RAG is enabled by default in process_amharic_conversation
            result['language'] = 'am'
        
        return result
        
    except Exception as e:
        logger.error(f"Amharic test conversation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Amharic conversation processing failed: {str(e)}"
        )


# ============================================================
# LANGUAGE PREFERENCE (already in user_profile_api.py)
# ============================================================

# Language preference endpoints are in voice/web/user_profile_api.py:
# - GET /api/users/me/profile - Get current language
# - PATCH /api/users/me/language - Update language
