"""
Twilio Voice Handler - TwiML Generation for IVR System

This module generates TwiML (Twilio Markup Language) responses for the IVR call flow.
"""

from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Record
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TwilioVoiceHandler:
    """Handles Twilio voice interactions and TwiML generation."""
    
    def __init__(self, base_url: str):
        """
        Initialize the voice handler.
        
        Args:
            base_url: Base URL for webhook callbacks (e.g., ngrok URL or production domain)
        """
        self.base_url = base_url.rstrip('/')
        logger.info(f"TwilioVoiceHandler initialized with base_url: {self.base_url}")
    
    def generate_welcome_message(self, language: str = "en", user_name: str = None) -> str:
        """
        Generate TwiML for the initial call greeting.
        
        Args:
            language: Language code (en, am for Amharic, etc.)
            user_name: Optional user's name for personalized greeting
            
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        # Personalized welcome message
        if language == "am":  # Amharic
            if user_name:
                message = f"ሰላም {user_name}። እንኳን ወደ ቮይስ ሌጀር በደህና መጡ።"
            else:
                message = "ሰላም። እንኳን ወደ ቮይስ ሌጀር በደህና መጡ።"
        else:  # English (default)
            if user_name:
                message = (
                    f"Welcome to Voice Ledger, {user_name}! "
                    "After the beep, please speak clearly and tell me about your coffee batch. "
                    "Include the quantity in kilograms, the origin, and the variety. "
                    "You will have up to 2 minutes to record. "
                    "Press any key when finished, or wait for the recording to end."
                )
            else:
                message = (
                    "Welcome to Voice Ledger. "
                    "This system helps you record coffee batch information using your voice. "
                    "After the beep, please speak clearly and state the type of coffee, "
                    "quantity in bags, quality grade, and farmer name. "
                    "You will have up to 2 minutes to record. "
                    "Press any key when finished, or wait for the recording to end."
                )
        
        response.say(message, voice='alice', language='en-US')
        response.pause(length=1)
        
        # Start recording with callback
        response.record(
            action=f"{self.base_url}/voice/ivr/recording",
            method="POST",
            max_length=120,  # 2 minutes max
            timeout=5,  # 5 seconds of silence ends recording
            transcribe=False,  # We use Whisper, not Twilio transcription
            play_beep=True,
            recording_status_callback=f"{self.base_url}/voice/ivr/recording-status",
            recording_status_callback_method="POST"
        )
        
        # Fallback if recording fails
        response.say("I did not receive a recording. Please try again. Goodbye.")
        
        return str(response)
    
    def generate_language_selection(self) -> str:
        """
        Generate TwiML for language selection menu.
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        gather = Gather(
            num_digits=1,
            action=f"{self.base_url}/voice/ivr/language-selected",
            method="POST",
            timeout=5
        )
        
        gather.say(
            "Welcome to Voice Ledger. "
            "Press 1 for English. "
            "Press 2 for Amharic. "
            "Press 3 for Oromo.",
            voice='alice',
            language='en-US'
        )
        
        response.append(gather)
        
        # If no input, default to English
        response.redirect(f"{self.base_url}/voice/ivr/incoming?lang=en")
        
        return str(response)
    
    def generate_processing_message(self, task_id: str) -> str:
        """
        Generate TwiML for "processing your recording" message.
        
        Args:
            task_id: Celery task ID for status tracking
            
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        response.say(
            "Thank you. Your recording has been received and is being processed. "
            "You will receive an SMS confirmation shortly with the batch details. "
            "Goodbye.",
            voice='alice',
            language='en-US'
        )
        
        response.hangup()
        
        return str(response)
    
    def generate_error_message(self, error_type: str = "general") -> str:
        """
        Generate TwiML for error scenarios.
        
        Args:
            error_type: Type of error (recording_failed, processing_error, authentication_failed, etc.)
            
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        error_messages = {
            "recording_failed": "We could not process your recording. Please try again later.",
            "processing_error": "There was an error processing your request. Please try again.",
            "no_recording": "No recording was received. Please call back and try again.",
            "authentication_failed": "We could not verify your phone number. Please try again later.",
            "general": "An error occurred. Please try again later."
        }
        
        message = error_messages.get(error_type, error_messages["general"])
        response.say(message, voice='alice', language='en-US')
        response.hangup()
        
        return str(response)
    
    def generate_registration_required_message(self) -> str:
        """
        Generate TwiML for unregistered phone numbers.
        Tells caller to register via Telegram first.
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        response.say(
            "Welcome to Voice Ledger. "
            "This phone number is not registered. "
            "To use this service, please register first by sending a message to our Telegram bot. "
            "Search for 'Voice Ledger Bot' on Telegram, or ask someone in your cooperative for the link. "
            "Send the slash start command and share your phone number to register. "
            "Thank you. Goodbye.",
            voice='alice',
            language='en-US'
        )
        
        response.hangup()
        
        return str(response)
    
    def generate_approval_pending_message(self) -> str:
        """
        Generate TwiML for users whose registration is pending approval.
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        response.say(
            "Welcome to Voice Ledger. "
            "Your account is pending approval. "
            "Please wait for your cooperative manager or system administrator to approve your registration. "
            "You will be notified via Telegram once approved. "
            "Thank you. Goodbye.",
            voice='alice',
            language='en-US'
        )
        
        response.hangup()
        
        return str(response)
    
    def generate_menu_response(self, digit_pressed: str) -> str:
        """
        Generate TwiML response based on user's menu selection.
        
        Args:
            digit_pressed: Digit the user pressed (1-9)
            
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        if digit_pressed == "1":
            response.say("You selected English.", voice='alice', language='en-US')
            response.redirect(f"{self.base_url}/voice/ivr/incoming?lang=en")
        elif digit_pressed == "2":
            response.say("You selected Amharic.", voice='alice', language='en-US')
            response.redirect(f"{self.base_url}/voice/ivr/incoming?lang=am")
        elif digit_pressed == "3":
            response.say("You selected Oromo.", voice='alice', language='en-US')
            response.redirect(f"{self.base_url}/voice/ivr/incoming?lang=om")
        else:
            response.say("Invalid selection. Defaulting to English.", voice='alice', language='en-US')
            response.redirect(f"{self.base_url}/voice/ivr/incoming?lang=en")
        
        return str(response)
    
    @staticmethod
    def parse_twilio_request(form_data: Dict) -> Dict:
        """
        Parse incoming Twilio webhook data.
        
        Args:
            form_data: Form data from Twilio webhook request
            
        Returns:
            Parsed data dictionary
        """
        return {
            "call_sid": form_data.get("CallSid"),
            "from_number": form_data.get("From"),
            "to_number": form_data.get("To"),
            "call_status": form_data.get("CallStatus"),
            "recording_url": form_data.get("RecordingUrl"),
            "recording_sid": form_data.get("RecordingSid"),
            "recording_duration": form_data.get("RecordingDuration"),
            "digits": form_data.get("Digits"),
        }
