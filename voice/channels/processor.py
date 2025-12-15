"""
Multi-channel voice processor.

Coordinates voice message processing across different channels (Twilio, Telegram, etc.)
"""

import os
import logging
from typing import Dict, Any, Optional
from io import BytesIO

from voice.channels.base import VoiceChannel, VoiceMessage
from voice.channels.twilio_channel import TwilioChannel
from voice.channels.telegram_channel import TelegramChannel

logger = logging.getLogger(__name__)


class MultiChannelProcessor:
    """
    Unified processor for voice messages from multiple channels.
    
    Handles:
    - Channel routing
    - Voice message standardization
    - Cross-channel notifications
    - Task status updates
    """
    
    def __init__(self):
        """Initialize all available channels."""
        self.channels: Dict[str, VoiceChannel] = {}
        
        # Initialize Twilio if credentials available
        try:
            if os.getenv('TWILIO_ACCOUNT_SID'):
                self.channels['twilio'] = TwilioChannel()
                logger.info("Twilio channel registered")
        except Exception as e:
            logger.warning(f"Failed to initialize Twilio channel: {e}")
        
        # Initialize Telegram if token available
        try:
            if os.getenv('TELEGRAM_BOT_TOKEN'):
                self.channels['telegram'] = TelegramChannel()
                logger.info("Telegram channel registered")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram channel: {e}")
        
        if not self.channels:
            logger.warning("No voice channels initialized!")
    
    def get_channel(self, channel_name: str) -> Optional[VoiceChannel]:
        """
        Get a specific channel handler.
        
        Args:
            channel_name: 'twilio', 'telegram', etc.
            
        Returns:
            VoiceChannel instance or None if not available
        """
        return self.channels.get(channel_name.lower())
    
    def is_channel_available(self, channel_name: str) -> bool:
        """Check if a channel is available."""
        return channel_name.lower() in self.channels
    
    async def process_voice_message(
        self,
        channel_name: str,
        message_data: Dict[str, Any]
    ) -> VoiceMessage:
        """
        Process voice message from any channel.
        
        Args:
            channel_name: Source channel ('twilio', 'telegram', etc.)
            message_data: Raw webhook/message data from the channel
            
        Returns:
            VoiceMessage: Standardized voice message object
            
        Raises:
            ValueError: If channel not available or processing fails
        """
        channel = self.get_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not available")
        
        logger.info(f"Processing voice message from {channel_name}")
        
        # Convert channel-specific format to standard VoiceMessage
        voice_message = await channel.receive_voice(message_data)
        
        logger.info(
            f"Received voice: channel={voice_message.channel}, "
            f"user={voice_message.user_id}, "
            f"format={voice_message.audio_format}, "
            f"size={len(voice_message.audio_data)} bytes"
        )
        
        return voice_message
    
    async def send_notification(
        self,
        channel_name: str,
        user_id: str,
        message: str,
        **kwargs
    ) -> bool:
        """
        Send notification through specific channel.
        
        Args:
            channel_name: Target channel
            user_id: Channel-specific user ID
            message: Message to send
            **kwargs: Channel-specific options
            
        Returns:
            bool: True if sent successfully
        """
        channel = self.get_channel(channel_name)
        if not channel:
            logger.warning(f"Cannot send notification: {channel_name} not available")
            return False
        
        return await channel.send_notification(user_id, message, **kwargs)
    
    async def send_status_update(
        self,
        channel_name: str,
        user_id: str,
        task_id: str,
        status: str,
        **kwargs
    ) -> bool:
        """
        Send task status update through specific channel.
        
        Args:
            channel_name: Target channel
            user_id: Channel-specific user ID
            task_id: Celery task ID
            status: Status message
            **kwargs: Channel-specific options
            
        Returns:
            bool: True if sent successfully
        """
        channel = self.get_channel(channel_name)
        if not channel:
            return False
        
        return await channel.send_status_update(user_id, task_id, status, **kwargs)
    
    async def broadcast_notification(
        self,
        user_channels: Dict[str, str],
        message: str,
        **kwargs
    ) -> Dict[str, bool]:
        """
        Send notification to user across multiple channels.
        
        Useful for important notifications that should reach user
        through all their connected channels.
        
        Args:
            user_channels: Dict mapping channel_name -> user_id
                          e.g., {'telegram': '12345', 'twilio': '+1234567890'}
            message: Message to broadcast
            **kwargs: Channel-specific options
            
        Returns:
            Dict mapping channel_name -> success (bool)
        """
        results = {}
        
        for channel_name, user_id in user_channels.items():
            success = await self.send_notification(
                channel_name, user_id, message, **kwargs
            )
            results[channel_name] = success
        
        return results
    
    def get_available_channels(self) -> list:
        """Get list of available channel names."""
        return list(self.channels.keys())
    
    def get_channel_info(self) -> Dict[str, Any]:
        """Get information about all available channels."""
        info = {}
        for name, channel in self.channels.items():
            info[name] = {
                'name': name,
                'class': channel.__class__.__name__,
                'available': True,
            }
        return info


# Global processor instance
_processor: Optional[MultiChannelProcessor] = None


def get_processor() -> MultiChannelProcessor:
    """
    Get the global MultiChannelProcessor instance.
    
    Creates a new instance if one doesn't exist yet.
    
    Returns:
        MultiChannelProcessor: Global processor instance
    """
    global _processor
    if _processor is None:
        _processor = MultiChannelProcessor()
    return _processor
