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
from voice.asr.asr_infer import run_asr
from voice.nlu.nlu_infer import infer_nlu_json
from voice.audio_utils import validate_and_convert_audio, cleanup_temp_file, AudioValidationError
from database.connection import get_db
from voice.command_integration import execute_voice_command, VoiceCommandError

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
            meta={'stage': 'Transcribing audio with Whisper (auto-detecting language)', 'progress': 30}
        )
        
        # Run ASR (Whisper) with automatic language detection
        try:
            asr_result = run_asr(wav_path)
            transcript = asr_result['text']
            detected_language = asr_result['language']
            metadata['detected_language'] = detected_language
            logger.info(f"ASR detected language: {detected_language}, transcript: {transcript[:50]}...")
        except Exception as e:
            # Retry on ASR failures (could be API rate limit)
            logger.error(f"ASR failed: {e}")
            raise self.retry(exc=e, countdown=60)
        
        # Update task state: extracting
        self.update_state(
            state='EXTRACTING',
            meta={
                'stage': f'Extracting intent and entities (Language: {detected_language})', 
                'progress': 60
            }
        )
        
        # Run NLU (GPT-3.5) - works for both English and Amharic
        try:
            nlu_result = infer_nlu_json(transcript)
            intent = nlu_result.get("intent")
            entities = nlu_result.get("entities", {})
        except Exception as e:
            # Retry on NLU failures
            logger.error(f"NLU failed: {e}")
            raise self.retry(exc=e, countdown=60)
        
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
                        from voice.telegram.notifier import send_batch_confirmation, send_error_notification
                        
                        # Use chat_id if available, otherwise user_id
                        target_id = chat_id if chat_id else int(user_id) if isinstance(user_id, str) else user_id
                        
                        if not error and db_result:
                            # Success notification
                            batch_info = {
                                "id": db_result.get("batch_id") or db_result.get("gtin"),
                                "variety": db_result.get("variety") or entities.get("product", "Unknown"),
                                "quantity": db_result.get("quantity_kg") or entities.get("quantity", 0),
                                "farm": db_result.get("origin") or entities.get("origin", "Unknown"),
                                "gtin": db_result.get("gtin")
                            }
                            logger.info(f"Sending batch confirmation to Telegram chat {target_id}")
                            success = send_batch_confirmation(target_id, batch_info)
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
