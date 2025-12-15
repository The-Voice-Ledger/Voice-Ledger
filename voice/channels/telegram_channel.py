"""
Telegram Bot channel for voice message processing.

Handles voice notes sent to the Telegram bot, downloads audio,
and sends notifications back to users.
"""

import os
import logging
from typing import Dict, Any, Optional
from io import BytesIO

from telegram import Bot, Update
from telegram.error import TelegramError

from voice.channels.base import VoiceChannel, VoiceMessage

logger = logging.getLogger(__name__)


class TelegramChannel(VoiceChannel):
    """
    Telegram Bot API integration for voice messages.
    
    Features:
    - Receives voice notes (OGG Opus format)
    - Downloads audio automatically
    - Sends text notifications
    - Supports real-time status updates
    - Handles Telegram-specific formatting (Markdown/HTML)
    """
    
    def __init__(self, bot_token: Optional[str] = None):
        """
        Initialize Telegram bot.
        
        Args:
            bot_token: Telegram bot token from @BotFather.
                      If None, reads from TELEGRAM_BOT_TOKEN env variable.
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError(
                "Telegram bot token required. "
                "Set TELEGRAM_BOT_TOKEN environment variable or pass bot_token parameter."
            )
        
        self.bot = Bot(token=self.bot_token)
        logger.info("TelegramChannel initialized")
    
    async def receive_voice(self, message_data: Dict[str, Any]) -> VoiceMessage:
        """
        Process incoming Telegram voice note.
        
        Args:
            message_data: Telegram Update dict containing voice message
            
        Returns:
            VoiceMessage with audio data in OGG Opus format
            
        Raises:
            ValueError: If message doesn't contain voice data
        """
        try:
            # Extract message from update
            if 'message' not in message_data:
                raise ValueError("No 'message' field in Telegram update")
            
            message = message_data['message']
            
            if 'voice' not in message:
                raise ValueError("Message doesn't contain voice note")
            
            # Get voice file info
            voice = message['voice']
            file_id = voice['file_id']
            duration = voice.get('duration', 0)
            
            # Get user info
            from_user = message.get('from', {})
            user_id = str(from_user.get('id', 'unknown'))
            username = from_user.get('username')
            first_name = from_user.get('first_name', '')
            last_name = from_user.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()
            
            # Get message metadata
            chat_id = message.get('chat', {}).get('id')
            message_id = message.get('message_id')
            date = message.get('date')
            
            logger.info(
                f"Receiving Telegram voice note: user={user_id} ({username}), "
                f"duration={duration}s, file_id={file_id[:20]}..."
            )
            
            # Download voice file
            file = await self.bot.get_file(file_id)
            audio_bytes = await file.download_as_bytearray()
            
            logger.info(f"Downloaded {len(audio_bytes)} bytes from Telegram")
            
            # Create standardized voice message
            return VoiceMessage(
                channel='telegram',
                user_id=user_id,
                audio_data=bytes(audio_bytes),
                audio_format='ogg',  # Telegram uses OGG Opus
                username=username or full_name,
                metadata={
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'duration': duration,
                    'file_id': file_id,
                    'date': date,
                    'username': username,
                    'full_name': full_name,
                }
            )
            
        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            raise ValueError(f"Failed to download Telegram voice: {e}")
        except Exception as e:
            logger.error(f"Error processing Telegram voice: {e}")
            raise
    
    async def send_notification(
        self, 
        user_id: str, 
        message: str,
        parse_mode: Optional[str] = 'Markdown',
        **kwargs
    ) -> bool:
        """
        Send notification message to Telegram user.
        
        Args:
            user_id: Telegram chat ID (can be user or group)
            message: Text message to send
            parse_mode: 'Markdown', 'HTML', or None for plain text
            **kwargs: Additional Telegram send_message parameters
            
        Returns:
            bool: True if sent successfully
        """
        try:
            chat_id = int(user_id)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
                **kwargs
            )
            
            logger.info(f"Sent Telegram notification to {user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    async def send_status_update(
        self,
        user_id: str,
        task_id: str,
        status: str,
        **kwargs
    ) -> bool:
        """
        Send processing status update to Telegram user.
        
        Args:
            user_id: Telegram chat ID
            task_id: Celery task ID
            status: Status message
            **kwargs: Additional parameters
            
        Returns:
            bool: True if sent successfully
        """
        # Format status with emoji for better UX
        emoji_map = {
            'PENDING': '⏳',
            'PROCESSING': '🔄',
            'SUCCESS': '✅',
            'FAILURE': '❌',
            'RETRY': '🔁',
        }
        
        emoji = emoji_map.get(status.upper(), '📝')
        
        message = f"{emoji} *Task Status*\n\n"
        message += f"Task ID: `{task_id[:16]}...`\n"
        message += f"Status: {status}"
        
        return await self.send_notification(user_id, message, **kwargs)
    
    async def send_batch_confirmation(
        self,
        user_id: str,
        batch_info: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Send rich batch creation confirmation with details.
        
        Args:
            user_id: Telegram chat ID
            batch_info: Batch details (id, variety, quantity, etc.)
            **kwargs: Additional parameters
            
        Returns:
            bool: True if sent successfully
        """
        message = "✅ *Batch Created Successfully!*\n\n"
        message += f"🆔 Batch ID: `{batch_info.get('id', 'N/A')}`\n"
        message += f"☕ Variety: *{batch_info.get('variety', 'N/A')}*\n"
        message += f"📦 Quantity: *{batch_info.get('quantity', 'N/A')} kg*\n"
        
        if 'farm' in batch_info:
            message += f"🏡 Farm: {batch_info['farm']}\n"
        
        if 'blockchain_tx' in batch_info:
            tx = batch_info['blockchain_tx'][:16]
            message += f"\n🔗 Blockchain TX: `{tx}...`\n"
        
        message += "\n💡 *Next Steps:*\n"
        message += "• View batch: /batch\\_" + str(batch_info.get('id', ''))[:8] + "\n"
        message += "• Create DPP: /dpp\n"
        message += "• Add another: Send voice note"
        
        return await self.send_notification(user_id, message, **kwargs)
    
    def get_bot_info(self) -> Dict[str, Any]:
        """
        Get information about the bot (for testing/debugging).
        
        Returns:
            Dict with bot username, id, name
        """
        import asyncio
        try:
            bot_data = asyncio.run(self.bot.get_me())
            return {
                'id': bot_data.id,
                'username': bot_data.username,
                'first_name': bot_data.first_name,
                'can_join_groups': bot_data.can_join_groups,
                'can_read_all_group_messages': bot_data.can_read_all_group_messages,
            }
        except Exception as e:
            logger.error(f"Failed to get bot info: {e}")
            return {}
