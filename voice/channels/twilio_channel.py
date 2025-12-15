"""
Twilio channel wrapper for voice calls and SMS.

Wraps existing Twilio IVR functionality to conform to the VoiceChannel interface.
"""

import os
import logging
from typing import Dict, Any, Optional

import httpx
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from voice.channels.base import VoiceChannel, VoiceMessage
from voice.ivr.sms_notifier import SMSNotifier

logger = logging.getLogger(__name__)


class TwilioChannel(VoiceChannel):
    """
    Twilio phone call integration for voice recordings.
    
    Features:
    - Receives voice recordings from phone calls (via TwiML)
    - Downloads recordings from Twilio
    - Sends SMS notifications
    - Supports multiple audio formats
    """
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None
    ):
        """
        Initialize Twilio client.
        
        Args:
            account_sid: Twilio Account SID (from env if None)
            auth_token: Twilio Auth Token (from env if None)
            phone_number: Twilio phone number (from env if None)
        """
        self.account_sid = account_sid or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = phone_number or os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([self.account_sid, self.auth_token]):
            raise ValueError(
                "Twilio credentials required. "
                "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
            )
        
        self.client = Client(self.account_sid, self.auth_token)
        self.sms_notifier = SMSNotifier(self.account_sid, self.auth_token, self.phone_number)
        
        logger.info("TwilioChannel initialized")
    
    async def receive_voice(self, message_data: Dict[str, Any]) -> VoiceMessage:
        """
        Process incoming Twilio voice recording.
        
        Args:
            message_data: Twilio webhook form data containing recording URL
            
        Returns:
            VoiceMessage with downloaded audio data
            
        Raises:
            ValueError: If recording URL is missing or download fails
        """
        try:
            # Extract recording URL
            recording_url = message_data.get('RecordingUrl')
            if not recording_url:
                raise ValueError("No RecordingUrl in Twilio webhook data")
            
            # Get caller info
            from_number = message_data.get('From', 'unknown')
            call_sid = message_data.get('CallSid', '')
            
            # Recording metadata
            recording_sid = message_data.get('RecordingSid', '')
            recording_duration = message_data.get('RecordingDuration', '0')
            
            logger.info(
                f"Receiving Twilio recording: from={from_number}, "
                f"duration={recording_duration}s, sid={recording_sid[:20]}..."
            )
            
            # Download recording with auth
            # Note: Twilio recordings require basic auth (Account SID : Auth Token)
            full_url = f"{recording_url}.wav"  # Request WAV format
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    full_url,
                    auth=(self.account_sid, self.auth_token),
                    timeout=30.0
                )
                response.raise_for_status()
                audio_bytes = response.content
            
            logger.info(f"Downloaded {len(audio_bytes)} bytes from Twilio")
            
            # Create standardized voice message
            return VoiceMessage(
                channel='twilio',
                user_id=from_number,
                audio_data=audio_bytes,
                audio_format='wav',
                metadata={
                    'from_number': from_number,
                    'call_sid': call_sid,
                    'recording_sid': recording_sid,
                    'recording_url': recording_url,
                    'duration': recording_duration,
                }
            )
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to download Twilio recording: {e}")
            raise ValueError(f"Failed to download recording: {e}")
        except Exception as e:
            logger.error(f"Error processing Twilio recording: {e}")
            raise
    
    async def send_notification(
        self, 
        user_id: str, 
        message: str,
        **kwargs
    ) -> bool:
        """
        Send SMS notification to phone number.
        
        Args:
            user_id: Phone number (E.164 format)
            message: SMS message text
            **kwargs: Additional Twilio message parameters
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.phone_number:
                logger.warning("No Twilio phone number configured, skipping SMS")
                return False
            
            result = self.client.messages.create(
                from_=self.phone_number,
                to=user_id,
                body=message,
                **kwargs
            )
            
            logger.info(f"Sent SMS to {user_id}, SID: {result.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending SMS notification: {e}")
            return False
    
    async def send_status_update(
        self,
        user_id: str,
        task_id: str,
        status: str,
        **kwargs
    ) -> bool:
        """
        Send processing status update via SMS.
        
        Args:
            user_id: Phone number
            task_id: Celery task ID
            status: Status message
            **kwargs: Additional parameters
            
        Returns:
            bool: True if sent successfully
        """
        message = f"Task {task_id[:8]}... Status: {status}"
        return await self.send_notification(user_id, message, **kwargs)
    
    def send_batch_confirmation_sms(
        self,
        to_number: str,
        batch_data: Dict[str, Any],
        batch_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Send batch confirmation using existing SMS notifier.
        
        This is a convenience method that wraps the existing SMSNotifier.
        
        Args:
            to_number: Recipient phone number
            batch_data: Batch details
            batch_id: Optional batch ID
            
        Returns:
            Message SID if successful, None otherwise
        """
        return self.sms_notifier.send_batch_confirmation(
            to_number=to_number,
            batch_data=batch_data,
            batch_id=batch_id
        )
