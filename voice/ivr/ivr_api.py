"""
IVR API - Webhook endpoints for Twilio voice calls

These endpoints receive webhooks from Twilio when:
1. A call comes in (incoming call)
2. Recording is completed
3. Recording status updates
"""

from fastapi import APIRouter, Request, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import Response
from typing import Optional
import logging
import os
import httpx
from pathlib import Path
import tempfile

from voice.ivr.twilio_handlers import TwilioVoiceHandler
from voice.ivr.sms_notifier import SMSNotifier
from voice.tasks.voice_tasks import process_voice_command_task

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/voice/ivr", tags=["IVR"])

# Initialize handlers
# Base URL should be set via environment variable (ngrok URL or production domain)
BASE_URL = os.getenv("NGROK_URL", "https://your-domain.com")
voice_handler = TwilioVoiceHandler(base_url=BASE_URL)
sms_notifier = SMSNotifier()


@router.post("/incoming")
async def handle_incoming_call(
    request: Request,
    lang: Optional[str] = "en"
):
    """
    Handle incoming Twilio voice call.
    
    This is the initial webhook when a call comes in.
    Authenticates caller by phone number before allowing recording.
    
    Args:
        lang: Language code (en, am, om)
    """
    # Get form data from Twilio
    form_data = await request.form()
    call_data = voice_handler.parse_twilio_request(dict(form_data))
    
    from_number = call_data['from_number']
    
    logger.info(f"Incoming call from {from_number} to {call_data['to_number']}")
    logger.info(f"Call SID: {call_data['call_sid']}, Status: {call_data['call_status']}")
    
    # AUTHENTICATE: Check if phone number is registered
    from database.models import UserIdentity
    from database.connection import get_db
    
    with get_db() as db:
        user = db.query(UserIdentity).filter_by(phone_number=from_number).first()
        
        if not user:
            # Unregistered phone number - reject call
            logger.warning(f"Unregistered phone attempted IVR call: {from_number}")
            twiml = voice_handler.generate_registration_required_message()
            return Response(content=twiml, media_type="application/xml")
        
        if not user.is_approved:
            # User exists but not approved
            logger.warning(f"Unapproved user attempted IVR call: {from_number}")
            twiml = voice_handler.generate_approval_pending_message()
            return Response(content=twiml, media_type="application/xml")
        
        # Authenticated - user exists and is approved
        logger.info(f"Authenticated IVR call from {user.telegram_username} (ID: {user.id}, DID: {user.did[:20]}...)")
        
        # Generate welcome TwiML with user's name
        user_name = user.telegram_first_name or user.telegram_username or "user"
        twiml = voice_handler.generate_welcome_message(
            language=lang,
            user_name=user_name
        )
        
        return Response(content=twiml, media_type="application/xml")


@router.post("/recording")
async def handle_recording_complete(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle recording completion webhook from Twilio.
    
    When the caller finishes recording, Twilio sends the recording URL here.
    We download the audio, queue it for processing, and return TwiML confirmation.
    """
    # Get form data
    form_data = await request.form()
    call_data = voice_handler.parse_twilio_request(dict(form_data))
    
    recording_url = call_data.get("recording_url")
    recording_sid = call_data.get("recording_sid")
    from_number = call_data.get("from_number")
    call_sid = call_data.get("call_sid")
    
    logger.info(f"Recording complete: {recording_sid}")
    logger.info(f"Recording URL: {recording_url}")
    logger.info(f"Duration: {call_data.get('recording_duration')} seconds")
    
    if not recording_url:
        logger.error("No recording URL received")
        twiml = voice_handler.generate_error_message("no_recording")
        return Response(content=twiml, media_type="application/xml")
    
    # AUTHENTICATE: Verify caller is registered (should have passed /incoming check)
    from database.models import UserIdentity
    from database.connection import get_db
    
    with get_db() as db:
        user = db.query(UserIdentity).filter_by(phone_number=from_number).first()
        
        if not user:
            # Shouldn't happen (we rejected in /incoming), but safety check
            logger.error(f"Recording received from unregistered number: {from_number}")
            twiml = voice_handler.generate_error_message("authentication_failed")
            return Response(content=twiml, media_type="application/xml")
        
        logger.info(f"Processing recording from authenticated user: {user.telegram_username} (ID: {user.id})")
    
    try:
        # Download the recording from Twilio
        # Twilio recordings need authentication
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        # Add .wav extension to get WAV format
        audio_url = f"{recording_url}.wav"
        
        # Download audio file
        async with httpx.AsyncClient(auth=(account_sid, auth_token)) as client:
            response = await client.get(audio_url)
            response.raise_for_status()
            audio_data = response.content
        
        # Save to temporary file
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"ivr_recording_{recording_sid}.wav"
        
        with open(temp_file, "wb") as f:
            f.write(audio_data)
        
        logger.info(f"Recording saved to: {temp_file}")
        
        # Queue for async processing with authenticated user context
        task = process_voice_command_task.delay(
            str(temp_file),
            metadata={
                "source": "ivr",
                "channel": "ivr",
                "user_id": user.id,  # Database ID for batch linking
                "user_did": user.did,  # DID for credential issuance
                "telegram_user_id": user.telegram_user_id,  # For notifications
                "username": user.telegram_username,
                "first_name": user.telegram_first_name,
                "phone_number": from_number,
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "recording_duration": call_data.get("recording_duration")
            }
        )
        
        logger.info(f"Queued processing task: {task.id}")
        
        # Schedule SMS notification in background
        if from_number and sms_notifier.is_available():
            background_tasks.add_task(
                sms_notifier.send_processing_update,
                to_number=from_number,
                status="processing"
            )
        
        # Generate "thank you" TwiML
        twiml = voice_handler.generate_processing_message(task_id=task.id)
        
        # Store task_id and phone number for completion callback
        # (In production, you'd store this in Redis or database)
        # For now, we'll handle completion in the Celery task
        
        return Response(content=twiml, media_type="application/xml")
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to download recording: {e}")
        twiml = voice_handler.generate_error_message("recording_failed")
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing recording: {e}", exc_info=True)
        twiml = voice_handler.generate_error_message("processing_error")
        return Response(content=twiml, media_type="application/xml")


@router.post("/recording-status")
async def handle_recording_status(request: Request):
    """
    Handle recording status callback from Twilio.
    
    Twilio sends status updates (in-progress, completed, failed) here.
    This is optional monitoring - main processing happens in /recording endpoint.
    """
    form_data = await request.form()
    
    recording_sid = form_data.get("RecordingSid")
    recording_status = form_data.get("RecordingStatus")
    recording_url = form_data.get("RecordingUrl")
    
    logger.info(f"Recording status update: {recording_sid} -> {recording_status}")
    
    if recording_status == "completed":
        logger.info(f"Recording available at: {recording_url}")
    elif recording_status == "failed":
        logger.error(f"Recording failed: {recording_sid}")
    
    # Return 200 OK (Twilio doesn't need TwiML response for status callbacks)
    return {"status": "received"}


@router.post("/language-selected")
async def handle_language_selection(request: Request):
    """
    Handle language selection from DTMF menu.
    
    If language selection menu is enabled, this processes the user's choice.
    """
    form_data = await request.form()
    digits = form_data.get("Digits", "1")
    
    logger.info(f"Language selection: {digits}")
    
    twiml = voice_handler.generate_menu_response(digits)
    return Response(content=twiml, media_type="application/xml")


@router.get("/health")
async def ivr_health_check():
    """Health check endpoint for IVR system."""
    return {
        "status": "healthy",
        "service": "voice-ledger-ivr",
        "base_url": BASE_URL,
        "sms_available": sms_notifier.is_available()
    }
