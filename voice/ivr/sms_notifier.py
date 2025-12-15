"""
SMS Notifier - Send SMS confirmations via Twilio

Sends SMS notifications to farmers after their voice recordings are processed.
"""

import os
from typing import Optional, Dict
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger(__name__)


class SMSNotifier:
    """Handles SMS notifications via Twilio."""
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None
    ):
        """
        Initialize SMS notifier.
        
        Args:
            account_sid: Twilio Account SID (defaults to env var)
            auth_token: Twilio Auth Token (defaults to env var)
            from_number: Twilio phone number to send from (defaults to env var)
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not fully configured. SMS notifications will be disabled.")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
            logger.info(f"SMSNotifier initialized with number: {self.from_number}")
    
    def send_batch_confirmation(
        self,
        to_number: str,
        batch_data: Dict,
        batch_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Send SMS confirmation after batch creation.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            batch_data: Dictionary with batch details
            batch_id: Optional batch ID/GTIN
            
        Returns:
            Message SID if sent successfully, None otherwise
        """
        if not self.client:
            logger.warning(f"SMS disabled. Would send to {to_number}: Batch created successfully")
            return None
        
        try:
            # Format batch details
            coffee_type = batch_data.get('coffee_type', 'Unknown')
            quantity_bags = batch_data.get('quantity_bags', 0)
            quantity_kg = batch_data.get('quantity_kg', 0)
            quality_grade = batch_data.get('quality_grade', 'Unknown')
            
            # Compose message
            message_body = (
                f"✅ Voice Ledger: Batch recorded successfully!\n\n"
                f"Type: {coffee_type}\n"
                f"Qty: {quantity_bags} bags ({quantity_kg} kg)\n"
                f"Grade: {quality_grade}"
            )
            
            if batch_id:
                message_body += f"\nID: {batch_id}"
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"SMS sent to {to_number}: {message.sid}")
            return message.sid
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {to_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_number}: {e}")
            return None
    
    def send_processing_update(
        self,
        to_number: str,
        status: str,
        message: Optional[str] = None
    ) -> Optional[str]:
        """
        Send SMS with processing status update.
        
        Args:
            to_number: Recipient phone number
            status: Status (processing, completed, failed)
            message: Optional custom message
            
        Returns:
            Message SID if sent successfully, None otherwise
        """
        if not self.client:
            logger.warning(f"SMS disabled. Would send to {to_number}: Status {status}")
            return None
        
        try:
            status_messages = {
                "processing": "🔄 Voice Ledger: Processing your recording...",
                "completed": "✅ Voice Ledger: Processing complete!",
                "failed": "❌ Voice Ledger: Processing failed. Please try again."
            }
            
            body = message or status_messages.get(status, f"Status: {status}")
            
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"Status SMS sent to {to_number}: {message.sid}")
            return message.sid
            
        except Exception as e:
            logger.error(f"Error sending status SMS to {to_number}: {e}")
            return None
    
    def send_error_notification(
        self,
        to_number: str,
        error_details: str
    ) -> Optional[str]:
        """
        Send SMS notification about an error.
        
        Args:
            to_number: Recipient phone number
            error_details: Error description
            
        Returns:
            Message SID if sent successfully, None otherwise
        """
        if not self.client:
            logger.warning(f"SMS disabled. Would send error to {to_number}")
            return None
        
        try:
            body = (
                f"❌ Voice Ledger Error\n\n"
                f"{error_details}\n\n"
                f"Please try again or contact support."
            )
            
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"Error SMS sent to {to_number}: {message.sid}")
            return message.sid
            
        except Exception as e:
            logger.error(f"Error sending error SMS to {to_number}: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if SMS service is available."""
        return self.client is not None
