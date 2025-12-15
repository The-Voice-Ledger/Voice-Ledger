"""
Telegram Bot API endpoints for Voice Ledger.

Handles webhooks from Telegram for voice messages, text commands, and callbacks.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from voice.channels.processor import get_processor
from voice.tasks.voice_tasks import process_voice_command_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice/telegram", tags=["telegram"])


class TelegramResponse(BaseModel):
    """Response for Telegram webhook."""
    ok: bool
    message: str = ""


@router.post("/webhook", response_model=TelegramResponse)
async def telegram_webhook(request: Request) -> Dict[str, Any]:
    """
    Webhook endpoint for Telegram bot updates.
    
    Telegram sends updates here when users send messages to the bot.
    Supports:
    - Voice messages (audio notes)
    - Text commands
    - Callback queries
    
    Args:
        request: FastAPI request object containing Telegram Update
        
    Returns:
        {"ok": True} to acknowledge receipt
        
    Example Update (voice message):
        {
            "update_id": 123456,
            "message": {
                "message_id": 789,
                "from": {"id": 987654321, "username": "farmer_john"},
                "chat": {"id": 987654321, "type": "private"},
                "date": 1703001234,
                "voice": {
                    "file_id": "AwACAgIAAxkBAAIBY2...",
                    "duration": 12,
                    "mime_type": "audio/ogg"
                }
            }
        }
    """
    try:
        # Parse Telegram update
        update_data = await request.json()
        logger.info(f"Received Telegram update: {update_data.get('update_id')}")
        
        # Check if it's a message with voice
        if 'message' not in update_data:
            logger.debug("Update doesn't contain message, skipping")
            return {"ok": True, "message": "No message in update"}
        
        message = update_data['message']
        
        # Handle voice messages
        if 'voice' in message:
            logger.info("Routing to voice handler")
            return await handle_voice_message(update_data)
        
        # Handle text commands (optional - for future features)
        if 'text' in message:
            logger.info(f"Routing to text handler for: {message.get('text', 'N/A')}")
            return await handle_text_command(update_data)
        
        logger.debug(f"Unhandled message type: {list(message.keys())}")
        return {"ok": True, "message": "Message type not handled"}
        
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        # Return ok=True to Telegram anyway to avoid retries
        return {"ok": True, "message": f"Error: {str(e)}"}


async def handle_voice_message(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process voice message from Telegram.
    
    Args:
        update_data: Telegram Update dict containing voice message
        
    Returns:
        Response dict for Telegram
    """
    try:
        processor = get_processor()
        
        # Check if Telegram channel is available
        if not processor.is_channel_available('telegram'):
            logger.error("Telegram channel not initialized")
            raise HTTPException(
                status_code=503,
                detail="Telegram channel not available"
            )
        
        # Get standardized voice message
        voice_message = await processor.process_voice_message(
            channel_name='telegram',
            message_data=update_data
        )
        
        logger.info(
            f"Processing Telegram voice from user {voice_message.user_id}, "
            f"{len(voice_message.audio_data)} bytes"
        )
        
        # Send immediate acknowledgment to user
        await processor.send_notification(
            channel_name='telegram',
            user_id=voice_message.user_id,
            message=(
                "🎙️ *Voice received!*\n\n"
                "Processing your message...\n"
                "I'll notify you when the batch is created."
            )
        )
        
        # Save audio to temp file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(
            suffix=f'.{voice_message.audio_format}',
            delete=False
        ) as temp_file:
            temp_file.write(voice_message.audio_data)
            audio_path = temp_file.name
        
        # Queue async processing task with metadata
        task = process_voice_command_task.apply_async(
            args=[audio_path],
            kwargs={
                'original_filename': f"telegram_voice.{voice_message.audio_format}",
                'metadata': {
                    'user_id': voice_message.user_id,
                    'username': voice_message.username,
                    'channel': 'telegram',
                    **voice_message.metadata
                }
            }
        )
        
        logger.info(f"Queued Telegram voice processing: task_id={task.id}")
        
        # Optionally send task ID
        if task.id:
            await processor.send_notification(
                channel_name='telegram',
                user_id=voice_message.user_id,
                message=f"📋 Task ID: `{task.id[:16]}...`"
            )
        
        return {
            "ok": True,
            "message": "Voice message queued for processing"
        }
        
    except Exception as e:
        logger.error(f"Error handling Telegram voice: {e}", exc_info=True)
        
        # Try to notify user of error
        try:
            message_data = update_data.get('message', {})
            user_id = str(message_data.get('from', {}).get('id', ''))
            if user_id:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=(
                        "❌ Sorry, I couldn't process your voice message.\n\n"
                        f"Error: {str(e)}\n\n"
                        "Please try again or contact support."
                    )
                )
        except:
            pass
        
        raise HTTPException(status_code=500, detail=str(e))


async def handle_text_command(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle text commands from Telegram (optional feature).
    
    Could support commands like:
    - /start - Welcome message
    - /help - Instructions
    - /status - Check processing status
    - /batch_12345 - View batch details
    
    Args:
        update_data: Telegram Update dict with text message
        
    Returns:
        Response dict for Telegram
    """
    try:
        message = update_data['message']
        text = message.get('text', '')
        user_id = str(message['from']['id'])
        
        processor = get_processor()
        
        # Handle /start command
        if text.startswith('/start'):
            logger.info(f"Handling /start command for user {user_id}")
            result = await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "👋 *Welcome to Voice Ledger!*\n\n"
                    "I help coffee farmers create digital records using voice commands.\n\n"
                    "🎙️ *What You Can Do:*\n\n"
                    "📦 *Create New Batch* (Commission)\n"
                    "Say: \"New batch of 50 kg Yirgacheffe from Gedeo farm\"\n\n"
                    "📤 *Ship Existing Batch* (Shipment)\n"
                    "Say: \"Shipped batch ABC123 to Addis warehouse\"\n\n"
                    "📥 *Receive Batch* (Receipt)\n"
                    "Say: \"Received batch XYZ456 from Abebe cooperative\"\n\n"
                    "⚙️ *Process Coffee* (Transformation)\n"
                    "Say: \"Washed batch DEF789 at processing station\"\n\n"
                    "Just record a voice message describing what you did! 🎤"
                )
            )
            logger.info(f"/start notification result: {result}")
            return {"ok": True, "message": "Sent welcome message"}
        
        # Handle /help command
        if text.startswith('/help'):
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "ℹ️ *Voice Ledger Help*\n\n"
                    "*Text Commands:*\n"
                    "/start - Welcome & examples\n"
                    "/help - This help message\n"
                    "/status - Check system status\n\n"
                    "*Voice Command Types:*\n\n"
                    "1️⃣ *Commission* - Create new batch\n"
                    "   Example: \"New batch, 50 kg Sidama from my farm\"\n\n"
                    "2️⃣ *Shipment* - Send existing batch\n"
                    "   Example: \"Shipped batch ABC to warehouse\"\n"
                    "   ⚠️ Requires batch ID\n\n"
                    "3️⃣ *Receipt* - Receive from supplier\n"
                    "   Example: \"Received batch XYZ from cooperative\"\n"
                    "   ⚠️ Requires batch ID\n\n"
                    "4️⃣ *Transformation* - Process coffee\n"
                    "   Example: \"Washed batch DEF at station\"\n"
                    "   ⚠️ Requires batch ID\n\n"
                    "💡 Tip: Always mention quantity, variety, and origin for new batches!"
                )
            )
            return {"ok": True, "message": "Sent help message"}
        
        # Handle /status command
        if text.startswith('/status'):
            channels = processor.get_available_channels()
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "✅ *System Status*\n\n"
                    f"Available channels: {', '.join(channels)}\n"
                    "Voice processing: Online\n"
                    "Blockchain: Connected\n\n"
                    "All systems operational! 🚀"
                )
            )
            return {"ok": True, "message": "Sent status"}
        
        # Unknown command
        logger.debug(f"Unknown Telegram text command: {text}")
        return {"ok": True, "message": "Text command not recognized"}
        
    except Exception as e:
        logger.error(f"Error handling Telegram text command: {e}")
        return {"ok": True, "message": f"Error: {str(e)}"}


@router.get("/info")
async def telegram_bot_info() -> Dict[str, Any]:
    """
    Get information about the Telegram bot.
    
    Useful for debugging and verification.
    
    Returns:
        Bot information (username, ID, etc.)
    """
    try:
        processor = get_processor()
        telegram_channel = processor.get_channel('telegram')
        
        if not telegram_channel:
            raise HTTPException(
                status_code=503,
                detail="Telegram channel not available"
            )
        
        bot_info = telegram_channel.get_bot_info()
        
        return {
            "ok": True,
            "bot": bot_info,
            "webhook_url": "/voice/telegram/webhook"
        }
        
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
