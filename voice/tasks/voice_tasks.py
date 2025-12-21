"""
Voice Processing Celery Tasks

Background tasks for async voice command processing.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any
from celery import Task

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from voice.tasks.celery_app import app
from voice.asr.asr_infer import run_asr, run_asr_with_user_preference
from voice.nlu.nlu_infer import infer_nlu_json
from voice.audio_utils import validate_and_convert_audio, cleanup_temp_file, AudioValidationError
from database.connection import get_db
from voice.command_integration import execute_voice_command, VoiceCommandError
from voice.tasks.voice_command_detector import detect_voice_command
from voice.integrations import ConversationManager, process_english_conversation, process_amharic_conversation

# Import SMS notifier for IVR notifications
try:
    from voice.ivr.sms_notifier import SMSNotifier
    sms_notifier = SMSNotifier()
except ImportError:
    sms_notifier = None


class VoiceProcessingTask(Task):
    """
    Base task class for voice processing.
    
    Provides:
    - Progress tracking
    - Error handling
    - Cleanup on failure
    """
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        # Cleanup temp files if they exist
        if 'audio_path' in kwargs:
            cleanup_temp_file(kwargs['audio_path'])
        
        print(f"Task {task_id} failed: {exc}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        # Cleanup temp files
        if 'audio_path' in kwargs:
            cleanup_temp_file(kwargs['audio_path'])
        
        print(f"Task {task_id} completed successfully")


@app.task(
    base=VoiceProcessingTask,
    bind=True,
    name='voice.tasks.process_voice_command',
    max_retries=3,
    default_retry_delay=60
)
def process_voice_command_task(
    self, 
    audio_path: str, 
    original_filename: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Background task: Process voice command from audio file.
    
    Pipeline:
    1. Validate and convert audio to WAV
    2. Transcribe with Whisper (ASR)
    3. Extract intent/entities with GPT-3.5 (NLU)
    4. Execute database command
    5. Return complete result
    
    Args:
        self: Task instance (auto-injected by bind=True)
        audio_path: Path to uploaded audio file
        original_filename: Original filename for logging
        metadata: Optional metadata (channel, user_id, etc.)
        
    Returns:
        {
            "status": "success" | "error",
            "transcript": str,
            "intent": str,
            "entities": dict,
            "result": dict,  # Database operation result
            "error": str | None,
            "audio_metadata": dict
        }
        
    Raises:
        Exception: On unrecoverable errors (triggers retry)
    """
    
    # Initialize metadata if not provided
    if metadata is None:
        metadata = {}
    
    try:
        # Update task state: validating
        self.update_state(
            state='VALIDATING',
            meta={'stage': 'Validating audio file', 'progress': 10}
        )
        
        # Validate and convert audio to WAV
        try:
            wav_path, audio_metadata = validate_and_convert_audio(audio_path)
            # Merge audio metadata with passed metadata
            metadata.update(audio_metadata)
        except AudioValidationError as e:
            return {
                "status": "error",
                "error": f"Audio validation failed: {str(e)}",
                "transcript": None,
                "intent": None,
                "entities": None,
                "result": None,
                "audio_metadata": None
            }
        
        # Update task state: transcribing
        self.update_state(
            state='TRANSCRIBING',
            meta={'stage': 'Transcribing audio with Whisper', 'progress': 30}
        )
        
        # Get user to determine language preference
        user_db_id = None  # Store user's database ID (not the object)
        user_language = 'en'  # Default to English
        user_telegram_id = None
        
        with get_db() as db:
            try:
                from ssi.user_identity import get_user_by_telegram_id
                from database.models import UserIdentity
                
                # IVR channel: User already authenticated, ID passed in metadata
                if metadata and metadata.get("channel") == "ivr":
                    user_db_id = metadata.get("user_id")
                    if user_db_id:
                        user_identity = db.query(UserIdentity).filter_by(id=user_db_id).first()
                        if user_identity:
                            user_language = user_identity.preferred_language or 'en'
                            user_telegram_id = user_identity.telegram_user_id
                            logger.info(f"IVR call from user {user_db_id}, language: {user_language}")
                        else:
                            logger.error(f"IVR: User ID {user_db_id} not found in database")
                
                # Telegram channel: Look up by telegram_user_id
                elif metadata and metadata.get("channel") == "telegram":
                    user_telegram_id = metadata.get("user_id")
                    if user_telegram_id:
                        user_identity = get_user_by_telegram_id(user_telegram_id, db)
                        if user_identity:
                            # Check if user is approved
                            if not user_identity.is_approved:
                                logger.warning(f"User {user_telegram_id} not approved yet")
                                # Send notification to user
                                from voice.service.notification_processor import NotificationProcessor
                                processor = NotificationProcessor()
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    loop.run_until_complete(
                                        processor.send_notification(
                                            channel_name='telegram',
                                            user_id=user_telegram_id,
                                            message="⏳ Your registration is pending admin approval. You'll be notified once approved!"
                                        )
                                    )
                                finally:
                                    loop.close()
                                
                                return {
                                    "status": "error",
                                    "error": "User not approved",
                                    "message": "Registration pending approval"
                                }
                            
                            user_db_id = user_identity.id  # Store the ID, not the object
                            user_language = user_identity.preferred_language or 'en'
                            logger.info(f"User {user_db_id} language preference: {user_language}")
                        else:
                            logger.warning(f"User {user_telegram_id} not found in database - needs registration")
            except Exception as e:
                logger.warning(f"Could not get user language preference: {e}")
        
        # ENFORCE REGISTRATION: Reject if user not found
        if not user_db_id:
            logger.error(f"User {user_telegram_id} not registered")
            # Send notification to user
            from voice.service.notification_processor import NotificationProcessor
            processor = NotificationProcessor()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    processor.send_notification(
                        channel_name='telegram',
                        user_id=user_telegram_id,
                        message=(
                            "🔒 Please register first!\n\n"
                            "Send /register to create your account and select your language preference."
                        )
                    )
                )
            finally:
                loop.close()
            
            return {
                "status": "error",
                "error": "User not registered",
                "message": "Please register first using /register"
            }
        
        # Run ASR with user's language preference (NEW: no auto-detection)
        try:
            asr_result = run_asr_with_user_preference(wav_path, user_language)
            transcript = asr_result['text']
            detected_language = asr_result['language']
            metadata['detected_language'] = detected_language
            logger.info(f"ASR with language '{detected_language}': {transcript[:50]}...")
        except Exception as e:
            # Fallback to old detection-based ASR
            logger.warning(f"New ASR failed, falling back to detection: {e}")
            try:
                asr_result = run_asr(wav_path)
                transcript = asr_result['text']
                detected_language = asr_result['language']
                metadata['detected_language'] = detected_language
            except Exception as asr_error:
                logger.error(f"ASR failed: {asr_error}")
                raise self.retry(exc=asr_error, countdown=60)
        
        # Check for voice commands (simple pattern matching)
        voice_command_result = detect_voice_command(transcript, metadata)
        if voice_command_result:
            command = voice_command_result['command']
            logger.info(f"Voice command detected: {command}")
            
            # Route to Telegram command handler
            if metadata and metadata.get("channel") == "telegram":
                user_id = metadata.get("user_id")
                if user_id:
                    try:
                        import asyncio
                        from voice.telegram.telegram_api import route_voice_to_command
                        
                        # Run async function in event loop - let it complete fully
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            # Execute the async function and wait for completion
                            response = loop.run_until_complete(
                                route_voice_to_command(command, int(user_id), metadata)
                            )
                            
                            # Give any background tasks time to finish (e.g., HTTP requests)
                            # This ensures httpx connections are properly closed
                            loop.run_until_complete(asyncio.sleep(0.1))
                            
                            result = {
                                "status": "success",
                                "transcript": transcript,
                                "command": command,
                                "response": response,
                                "audio_metadata": metadata
                            }
                        finally:
                            # Shutdown async generators and cancel any remaining tasks
                            try:
                                if hasattr(loop, 'shutdown_asyncgens'):
                                    loop.run_until_complete(loop.shutdown_asyncgens())
                            except Exception as e:
                                logger.debug(f"Async generator shutdown warning: {e}")
                            
                            try:
                                loop.close()
                            except Exception as e:
                                logger.debug(f"Loop close warning: {e}")
                        
                        return result
                            
                    except Exception as e:
                        logger.error(f"Failed to route voice command: {e}")
                        # Fall back to returning the detection result
                        return voice_command_result
            
            return voice_command_result
        
        # Update task state: extracting
        self.update_state(
            state='EXTRACTING',
            meta={
                'stage': f'Processing conversation (Language: {detected_language})', 
                'progress': 60
            }
        )
        
        # Route to conversational AI based on user language (NEW: multi-turn conversation)
        try:
            # Ensure we have user_db_id for conversational tracking
            if not user_db_id:
                logger.warning("No user identity, falling back to single-shot NLU")
                raise Exception("User not registered")
            
            # Import async processing
            import asyncio
            
            # Process conversation based on language
            if user_language == 'am':
                # Amharic conversation with Addis AI
                logger.info(f"Processing Amharic conversation for user {user_db_id}")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    conversation_result = loop.run_until_complete(
                        process_amharic_conversation(user_db_id, transcript)
                    )
                    loop.run_until_complete(asyncio.sleep(0.1))
                finally:
                    try:
                        if hasattr(loop, 'shutdown_asyncgens'):
                            loop.run_until_complete(loop.shutdown_asyncgens())
                    except:
                        pass
                    loop.close()
            else:
                # English conversation with GPT-4
                logger.info(f"Processing English conversation for user {user_db_id}")
                conversation_result = process_english_conversation(user_db_id, transcript)
            
            # Check if conversation is ready to execute
            if not conversation_result.get('ready_to_execute'):
                # Conversation needs more information - send follow-up question
                follow_up_message = conversation_result.get('message', 'Please provide more information.')
                logger.info(f"Conversation not ready, sending follow-up: {follow_up_message}")
                
                # Send follow-up via Telegram if available
                if metadata and metadata.get("channel") == "telegram":
                    user_id = metadata.get("user_id")
                    if user_id:
                        try:
                            from voice.telegram.notifier import send_telegram_notification
                            send_telegram_notification(int(user_id), follow_up_message)
                        except Exception as msg_error:
                            logger.error(f"Failed to send follow-up message: {msg_error}")
                
                return {
                    "status": "awaiting_response",
                    "transcript": transcript,
                    "message": follow_up_message,
                    "conversation_active": True,
                    "audio_metadata": metadata
                }
            
            # Conversation ready - extract intent and entities
            intent = conversation_result.get('intent')
            entities = conversation_result.get('entities', {})
            logger.info(f"Conversation ready: intent={intent}, entities={entities}")
            
        except Exception as conv_error:
            # Fallback to single-shot NLU (GPT-3.5) if conversational AI fails
            logger.warning(f"Conversational AI failed, falling back to single-shot: {conv_error}")
            try:
                nlu_result = infer_nlu_json(transcript)
                intent = nlu_result.get("intent")
                entities = nlu_result.get("entities", {})
            except Exception as nlu_error:
                logger.error(f"NLU fallback also failed: {nlu_error}")
                raise self.retry(exc=nlu_error, countdown=60)
        
        # Update task state: executing
        self.update_state(
            state='EXECUTING',
            meta={'stage': 'Executing database command', 'progress': 80}
        )
        
        # Execute database command
        db_result = None
        error = None
        user_identity = None
        
        with get_db() as db:
            try:
                # Get or create user identity (for DID and batch ownership)
                user_id_for_identity = None
                username = None
                first_name = None
                last_name = None
                
                if metadata:
                    if metadata.get("channel") == "telegram":
                        user_id_for_identity = metadata.get("user_id")
                        username = metadata.get("username")
                        # Extract name from metadata if available
                        first_name = metadata.get("first_name")
                        last_name = metadata.get("last_name")
                
                if user_id_for_identity:
                    try:
                        from ssi.user_identity import get_or_create_user_identity
                        user_identity = get_or_create_user_identity(
                            telegram_user_id=str(user_id_for_identity),
                            telegram_username=username,
                            telegram_first_name=first_name,
                            telegram_last_name=last_name,
                            db_session=db
                        )
                        logger.info(f"User identity: {user_identity['did']}, created={user_identity['created']}")
                    except Exception as e:
                        logger.warning(f"Failed to create user identity: {e}")
                
                # Execute command with user context
                if user_identity:
                    message, db_result = execute_voice_command(
                        db, intent, entities, 
                        user_id=user_identity.get('user_id'),
                        user_did=user_identity.get('did')
                    )
                else:
                    message, db_result = execute_voice_command(db, intent, entities)
                
            except VoiceCommandError as e:
                # Known command error (not a failure, just unsupported)
                error = str(e)
                
            except Exception as e:
                # Unexpected database error
                error = f"Database error: {str(e)}"
                logger.error(f"Database error details: {e}", exc_info=True)
        
        # Send notification back to user
        if metadata:
            channel = metadata.get("channel") or metadata.get("source")
            user_id = metadata.get("user_id") or metadata.get("from_number")
            chat_id = metadata.get("chat_id")
            
            if channel and user_id:
                try:
                    # Telegram notifications (simple and reliable)
                    if channel == "telegram":
                        from voice.telegram.notifier import send_batch_verification_qr, send_error_notification
                        
                        # Use chat_id if available, otherwise user_id
                        target_id = chat_id if chat_id else int(user_id) if isinstance(user_id, str) else user_id
                        
                        if not error and db_result:
                            # Success notification with verification QR code
                            batch_info = {
                                "batch_id": db_result.get("batch_id"),
                                "variety": db_result.get("variety") or entities.get("product", "Unknown"),
                                "quantity_kg": db_result.get("quantity_kg") or entities.get("quantity", 0),
                                "origin": db_result.get("origin") or entities.get("origin", "Unknown"),
                                "gtin": db_result.get("gtin"),
                                "gln": db_result.get("gln"),
                                "status": db_result.get("status", "PENDING_VERIFICATION"),
                                "verification_token": db_result.get("verification_token")
                            }
                            logger.info(f"Sending batch verification QR code to Telegram chat {target_id}")
                            success = send_batch_verification_qr(target_id, batch_info)
                            if success:
                                logger.info(f"Notification sent successfully to {target_id}")
                            else:
                                logger.error(f"Failed to send notification to {target_id}")
                        else:
                            # Error notification
                            logger.info(f"Sending error notification to Telegram chat {target_id}")
                            send_error_notification(target_id, error or 'Processing failed')
                    
                    # IVR/SMS notifications (legacy)
                    elif channel == "ivr":
                        from voice.ivr.sms_notifier import SMSNotifier
                        sms_notifier = SMSNotifier()
                        
                        if sms_notifier.is_available():
                            if not error and db_result:
                                batch_id = db_result.get("batch_id") or db_result.get("gtin")
                                batch_data = {
                                    "coffee_type": entities.get("product", "Unknown"),
                                    "quantity_kg": entities.get("quantity", 0)
                                }
                                sms_notifier.send_batch_confirmation(user_id, batch_data, batch_id)
                            else:
                                sms_notifier.send_error_notification(user_id, error or 'Processing failed')
                
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}", exc_info=True)
        
        # Clear conversation history after successful execution
        if not error and user_db_id:
            try:
                ConversationManager.clear_conversation(user_db_id)
                logger.info(f"Cleared conversation for user {user_db_id}")
            except Exception as clear_error:
                logger.warning(f"Failed to clear conversation: {clear_error}")
        
        # Return complete result
        return {
            "status": "success" if not error else "partial",
            "transcript": transcript,
            "intent": intent,
            "entities": entities,
            "result": db_result,
            "message": message if not error else None,
            "error": error,
            "audio_metadata": metadata
        }
        
    except Exception as e:
        # Unexpected error - log and return error result
        print(f"Task failed with unexpected error: {str(e)}")
        return {
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "transcript": None,
            "intent": None,
            "entities": None,
            "result": None,
            "audio_metadata": None
        }
