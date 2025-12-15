"""
Base abstraction for voice input channels.

Defines the interface that all voice channels must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class VoiceMessage:
    """Standardized voice message format across all channels."""
    
    channel: str  # "twilio", "telegram", "whatsapp"
    user_id: str  # Channel-specific user identifier
    audio_data: bytes  # Raw audio bytes
    audio_format: str  # "wav", "mp3", "ogg", etc.
    
    # Optional metadata
    metadata: Optional[Dict[str, Any]] = None
    username: Optional[str] = None
    language: Optional[str] = None
    
    def __post_init__(self):
        """Ensure metadata is a dict."""
        if self.metadata is None:
            self.metadata = {}


class VoiceChannel(ABC):
    """
    Base class for all voice input channels.
    
    Each channel implementation must handle:
    1. Receiving voice messages in channel-specific format
    2. Converting to standardized VoiceMessage format
    3. Sending notifications back to users
    4. Sending status updates during processing
    """
    
    @abstractmethod
    async def receive_voice(self, message_data: Dict[str, Any]) -> VoiceMessage:
        """
        Process incoming voice message from channel-specific format.
        
        Args:
            message_data: Raw message data from the channel (webhook payload)
            
        Returns:
            VoiceMessage: Standardized voice message object
            
        Raises:
            ValueError: If message data is invalid or missing required fields
        """
        pass
    
    @abstractmethod
    async def send_notification(
        self, 
        user_id: str, 
        message: str,
        **kwargs
    ) -> bool:
        """
        Send a notification message back to the user.
        
        Args:
            user_id: Channel-specific user identifier
            message: Text message to send
            **kwargs: Channel-specific options (e.g., parse_mode for Telegram)
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_status_update(
        self,
        user_id: str,
        task_id: str,
        status: str,
        **kwargs
    ) -> bool:
        """
        Send a processing status update to the user.
        
        Args:
            user_id: Channel-specific user identifier
            task_id: Task ID being processed
            status: Current status message
            **kwargs: Channel-specific options
            
        Returns:
            bool: True if update sent successfully, False otherwise
        """
        pass
    
    def get_channel_name(self) -> str:
        """Return the name of this channel."""
        return self.__class__.__name__.replace('Channel', '').lower()
