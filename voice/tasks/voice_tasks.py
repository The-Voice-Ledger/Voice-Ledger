"""
Voice Processing Celery Tasks

Background tasks for async voice command processing.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any
from celery import Task

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
def process_voice_command_task(self, audio_path: str, original_filename: str = None) -> Dict[str, Any]:
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
    
    try:
        # Update task state: validating
        self.update_state(
            state='VALIDATING',
            meta={'stage': 'Validating audio file', 'progress': 10}
        )
        
        # Validate and convert audio to WAV
        try:
            wav_path, metadata = validate_and_convert_audio(audio_path)
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
        
        # Run ASR (Whisper)
        try:
            transcript = run_asr(wav_path)
        except Exception as e:
            # Retry on ASR failures (could be API rate limit)
            raise self.retry(exc=e, countdown=60)
        
        # Update task state: extracting
        self.update_state(
            state='EXTRACTING',
            meta={'stage': 'Extracting intent and entities', 'progress': 60}
        )
        
        # Run NLU (GPT-3.5)
        try:
            nlu_result = infer_nlu_json(transcript)
            intent = nlu_result.get("intent")
            entities = nlu_result.get("entities", {})
        except Exception as e:
            # Retry on NLU failures
            raise self.retry(exc=e, countdown=60)
        
        # Update task state: executing
        self.update_state(
            state='EXECUTING',
            meta={'stage': 'Executing database command', 'progress': 80}
        )
        
        # Execute database command
        db_result = None
        error = None
        
        with get_db() as db:
            try:
                message, db_result = execute_voice_command(db, intent, entities)
                
            except VoiceCommandError as e:
                # Known command error (not a failure, just unsupported)
                error = str(e)
                
            except Exception as e:
                # Unexpected database error
                error = f"Database error: {str(e)}"
        
        # Send SMS notification if this came from IVR and we have phone number
        if metadata and metadata.get("source") == "ivr":
            from_number = metadata.get("from_number")
            
            if from_number and sms_notifier and sms_notifier.is_available():
                try:
                    if not error and db_result:
                        # Success - send batch confirmation
                        batch_id = db_result.get("batch_id") or db_result.get("gtin")
                        batch_data = {
                            "coffee_type": entities.get("coffee_type", "Unknown"),
                            "quantity_bags": entities.get("quantity_bags", 0),
                            "quantity_kg": entities.get("quantity_kg", 0),
                            "quality_grade": entities.get("quality_grade", "Unknown")
                        }
                        sms_notifier.send_batch_confirmation(from_number, batch_data, batch_id)
                    else:
                        # Error - send error notification
                        sms_notifier.send_error_notification(
                            from_number,
                            error or "Processing completed but no batch was created"
                        )
                except Exception as sms_error:
                    print(f"Failed to send SMS notification: {sms_error}")
        
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
