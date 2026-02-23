"""
Telegram Bot API endpoints for Voice Ledger.

Handles webhooks from Telegram for voice messages, text commands, and callbacks.
"""

import logging
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from pathlib import Path

from voice.channels.processor import get_processor
from voice.tasks.voice_tasks import process_voice_command_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice/telegram", tags=["telegram"])


def is_maintenance_mode() -> bool:
    """Check if system is in maintenance mode."""
    try:
        maintenance_file = Path(__file__).parent.parent.parent / ".maintenance"
        if maintenance_file.exists():
            content = maintenance_file.read_text().strip()
            # Check if MAINTENANCE_MODE=True
            for line in content.split('\n'):
                if line.startswith('MAINTENANCE_MODE='):
                    value = line.split('=')[1].strip()
                    return value.lower() in ('true', '1', 'yes')
        return False
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        return False


async def send_maintenance_message(chat_id: int):
    """Send maintenance message to user."""
    try:
        from voice.channels.telegram_channel import send_telegram_message
        
        message = (
            "🔧 *System Under Maintenance*\n\n"
            "The Voice Ledger system is currently undergoing maintenance. "
            "We apologize for any inconvenience.\n\n"
            "Please try again later. Thank you for your patience!"
        )
        
        await send_telegram_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Sent maintenance message to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error sending maintenance message: {e}")


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
        # Check maintenance mode first
        if is_maintenance_mode():
            logger.info("System in maintenance mode, sending maintenance message")
            # Get chat_id from update
            update_data = await request.json()
            if 'message' in update_data:
                chat_id = update_data['message']['chat']['id']
                await send_maintenance_message(chat_id)
            elif 'callback_query' in update_data:
                chat_id = update_data['callback_query']['message']['chat']['id']
                await send_maintenance_message(chat_id)
            return {"ok": True, "message": "Maintenance mode active"}
        
        # Parse Telegram update
        update_data = await request.json()
        logger.info(f"Received Telegram update: {update_data.get('update_id')}")
        
        # Handle callback queries (inline keyboard buttons)
        if 'callback_query' in update_data:
            logger.info("Routing to callback query handler")
            return await handle_callback_query(update_data)
        
        # Check if it's a message
        if 'message' not in update_data:
            logger.debug("Update doesn't contain message, skipping")
            return {"ok": True, "message": "No message in update"}
        
        message = update_data['message']
        
        # Handle contact sharing (phone number registration)
        if 'contact' in message:
            logger.info("Routing to contact handler (phone registration)")
            return await handle_contact_shared(update_data)
        
        # Handle photo messages (for farm GPS verification)
        if 'photo' in message:
            logger.info("Routing to photo handler (GPS verification)")
            return await handle_photo_message(update_data)
        
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


async def handle_contact_shared(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle when user shares their contact (phone number).
    
    Note: Phone collection now happens during /register flow.
    This handler is for users who share contact outside of registration.
    
    Args:
        update_data: Telegram Update dict containing contact
        
    Returns:
        Response dict for Telegram
    """
    try:
        message = update_data.get('message', {})
        contact = message.get('contact', {})
        user = message.get('from', {})
        
        user_id = user.get('id')
        phone_number = contact.get('phone_number')
        
        if not phone_number:
            logger.error("Contact shared but no phone number found")
            return {"ok": True, "message": "No phone number in contact"}
        
        # Ensure phone is in E.164 format (+country_code + number)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        logger.info(f"User {user_id} shared phone outside registration: {phone_number}")
        
        # Check if user is in registration flow
        from voice.telegram.register_handler import conversation_states, STATE_PHONE
        from telegram import ReplyKeyboardRemove
        
        if user_id in conversation_states and conversation_states[user_id]['state'] == STATE_PHONE:
            # User is in registration flow - store phone in conversation state
            conversation_states[user_id]['data']['phone_number'] = phone_number
            
            # Import and call the registration text handler to continue flow
            from voice.telegram.register_handler import handle_registration_text
            response = await handle_registration_text(user_id, phone_number)
            
            # Send response and dismiss the share-phone keyboard
            processor = get_processor()
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=response.get('message', '✅ Phone number received'),
                parse_mode=response.get('parse_mode'),
                reply_markup=ReplyKeyboardRemove()
            )
            
            return {"ok": True, "message": "Phone processed in registration"}
        
        # User shared contact outside of registration - acknowledge and suggest /register
        processor = get_processor()
        await processor.send_notification(
            channel_name='telegram',
            user_id=user_id,
            message=(
                f"✅ Thanks for sharing your phone number!\n\n"
                f"📱 Phone: {phone_number}\n\n"
                f"To complete registration and start using Voice Ledger, please send:\n"
                f"👉 /register\n\n"
                f"This will set up your account with your role (farmer, manager, exporter, or buyer)."
            ),
            parse_mode=None,
            send_voice=False  # Acknowledgment - text only
        )
        
        return {"ok": True, "message": "Contact acknowledged"}
            
    except Exception as e:
        logger.error(f"Error handling contact: {e}", exc_info=True)
        return {"ok": True, "message": f"Error: {str(e)}"}



async def handle_photo_message(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle photo upload from Telegram (for GPS verification during farmer registration).
    
    Args:
        update_data: Telegram Update dict containing photo
        
    Returns:
        Response dict for Telegram
    """
    try:
        message = update_data.get('message', {})
        user = message.get('from', {})
        photo_array = message.get('photo', [])
        
        user_id = user.get('id')
        
        if not photo_array:
            logger.error("Photo message but no photo array found")
            return {"ok": True, "message": "No photo in message"}
        
        # Get largest photo (last in array)
        photo = photo_array[-1]
        photo_file_id = photo.get('file_id')
        
        logger.info(f"User {user_id} sent photo: {photo_file_id}")
        
        # Check if user is in registration flow expecting a photo
        from voice.telegram.register_handler import (
            conversation_states, 
            STATE_UPLOAD_FARM_PHOTO,
            handle_farm_photo_upload
        )
        from voice.telegram.batch_photo_sessions import get_batch_photo_session, clear_batch_photo_session
        
        # Priority 1: Check for farmer registration photo
        if user_id in conversation_states and conversation_states[user_id]['state'] == STATE_UPLOAD_FARM_PHOTO:
            # Get file URL from Telegram
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN not configured")
            
            # Get file path from Telegram API
            import requests
            file_info_response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={'file_id': photo_file_id},
                timeout=10
            )
            file_info_response.raise_for_status()
            file_info = file_info_response.json()
            
            if not file_info.get('ok'):
                logger.error(f"Failed to get file info: {file_info}")
                return {"ok": True, "message": "Failed to get file info"}
            
            file_path = file_info['result']['file_path']
            photo_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            
            # Process registration photo with GPS extraction
            response = await handle_farm_photo_upload(user_id, photo_file_id, photo_url)
            
            # Send response to user
            processor = get_processor()
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=response.get('message', '✅ Photo processed'),
                parse_mode=response.get('parse_mode'),
                inline_keyboard=response.get('inline_keyboard')
            )
            
            return {"ok": True, "message": "Registration photo processed"}
        
        # Priority 2: Check for batch verification photo
        batch_session = get_batch_photo_session(user_id)
        if batch_session:
            # User just created a batch and is uploading verification photo
            batch_id = batch_session['batch_id']
            batch_number = batch_session['batch_number']
            
            logger.info(f"Processing batch verification photo for batch {batch_id}")
            
            # Get file URL from Telegram
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN not configured")
            
            # Get file path and download photo
            import requests
            file_info_response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={'file_id': photo_file_id},
                timeout=10
            )
            file_info_response.raise_for_status()
            file_info = file_info_response.json()
            
            if not file_info.get('ok'):
                logger.error(f"Failed to get file info: {file_info}")
                return {"ok": True, "message": "Failed to get file info"}
            
            file_path = file_info['result']['file_path']
            photo_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            
            # Download photo
            photo_response = requests.get(photo_url, timeout=10)
            photo_response.raise_for_status()
            
            # Process with batch photo API
            from voice.verification.batch_photo_api import upload_batch_verification_photo
            from database.models import SessionLocal
            from io import BytesIO
            from fastapi import UploadFile
            
            db = SessionLocal()
            try:
                # Create UploadFile-like object
                photo_bytes = BytesIO(photo_response.content)
                photo_bytes.name = f"batch_{batch_id}_verification.jpg"
                
                # Upload to batch verification API
                result = await upload_batch_verification_photo(
                    batch_id=batch_id,
                    photo=UploadFile(file=photo_bytes, filename=photo_bytes.name),
                    db=db
                )
                
                # Clear session
                clear_batch_photo_session(user_id)
                
                # Get user language
                from database.models import UserIdentity
                user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
                lang = user.preferred_language if user else 'en'
                
                # Send success message
                if lang == 'am':
                    message = (
                        f"✅ *ማረጋገጫ ተሳክቷል!*\n\n"
                        f"የእርስዎ ፎቶ ለ {batch_number} ተመዝግቧል።\n\n"
                        f"📍 GPS: {result['gps']['latitude']:.6f}, {result['gps']['longitude']:.6f}\n"
                    )
                    if result.get('distance_from_farm_km') is not None:
                        message += f"📏 ከእርሻ ርቀት: {result['distance_from_farm_km']:.1f} ኪ.ሜ\n"
                    message += f"\n🌍 *EUDR የማክበር ዝግጁ!*"
                else:
                    message = (
                        f"✅ *Verification Successful!*\n\n"
                        f"Photo recorded for {batch_number}\n\n"
                        f"📍 GPS: {result['gps']['latitude']:.6f}, {result['gps']['longitude']:.6f}\n"
                    )
                    if result.get('distance_from_farm_km') is not None:
                        message += f"📏 Distance from farm: {result['distance_from_farm_km']:.1f} km\n"
                    message += f"\n🌍 *Ready for EUDR compliance!*"
                
                processor = get_processor()
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=message,
                    parse_mode='Markdown'
                )
                
                return {"ok": True, "message": "Batch verification photo processed"}
                
            except Exception as e:
                logger.error(f"Error processing batch verification photo: {e}", exc_info=True)
                
                # Send error message
                processor = get_processor()
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=f"❌ Failed to process photo: {str(e)}\n\nPlease try again with a photo that has GPS data.",
                    send_voice=False  # Error message - text only
                )
                
                return {"ok": True, "message": f"Error: {str(e)}"}
            finally:
                db.close()
        
        # Not in registration or batch flow - send help message
        processor = get_processor()
        await processor.send_notification(
            channel_name='telegram',
            user_id=user_id,
            message=(
                "📸 Photo received, but I'm not sure what to do with it.\n\n"
                "To add GPS verification:\n"
                "• Use /register for farmer registration\n"
                "• Record a batch first, then upload photo for verification"
            ),
            send_voice=False  # System notification - text only
        )
        return {"ok": True, "message": "Photo not expected"}
        
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
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
        
        # Send immediate acknowledgment to user (TEXT ONLY - no voice needed for system notification)
        await processor.send_notification(
            channel_name='telegram',
            user_id=voice_message.user_id,
            message=(
                "🎙️ *Voice received!*\n\n"
                "Processing your message...\n"
                "I'll notify you when the batch is created."
            ),
            send_voice=False  # System notification - no need for voice
        )
        
        # Save audio to temp file for processing
        import tempfile
        import os
        
        # Use persistent temp directory on Railway
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
            # Railway: Write file directly to Celery task to avoid race condition
            import base64
            import json
            
            # Encode audio data as base64 to pass in task
            audio_b64 = base64.b64encode(voice_message.audio_data).decode('utf-8')
            
            # Queue async processing task with audio data embedded
            task = process_voice_command_task.apply_async(
                args=[],  # No file path
                kwargs={
                    'original_filename': f"telegram_voice.{voice_message.audio_format}",
                    'audio_data_b64': audio_b64,  # Pass audio data directly
                    'audio_format': voice_message.audio_format,
                    'metadata': {
                        'user_id': voice_message.user_id,
                        'username': voice_message.username,
                        'channel': 'telegram',
                        'audio_path': 'embedded_in_task',  # Debug marker
                        **voice_message.metadata
                    }
                }
            )
        else:
            # Local: Use regular temp file
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
                        'audio_path': audio_path,  # Add actual path for debugging
                        **voice_message.metadata
                    }
                }
            )
        
        logger.info(f"Queued Telegram voice processing: task_id={task.id}")
        
        # Optionally send task ID (TEXT ONLY - task IDs are useless in voice)
        if task.id:
            await processor.send_notification(
                channel_name='telegram',
                user_id=voice_message.user_id,
                message=f"📋 Task ID: `{task.id[:16]}...`",
                send_voice=False  # Task IDs have no value in voice format
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


# Role-based access control configuration
COMMAND_ROLES = {
    'commission': ['FARMER', 'COOPERATIVE_MANAGER'],
    'ship': ['FARMER', 'COOPERATIVE_MANAGER', 'EXPORTER', 'TRADER'],
    'receive': ['COOPERATIVE_MANAGER', 'EXPORTER', 'TRADER', 'BUYER'],
    'transform': ['COOPERATIVE_MANAGER', 'TRADER'],
    'pack': ['COOPERATIVE_MANAGER', 'EXPORTER'],
    'unpack': ['TRADER'],
    'split': ['TRADER'],
    'verify': ['COOPERATIVE_MANAGER'],
    'export': ['COOPERATIVE_MANAGER', 'EXPORTER'],
    'dpp': ['COOPERATIVE_MANAGER', 'EXPORTER', 'TRADER']
}


async def check_command_access(user_id: str, command: str, processor) -> tuple[bool, str, str]:
    """
    Check if user has access to execute a command based on their role.
    
    Args:
        user_id: Telegram user ID
        command: Command name (without /)
        processor: Channel processor for sending messages
        
    Returns:
        Tuple of (has_access: bool, user_role: str, error_message: str)
    """
    if command not in COMMAND_ROLES:
        return True, None, None  # No access control for this command
    
    from ssi.user_identity import get_user_by_telegram_id
    from database.models import SessionLocal
    
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(user_id, db_session=db)
        if not user:
            return False, None, "❌ No identity found. Use /register to create one."
        
        user_role = user.role
        required_roles = COMMAND_ROLES[command]
        
        if user_role not in required_roles:
            roles_display = ', '.join([r.replace('_', ' ').title() for r in required_roles])
            error_msg = (
                f"❌ *Permission Denied*\n\n"
                f"Only {roles_display} can use /{command}.\n"
                f"Your role: {user_role.replace('_', ' ').title()}"
            )
            return False, user_role, error_msg
        
        if not user.is_approved:
            error_msg = (
                "⏳ *Approval Pending*\n\n"
                "Your account is pending approval. Please contact an administrator."
            )
            return False, user_role, error_msg
        
        return True, user_role, None
    finally:
        db.close()


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
            
            # Check if it's a deep link with parameter (e.g., /start verify_VRF-...)
            parts = text.split(' ', 1)
            if len(parts) > 1 and parts[1].startswith('verify_'):
                # Verification deep link
                from voice.telegram.verification_handler import handle_verify_deeplink
                token = parts[1].replace('verify_', '')
                username = message.get('from', {}).get('username', '')
                
                logger.info(f"Handling verification deep link for token: {token}")
                response = await handle_verify_deeplink(
                    user_id=int(user_id),
                    username=username,
                    token=token
                )
                
                logger.info(f"Verification response for user {user_id}: {response.get('message', '')[:100]}")
                
                # Send response to user
                success = await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode'),
                    reply_markup=response.get('inline_keyboard')
                )
                
                if not success:
                    logger.error(f"Failed to send verification response to user {user_id}")
                else:
                    logger.info(f"Successfully sent verification response to user {user_id}")
                
                return {"ok": True, "message": "Sent verification form"}
            
            # Regular /start command - check if user is registered
            from database.models import SessionLocal
            from ssi.user_identity import get_user_by_telegram_id
            
            db = SessionLocal()
            try:
                existing_user = get_user_by_telegram_id(user_id, db)
                db.close()
                
                # If user doesn't exist, prompt them to register
                if not existing_user:
                    logger.info(f"New user {user_id}, prompting to register")
                    
                    result = await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            "👋 *Welcome to Voice Ledger!*\n\n"
                            "Voice Ledger helps coffee farmers, cooperatives, exporters, and buyers "
                            "create digital supply chain records using natural conversation.\n\n"
                            "📝 *Get Started:*\n"
                            "To begin, please complete registration:\n"
                            "👉 Send /register\n\n"
                            "This will let you:\n"
                            "• 🎙️ Create batches via voice messages\n"
                            "• 📞 Call our IVR line: +41 62 539 1661\n"
                            "• 📱 Receive SMS notifications\n"
                            "• 🔐 Access the web dashboard with PIN\n\n"
                            "Registration takes 2-5 minutes."
                        ),
                        parse_mode='Markdown',
                        send_voice=True  # Welcome message - conversational content
                    )
                    logger.info(f"/start prompt to register: {result}")
                    return {"ok": True, "message": "Prompted to register"}
                
                # User exists - show welcome message
            except Exception as e:
                logger.error(f"Error checking user registration: {e}")
                db.close()
            
            # Regular welcome message for registered users
            result = await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "👋 Welcome back to Voice Ledger!\n\n"
                    "I help coffee farmers, cooperatives, exporters, and buyers create digital supply chain records using natural conversation.\n\n"
                    "🗣️ *Just send a voice message!* I'll ask questions if I need more details.\n\n"
                    "📝 *Account & Identity:*\n"
                    "/register - Register new role\n"
                    "/myidentity - Show your DID\n"
                    "/mycredentials - View track record\n"
                    "/mybatches - List your batches\n"
                    "/language - Voice language preference\n\n"
                    "🛒 *Marketplace:*\n"
                    "/rfq - Create purchase request (buyers)\n"
                    "/myrfqs - View my RFQs & offers (buyers)\n"
                    "/offers - Browse available RFQs (cooperatives)\n"
                    "/myoffers - Track submitted offers (cooperatives)\n\n"
                    "📦 *Supply Chain:*\n"
                    "/verify - Verify a batch (managers only)\n"
                    "/dpp - Generate Digital Product Passport\n\n"
                    "🎙️ *Voice Examples:*\n"
                    "👨‍🌾 \"I harvested 50 kg coffee from Gedeo\"\n"
                    "📦 \"Ship batch ABC123 to Addis warehouse\"\n"
                    "🏭 \"Received batch XYZ456 in good condition\"\n"
                    "☕ \"Roast batch DEF789, output 850kg\"\n"
                    "📊 \"Pack batches A B C into pallet\"\n\n"
                    "Type /help for more details! 🎤"
                ),
                parse_mode='Markdown',
                send_voice=True  # Menu - conversational, useful as voice
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
                    "*📱 Account & Identity:*\n"
                    "/start - Welcome message\n"
                    "/help - This help message\n"
                    "/register - Register as farmer/manager/exporter/buyer\n"
                    "/myidentity - Show your Decentralized ID (DID)\n"
                    "/mycredentials - View your track record\n"
                    "/mybatches - List your batches\n"
                    "/language - Show voice language preference\n"
                    "/english - Switch to English voice\n"
                    "/amharic - Switch to Amharic voice\n\n"
                    "*🛒 Marketplace:*\n"
                    "/rfq - Create purchase request (buyers only)\n"
                    "/myrfqs - Track your RFQs and received offers\n"
                    "/offers - Browse available purchase requests (cooperatives)\n"
                    "/myoffers - Track your submitted offers\n\n"
                    "*📦 Supply Chain:*\n"
                    "/verify - Verify batch quality (managers only)\n"
                    "/dpp - Generate Digital Product Passport\n"
                    "/export - Get QR code for credentials\n"
                    "/status - Check system status\n\n"
                    "*🗣️ Voice Commands (Recommended):*\n\n"
                    "Just send voice messages naturally! I'll have a conversation with you to gather missing details.\n\n"
                    "*Examples by Role:*\n\n"
                    "👨‍🌾 *Farmers:*\n"
                    "   🎙️ \"I harvested 50 kg coffee from Gedeo\"\n"
                    "   💬 I'll ask: What variety? What type?\n\n"
                    "📦 *Cooperative Managers:*\n"
                    "   🎙️ \"Ship batch ABC123 to warehouse\"\n"
                    "   💬 I'll ask: Which location?\n\n"
                    "🏭 *Exporters:*\n"
                    "   🎙️ \"Received batch XYZ456 in good condition\"\n\n"
                    "☕ *Buyers/Roasters:*\n"
                    "   🎙️ \"Roast batch DEF789, output 850kg\"\n\n"
                    "📊 *Advanced Operations:*\n"
                    "   🎙️ \"Pack batches A and B into pallet\"\n"
                    "   🎙️ \"Split batch into 600kg and 400kg\"\n\n"
                    "💡 Voice messages in English or Amharic are the easiest way to interact!"
                ),
                parse_mode=None
            )
            return {"ok": True, "message": "Sent help message"}
        
        # Handle /admin command - show pending registrations
        if text.startswith('/admin'):
            logger.info(f"Handling /admin command for user {user_id}")
            from database.models import SessionLocal, PendingRegistration
            from ssi.user_identity import get_user_by_telegram_id
            
            db = SessionLocal()
            try:
                # Check if user is admin
                user = get_user_by_telegram_id(user_id, db)
                if not user or user.role != 'ADMIN':
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="❌ You must be an admin to use this command."
                    )
                    return {"ok": True}
                
                # Get pending registrations
                pending = db.query(PendingRegistration).filter(
                    PendingRegistration.status == 'pending'
                ).order_by(PendingRegistration.created_at.desc()).limit(10).all()
                
                if not pending:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="✅ No pending registrations!"
                    )
                    return {"ok": True}
                
                # Format pending registrations
                message = f"📋 Pending Registrations ({len(pending)}):\n\n"
                for reg in pending:
                    message += (
                        f"👤 {reg.full_name}\n"
                        f"   Role: {reg.requested_role}\n"
                        f"   Org: {reg.organization_name}\n"
                        f"   Location: {reg.location}\n"
                        f"   Date: {reg.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                    )
                
                base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
                message += f"\n🌐 Review & approve: {base_url}/review/registrations"
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=message
                )
                return {"ok": True}
                
            except Exception as e:
                logger.error(f"Error in /admin command: {e}", exc_info=True)
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Error retrieving pending registrations."
                )
                return {"ok": True}
            finally:
                db.close()
        
        # Handle text commands for supply chain operations (dev/testing alternatives to voice)
        if text.startswith('/commission '):
            logger.info(f"Handling /commission command for user {user_id}: {text}")
            
            # Check access control
            has_access, user_role, error_msg = await check_command_access(user_id, 'commission', processor)
            if not has_access:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=error_msg,
                    parse_mode='Markdown',
                    send_voice=True
                )
                return {"ok": True}
            
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /commission <qty> <variety> <origin>
            parts = text.split(maxsplit=3)
            if len(parts) < 4:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /commission <quantity> <variety> <origin>\nExample: /commission 500 Sidama MyFarm"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                entities = {
                    'quantity': parts[1],
                    'unit': 'kg',
                    'product': parts[2],
                    'origin': parts[3]
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='record_commission',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                logger.info(f"Commission response: {response_text[:100]}")
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
                
                # Create batch photo session and prompt for verification photo (EUDR compliance)
                if response_data and response_data.get('id'):
                    from voice.telegram.batch_photo_sessions import create_batch_photo_session
                    
                    batch_id = response_data['id']
                    batch_number = response_data.get('batch_id', f"Batch {batch_id}")
                    
                    create_batch_photo_session(user_id, batch_id, batch_number)
                    
                    # Prompt for photo upload
                    from database.models import UserIdentity
                    user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
                    lang = user.preferred_language if user else 'en'
                    
                    if lang == 'am':
                        photo_prompt = (
                            f"\n\n📸 *የEUDR ማረጋገጫ ፎቶ* (አማራጭ)\n\n"
                            f"በእርሻዎ ቦታ ላይ የተነሱ ፎቶግራፍ ያስገቡ:\n"
                            f"✅ ለአውሮፓ ወደሚላከው ቡና የሚረዳ\n"
                            f"✅ የቦታ ማረጋገጫ ይሰጣል\n"
                            f"✅ የ30 ቀናት ባልበለጠ ጊዜ ውስጥ የተነሱ\n\n"
                            f"አሁን ፎቶ ለመላክ 📎 የሚለውን ይጫኑ።"
                        )
                    else:
                        photo_prompt = (
                            f"\n\n📸 *EUDR Verification Photo* (Optional)\n\n"
                            f"Upload a photo from your harvest location:\n"
                            f"✅ Helps with EU export compliance\n"
                            f"✅ Provides GPS proof of origin\n"
                            f"✅ Photo must be recent (within 30 days)\n\n"
                            f"Press 📎 to send a photo now."
                        )
                    
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=photo_prompt,
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Error processing /commission: {e}", exc_info=True)
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=f"❌ Error: {str(e)}"
                )
            finally:
                db.close()
            return {"ok": True, "message": "Commission processed"}
        
        if text.startswith('/ship '):
            # Check access control
            has_access, user_role, error_msg = await check_command_access(user_id, 'ship', processor)
            if not has_access:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=error_msg,
                    parse_mode='Markdown',
                    send_voice=True
                )
                return {"ok": True}
            
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /ship <batch_id> <destination>
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /ship <gtin\\_or\\_batch\\_id> <destination>\nExample: /ship 00614141852251 Addis\\_Warehouse"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                entities = {
                    'batch_id': parts[1],
                    'destination': parts[2]
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='record_shipment',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Shipment processed"}
        
        if text.startswith('/receive '):
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /receive <batch_id> <condition>
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /receive <gtin\\_or\\_batch\\_id> [condition]\nExample: /receive 00614141852251 good"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                entities = {
                    'batch_id': parts[1],
                    'condition': parts[2] if len(parts) > 2 else 'good'
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='record_receipt',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Receipt processed"}
        
        if text.startswith('/transform '):
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /transform <batch_id> <type> <output_qty>
            parts = text.split(maxsplit=3)
            if len(parts) < 4:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /transform <batch_id_or_gtin> <type> <output_kg>\n"
                           "Example: /transform 00614141852251 roasting 850\n"
                           "💡 Tip: GTINs are shorter than batch IDs!"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                entities = {
                    'batch_id': parts[1],
                    'transformation_type': parts[2],
                    'output_quantity_kg': float(parts[3]),  # Convert to float
                    'output_unit': 'kg'
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='record_transformation',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Transformation processed"}
        
        if text.startswith('/pack '):
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /pack <batch1> <batch2> ... <container_id>
            parts = text.split()
            if len(parts) < 3:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /pack <batch1> <batch2> ... <container_id>\nExample: /pack ABC123 DEF456 PALLET-001"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                # Last part is container_id, rest are batch_ids
                batch_ids = parts[1:-1]
                container_id = parts[-1]
                
                entities = {
                    'batch_ids': batch_ids,
                    'container_id': container_id
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='pack_batches',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Pack processed"}
        
        if text.startswith('/unpack '):
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /unpack <container_id>
            parts = text.split()
            if len(parts) < 2:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /unpack <container_id>\nExample: /unpack PALLET-001"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                entities = {
                    'container_id': parts[1]
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='unpack_batches',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Unpack processed"}
        
        if text.startswith('/split '):
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /split <batch_id> <qty1> <qty2> ...
            parts = text.split()
            if len(parts) < 3:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /split <batch_id> <qty1> <qty2> [dest1] [dest2]\nExample: /split ABC123 600 400\nOr: /split ABC123 600 400 EUR ASIA"
                )
                return {"ok": True}
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                batch_id = parts[1]
                quantities = []
                destinations = []
                
                # Parse quantities and optional destinations
                i = 2
                while i < len(parts):
                    try:
                        qty = float(parts[i])
                        quantities.append(qty)
                        # Check if next part is destination (non-numeric)
                        if i + 1 < len(parts):
                            try:
                                float(parts[i + 1])
                                destinations.append(f"SPLIT_{i-1}")
                                i += 1
                            except ValueError:
                                destinations.append(parts[i + 1])
                                i += 2
                        else:
                            destinations.append(f"SPLIT_{i-1}")
                            i += 1
                    except ValueError:
                        break
                
                # Build splits array
                splits = [
                    {'quantity_kg': qty, 'destination': dest}
                    for qty, dest in zip(quantities, destinations)
                ]
                
                entities = {
                    'batch_id': batch_id,
                    'splits': splits
                }
                
                response_text, response_data = execute_voice_command(
                    db=db,
                    intent='split_batch',
                    entities=entities,
                    user_id=identity.get('user_id'),
                    user_did=identity['did']
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_text
                )
            finally:
                db.close()
            return {"ok": True, "message": "Split processed"}
        
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
        
        # Handle /register command - start registration conversation
        if text.startswith('/register'):
            from voice.telegram.register_handler import handle_register_command, conversation_states
            
            username = message.get('from', {}).get('username')
            first_name = message.get('from', {}).get('first_name', '')
            last_name = message.get('from', {}).get('last_name', '')
            
            response = await handle_register_command(
                user_id=int(user_id),
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            # Send response with optional keyboard (inline or reply/contact-share)
            if 'inline_keyboard' in response:
                import requests
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': {'inline_keyboard': response['inline_keyboard']}
                    },
                    timeout=30
                )
            elif 'reply_keyboard' in response:
                # ReplyKeyboardMarkup — used for contact-sharing / location buttons
                import requests
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                keyboard_rows = [
                    [
                        {k: v for k, v in btn.items() if k != 'text'}
                        | {'text': btn['text']}
                        for btn in row
                    ]
                    for row in response['reply_keyboard']
                ]
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': {
                            'keyboard': keyboard_rows,
                            'resize_keyboard': True,
                            'one_time_keyboard': True
                        }
                    },
                    timeout=30
                )
            else:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode')
                )
            
            return {"ok": True, "message": "Registration started"}
        
        # Handle /batches command - launch mini app
        if text.startswith('/batches'):
            import requests
            
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            api_base = os.getenv('API_BASE_URL', 'https://your-ngrok-url.ngrok.io')
            
            # Send message with inline button to launch mini app
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    'chat_id': user_id,
                    'text': '☕ *Browse Your Coffee Batches*\n\nView all your batches with detailed information and traceability timeline.',
                    'parse_mode': 'Markdown',
                    'reply_markup': {
                        'inline_keyboard': [[
                            {
                                'text': '📦 Open Batch Browser',
                                'web_app': {'url': f'{api_base}/miniapps/batches'}
                            }
                        ]]
                    }
                },
                timeout=30
            )
            
            return {"ok": True, "message": "Mini app launched"}
        
        # Handle /rfq command - create RFQ (buyers)
        if text.startswith('/rfq'):
            from voice.telegram.rfq_handler import handle_rfq_command
            
            username = message.get('from', {}).get('username')
            response = await handle_rfq_command(
                user_id=int(user_id),
                username=username
            )
            
            # Send response with keyboard
            import requests
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            reply_markup = {}
            if 'keyboard' in response:
                reply_markup = {'keyboard': response['keyboard'], 'resize_keyboard': True}
            elif 'inline_keyboard' in response:
                reply_markup = {'inline_keyboard': response['inline_keyboard']}
            
            if reply_markup:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': reply_markup
                    },
                    timeout=30
                )
            else:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode')
                )
            
            return {"ok": True, "message": "RFQ flow started"}
        
        # Handle /offers command - view available RFQs (cooperatives)
        if text.startswith('/offers'):
            from voice.telegram.rfq_handler import handle_offers_command
            
            username = message.get('from', {}).get('username')
            response = await handle_offers_command(
                user_id=int(user_id),
                username=username
            )
            
            # Send response with keyboard
            import requests
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            
            if 'keyboard' in response:
                telegram_response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'reply_markup': {'inline_keyboard': response['keyboard']}
                    },
                    timeout=30
                )
            else:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode')
                )
            
            return {"ok": True, "message": "Offers list sent"}
        
        # Handle /myoffers command - cooperative dashboard
        if text.startswith('/myoffers'):
            from voice.telegram.rfq_handler import handle_myoffers_command
            
            username = message.get('from', {}).get('username')
            response = await handle_myoffers_command(
                user_id=int(user_id),
                username=username
            )
            
            # Send response
            import requests
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if 'keyboard' in response:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': {'inline_keyboard': response['keyboard']}
                    },
                    timeout=30
                )
            else:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode')
                )
            
            return {"ok": True, "message": "My offers sent"}
        
        # Handle /myrfqs command - buyer dashboard
        if text.startswith('/myrfqs'):
            from voice.telegram.rfq_handler import handle_myrfqs_command
            
            username = message.get('from', {}).get('username')
            response = await handle_myrfqs_command(
                user_id=int(user_id),
                username=username
            )
            
            # Send response via processor
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=response['message'],
                parse_mode=response.get('parse_mode', 'Markdown'),
                reply_markup=response.get('keyboard')
            )
            
            return {"ok": True, "message": "My RFQs sent"}
        
        # Handle /language command - show current language
        if text.startswith('/language'):
            from ssi.user_identity import get_user_by_telegram_id
            from database.models import SessionLocal
            
            db = SessionLocal()
            try:
                user = get_user_by_telegram_id(user_id, db)
                if user:
                    lang_name = "English 🇺🇸" if user.preferred_language == 'en' else "Amharic (አማርኛ) 🇪🇹"
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            f"🌍 *Current Language*\n\n"
                            f"Your voice command language: *{lang_name}*\n\n"
                            f"To change language:\n"
                            f"• /english - Switch to English\n"
                            f"• /amharic - Switch to Amharic"
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="Please register first: /register"
                    )
            finally:
                db.close()
            
            return {"ok": True, "message": "Language info sent"}
        
        # Handle /english command - switch to English
        if text.startswith('/english'):
            from ssi.user_identity import get_user_by_telegram_id
            from database.models import SessionLocal
            from voice.integrations import ConversationManager
            from datetime import datetime
            
            db = SessionLocal()
            try:
                user = get_user_by_telegram_id(user_id, db)
                if user:
                    user.preferred_language = 'en'
                    user.language_set_at = datetime.utcnow()
                    db.commit()
                    
                    # Clear conversation history
                    ConversationManager.clear_conversation(user.id)
                    
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="✅ Language switched to English 🇺🇸\n\nYour voice commands will now be processed in English.",
                        parse_mode='Markdown'
                    )
                else:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="Please register first: /register"
                    )
            finally:
                db.close()
            
            return {"ok": True, "message": "Language switched to English"}
        
        # Handle /amharic command - switch to Amharic
        if text.startswith('/amharic'):
            from ssi.user_identity import get_user_by_telegram_id
            from database.models import SessionLocal
            from voice.integrations import ConversationManager
            from datetime import datetime
            
            db = SessionLocal()
            try:
                user = get_user_by_telegram_id(user_id, db)
                if user:
                    user.preferred_language = 'am'
                    user.language_set_at = datetime.utcnow()
                    db.commit()
                    
                    # Clear conversation history
                    ConversationManager.clear_conversation(user.id)
                    
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="✅ ቋንቋ ወደ አማርኛ ተቀይሯል 🇪🇹\n\nየድምጽ ትዕዛዞችዎ አሁን በአማርኛ ይሰራሉ።",
                        parse_mode='Markdown'
                    )
                else:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="እባክዎን መጀመሪያ ይመዝገቡ: /register"
                    )
            finally:
                db.close()
            
            return {"ok": True, "message": "Language switched to Amharic"}
        
        # Handle /myidentity command - show user's DID
        if text.startswith('/myidentity'):
            from ssi.user_identity import get_or_create_user_identity
            from database.models import SessionLocal
            
            db = SessionLocal()
            try:
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                status_emoji = "🆕" if identity['created'] else "✅"
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=(
                        f"{status_emoji} *Your Identity*\n\n"
                        f"DID: `{identity['did']}`\n\n"
                        "This is your decentralized identifier.\n"
                        "All batches you create are linked to this DID.\n\n"
                        "Use /mycredentials to see your track record."
                    )
                )
            finally:
                db.close()
            return {"ok": True, "message": "Sent identity"}
        
        # Handle /mycredentials command - show user's verifiable credentials
        if text.startswith('/mycredentials'):
            from ssi.user_identity import get_user_by_telegram_id
            from ssi.batch_credentials import get_user_credentials, calculate_simple_credit_score
            from database.models import SessionLocal
            
            db = SessionLocal()
            try:
                user = get_user_by_telegram_id(user_id, db_session=db)
                if not user:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="❌ No identity found. Create a batch first to generate your DID."
                    )
                    return {"ok": True}
                
                credentials = get_user_credentials(user.did, "CoffeeBatchCredential")
                score = calculate_simple_credit_score(user.did)
                
                if not credentials:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            "📋 *Your Credentials*\n\n"
                            "You haven't created any batches yet.\n"
                            "Record a voice message to create your first batch!"
                        )
                    )
                else:
                    creds_text = "\n\n".join([
                        f"📦 *{vc['credentialSubject']['batchId']}*\n"
                        f"   {vc['credentialSubject']['quantityKg']} kg {vc['credentialSubject']['variety']}\n"
                        f"   from {vc['credentialSubject']['origin']}\n"
                        f"   Recorded: {vc['issuanceDate'][:10]}"
                        for vc in credentials[:5]  # Show last 5
                    ])
                    
                    more_text = f"\n\n...and {len(credentials) - 5} more" if len(credentials) > 5 else ""
                    
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            f"📋 *Your Track Record*\n\n"
                            f"Credit Score: *{score['score']}/1000*\n"
                            f"Total Batches: {score['batch_count']}\n"
                            f"Total Production: {score['total_kg']:.1f} kg\n"
                            f"Days Active: {score['days_active']}\n\n"
                            f"*Recent Batches:*\n\n{creds_text}{more_text}"
                        )
                    )
            finally:
                db.close()
            return {"ok": True, "message": "Sent credentials"}
        
        # Handle /mybatches command - show user's batches
        if text.startswith('/mybatches'):
            from ssi.user_identity import get_user_by_telegram_id
            from database.models import SessionLocal, CoffeeBatch, Organization
            from sqlalchemy.orm import joinedload
            
            db = SessionLocal()
            try:
                user = get_user_by_telegram_id(user_id, db_session=db)
                if not user:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="❌ No identity found. Create a batch first!"
                    )
                    return {"ok": True}
                
                batches = db.query(CoffeeBatch).options(
                    joinedload(CoffeeBatch.verifying_organization)
                ).filter_by(
                    created_by_user_id=user.id
                ).order_by(CoffeeBatch.created_at.desc()).limit(10).all()
                
                if not batches:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message="📦 No batches found. Record a voice message to create one!"
                    )
                else:
                    # Build batch information with verification status
                    batch_lines = []
                    for b in batches:
                        # Status emoji
                        status_emoji = {
                            'PENDING_VERIFICATION': '⏳',
                            'VERIFIED': '✅',
                            'REJECTED': '❌',
                            'EXPIRED': '⌛'
                        }.get(b.status, '❓')
                        
                        # Base info
                        batch_info = (
                            f"📦 *{b.batch_id}*\n"
                            f"   {b.quantity_kg} kg {b.variety}\n"
                            f"   from {b.origin}\n"
                            f"   GTIN: `{b.gtin}`\n"
                        )
                        
                        # Add GLN if available
                        if b.gln:
                            batch_info += f"   GLN: `{b.gln}`\n"
                        
                        # Add verification status
                        batch_info += f"   Status: {status_emoji} {b.status.replace('_', ' ').title()}\n"
                        
                        # Add verifier info if verified
                        if b.status == 'VERIFIED' and b.verifying_organization:
                            batch_info += f"   Verified by: {b.verifying_organization.name}\n"
                            if b.verified_at:
                                batch_info += f"   Verified: {b.verified_at.strftime('%Y-%m-%d %H:%M')}\n"
                        
                        # Creation date
                        batch_info += f"   Created: {b.created_at.strftime('%Y-%m-%d %H:%M')}"
                        
                        batch_lines.append(batch_info)
                    
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            f"📦 *Your Batches* (showing last {len(batches)})\n\n"
                            f"{chr(10).join(batch_lines)}"
                        )
                    )
            finally:
                db.close()
            return {"ok": True, "message": "Sent batches"}
        
        # Handle /verify command - Verify a batch (COOPERATIVE_MANAGER only)
        if text.startswith('/verify'):
            # Check access control (uses new unified system)
            has_access, user_role, error_msg = await check_command_access(user_id, 'verify', processor)
            if not has_access:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=error_msg,
                    parse_mode='Markdown',
                    send_voice=True
                )
                return {"ok": True}
            
            from ssi.user_identity import get_user_by_telegram_id
            from database.models import SessionLocal
            from database import get_batch_by_id_or_gtin
            from datetime import datetime
            
            db = SessionLocal()
            try:
                
                # Parse: /verify <gtin_or_batch_id> <verified_quantity> [notes]
                parts = text.split(maxsplit=3)
                if len(parts) < 3:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            "❌ *Usage:* /verify <gtin\\_or\\_batch\\_id> <verified\\_quantity> [notes]\n\n"
                            "*Examples:*\n"
                            "`/verify 00614141852251 600`\n"
                            "`/verify BATCH_123 485 Quality excellent`"
                        )
                    )
                    return {"ok": True}
                
                identifier = parts[1]
                try:
                    verified_quantity = float(parts[2])
                except ValueError:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=f"❌ Invalid quantity: {parts[2]}. Must be a number."
                    )
                    return {"ok": True}
                
                notes = parts[3] if len(parts) > 3 else None
                
                # Look up batch
                batch = get_batch_by_id_or_gtin(db, identifier)
                if not batch:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            f"❌ Batch not found: {identifier}\n"
                            "Use GTIN (e.g., 00614141852251) or batch_id"
                        )
                    )
                    return {"ok": True}
                
                # Check if already verified
                if batch.status == 'VERIFIED':
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            f"ℹ️ *Already Verified*\n\n"
                            f"📦 {batch.batch_id}\n"
                            f"   {batch.quantity_kg} kg {batch.variety}\n"
                            f"   Verified by: {batch.verifying_organization.name if batch.verifying_organization else 'Unknown'}\n"
                            f"   Verified at: {batch.verified_at.strftime('%Y-%m-%d %H:%M') if batch.verified_at else 'Unknown'}"
                        )
                    )
                    return {"ok": True}
                
                # Verify batch
                batch.status = "VERIFIED"
                batch.verified_quantity = verified_quantity
                batch.verification_notes = notes
                batch.verified_by_did = user.did
                batch.verifying_organization_id = user.organization_id
                batch.verified_at = datetime.utcnow()
                batch.verification_used = True
                
                db.commit()
                
                logger.info(
                    f"Batch {batch.batch_id} verified by {user.telegram_first_name} "
                    f"(role={user.role}, did={user.did})"
                )
                
                # Issue verification credential signed by cooperative
                credential = None
                if user.organization_id and batch.created_by_did:
                    try:
                        from ssi.verification_credentials import issue_verification_credential
                        credential = issue_verification_credential(
                            batch_id=batch.batch_id,
                            farmer_did=batch.created_by_did,
                            organization_id=user.organization_id,
                            verified_quantity_kg=verified_quantity,
                            claimed_quantity_kg=batch.quantity_kg,
                            variety=batch.variety,
                            origin=batch.origin,
                            gtin=batch.gtin,
                            verification_date=datetime.utcnow().isoformat(),
                            notes=notes
                        )
                        logger.info(f"Issued verification credential for batch {batch.batch_id}")
                    except Exception as e:
                        logger.error(f"Failed to issue verification credential: {e}")
                
                # Send success message
                diff = verified_quantity - batch.quantity_kg
                diff_text = ""
                if abs(diff) > 0.1:
                    diff_sign = "+" if diff > 0 else ""
                    diff_text = f"\n   Difference: {diff_sign}{diff:.1f} kg ({diff_sign}{(diff/batch.quantity_kg)*100:.1f}%)"
                
                # Escape Markdown special characters in batch_id
                safe_batch_id = batch.batch_id.replace('_', '\\_')
                notes_line = f"   Notes: {notes}\n" if notes else ""
                credential_line = "✅ Verification credential issued" if credential else ""
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=(
                        f"✅ *Batch Verified*\n\n"
                        f"📦 {safe_batch_id}\n"
                        f"   GTIN: {batch.gtin}\n"
                        f"   Claimed: {batch.quantity_kg} kg\n"
                        f"   Verified: {verified_quantity} kg{diff_text}\n"
                        f"   Variety: {batch.variety}\n"
                        f"   Origin: {batch.origin}\n"
                        f"{notes_line}\n"
                        f"{credential_line}"
                    )
                )
            finally:
                db.close()
            return {"ok": True, "message": "Batch verified"}
        
        # Handle /dpp command - Generate Digital Product Passport for aggregated container
        if text.startswith('/dpp'):
            # Check if command has parameter
            if not text.startswith('/dpp '):
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ *Usage:* /dpp <container\\_id>\\n\\n*Example:* `/dpp 306141411234567892`",
                    parse_mode='Markdown',
                    send_voice=True
                )
                return {"ok": True}
            
            # Check access control
            has_access, user_role, error_msg = await check_command_access(user_id, 'dpp', processor)
            if not has_access:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=error_msg,
                    parse_mode='Markdown',
                    send_voice=True
                )
                return {"ok": True}
            
            from dpp.dpp_builder import build_aggregated_dpp
            from database.models import SessionLocal, CoffeeBatch
            import json
            
            # Parse: /dpp <container_id>
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /dpp <container_id>\\nExample: /dpp 306141411234567892"
                )
                return {"ok": True}
            
            container_id = parts[1].strip()
            
            db = SessionLocal()
            try:
                # Verify container exists by checking if it has aggregation relationships
                from database.models import AggregationRelationship
                relationships = db.query(AggregationRelationship).filter(
                    AggregationRelationship.parent_sscc == container_id,
                    AggregationRelationship.is_active == True
                ).first()
                
                if not relationships:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=f"❌ Container/SSCC not found or has no batches: {container_id}"
                    )
                    return {"ok": True}
                
                # Build aggregated DPP (container_id is an SSCC, not a batch_id)
                logger.info(f"Building aggregated DPP for SSCC {container_id}")
                dpp = build_aggregated_dpp(container_id)
                
                # Format response with key information
                contributors = dpp.get('traceability', {}).get('contributors', [])
                num_contributors = len(contributors)
                total_qty = dpp.get('productInformation', {}).get('totalQuantity', 'Unknown')
                eudr_compliant = dpp.get('dueDiligence', {}).get('eudrCompliant', False)
                all_geolocated = dpp.get('dueDiligence', {}).get('allFarmersGeolocated', False)
                
                # Get EUDR compliance details
                eudr_compliance = dpp.get('eudrCompliance', {})
                compliance_status = eudr_compliance.get('complianceStatus', 'UNKNOWN')
                compliance_level = eudr_compliance.get('complianceLevel', 'Unknown')
                farm_gps = eudr_compliance.get('geolocation', {}).get('farmLocation', {})
                verification_photos = eudr_compliance.get('geolocation', {}).get('harvestVerification', [])
                
                # Build compliance status emoji
                status_emoji = {
                    'FULLY_VERIFIED': '🟢',
                    'FARM_VERIFIED': '🟡',
                    'SELF_REPORTED': '🟠',
                    'NO_GPS': '🔴'
                }.get(compliance_status, '⚪')
                
                # Build contributors list
                contributor_lines = []
                for c in contributors[:5]:  # Show first 5 farmers
                    farmer_name = c.get('farmer', 'Unknown')
                    contribution = c.get('contributionPercent', '0%')
                    region = c.get('origin', {}).get('region', 'Unknown')
                    contributor_lines.append(
                        f"  • {farmer_name} - {contribution} ({region})"
                    )
                
                if num_contributors > 5:
                    contributor_lines.append(f"  ... and {num_contributors - 5} more farmers")
                
                contributors_text = "\n".join(contributor_lines)
                
                # Send formatted DPP summary with EUDR compliance
                message_text = (
                    f"📄 *Digital Product Passport*\n\n"
                    f"*Container:* `{container_id}`\n"
                    f"*Total Quantity:* {total_qty}\n"
                    f"*Contributors:* {num_contributors} farmers\n\n"
                    f"*Farmer Contributions:*\n{contributors_text}\n\n"
                    f"*EUDR Compliance:*\n"
                    f"{status_emoji} Status: {compliance_status.replace('_', ' ').title()}\n"
                    f"📊 Level: {compliance_level}\n"
                )
                
                # Add GPS verification details if available
                if farm_gps.get('coordinates'):
                    coords = farm_gps['coordinates']
                    message_text += f"📍 Farm GPS: {coords['latitude']:.6f}, {coords['longitude']:.6f}\n"
                    if farm_gps.get('verifiedAt'):
                        message_text += f"✅ Verified: {farm_gps['verifiedAt'][:10]}\n"
                
                if verification_photos:
                    message_text += f"📸 Harvest Photos: {len(verification_photos)} verified\n"
                
                message_text += (
                    f"\n*Due Diligence:*\n"
                    f"{'✅' if eudr_compliant else '❌'} EUDR Compliant\n"
                    f"{'✅' if all_geolocated else '❌'} All Farmers Geolocated\n\n"
                    f"*QR Code:* {dpp.get('qrCode', {}).get('url', 'N/A')}\n\n"
                    f"Full DPP with blockchain proofs and GPS verification."
                )
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=message_text,
                    parse_mode='Markdown'
                )
                
                logger.info(f"Successfully generated DPP for {container_id} with {num_contributors} contributors")
                
            except Exception as e:
                logger.error(f"Error generating DPP for {container_id}: {e}", exc_info=True)
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=f"❌ Error generating DPP: {str(e)}"
                )
            finally:
                db.close()
            
            return {"ok": True, "message": "Generated DPP"}
        
        # /export - Generate QR code with verifiable credentials
        if text.startswith('/export'):
            import qrcode
            import io
            from ssi.user_identity import get_user_by_telegram_id
            from ssi.batch_credentials import get_user_credentials, calculate_simple_credit_score
            from database.models import SessionLocal
            
            db = SessionLocal()
            try:
                # Extract user info from message
                username = message.get('from', {}).get('username')
                first_name = message.get('from', {}).get('first_name')
                last_name = message.get('from', {}).get('last_name')
                
                # Get or create user identity
                from ssi.user_identity import get_or_create_user_identity
                identity = get_or_create_user_identity(
                    telegram_user_id=user_id,
                    telegram_username=username,
                    telegram_first_name=first_name,
                    telegram_last_name=last_name,
                    db_session=db
                )
                
                user_did = identity['did']
                
                # Check if user has any credentials
                credentials = get_user_credentials(user_did)
                
                if not credentials:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=(
                            "❌ No credentials to export yet!\n\n"
                            "Create your first batch by sending a voice message:\n"
                            "🎙️ \"Record commission for 50kg Yirgacheffe from Gedeo\""
                        )
                    )
                    return {"ok": True}
                
                # Get credit score
                score = calculate_simple_credit_score(user_did)
                
                # Generate verification URL for QR code
                # Use ngrok URL if available, otherwise localhost
                base_url = os.getenv('NGROK_URL', 'http://localhost:8000')
                verification_url = f"{base_url}/voice/verify/{user_did}/html"
                
                # Create QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(verification_url)
                qr.make(fit=True)
                
                # Generate image
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save to BytesIO
                bio = io.BytesIO()
                img.save(bio, 'PNG')
                bio.seek(0)
                
                # Send QR code image via Telegram
                # We need to use the Telegram bot directly to send photos
                import requests
                
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                if not bot_token:
                    raise Exception("TELEGRAM_BOT_TOKEN not configured")
                
                # Send photo using Telegram API
                files = {'photo': ('qr_code.png', bio, 'image/png')}
                data = {
                    'chat_id': user_id,
                    'caption': (
                        f"📱 *Your Credential QR Code*\n\n"
                        f"✅ Credit Score: *{score['score']}/1000*\n"
                        f"📦 Total Batches: {score['batch_count']}\n"
                        f"⚖️ Total Production: {score['total_kg']:.1f} kg\n\n"
                        f"*How to Use:*\n"
                        f"1. Save this QR code to your photos\n"
                        f"2. Show it at banks/cooperatives\n"
                        f"3. They scan to verify your track record\n\n"
                        f"🔗 Or share this link:\n"
                        f"`{verification_url}`\n\n"
                        f"Anyone can verify your credentials without needing Voice Ledger!"
                    ),
                    'parse_mode': 'Markdown'
                }
                
                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                    files=files,
                    data=data,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to send QR code: {response.text}")
                    raise Exception(f"Failed to send QR code: {response.text}")
                
                logger.info(f"Sent QR code to user {user_id}, DID: {user_did}")
                
            except Exception as e:
                logger.error(f"Error generating QR code: {e}")
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=f"❌ Error generating QR code: {str(e)}"
                )
            finally:
                db.close()
            
            return {"ok": True, "message": "Sent QR code"}
        
        # Check if user is in verification session (awaiting quantity input)
        from voice.telegram.verification_handler import verification_sessions, handle_quantity_message
        
        if int(user_id) in verification_sessions:
            logger.info(f"User {user_id} in verification session, checking for quantity input")
            response = await handle_quantity_message(int(user_id), text)
            
            if response:  # If handler processed it
                # Send response with optional inline keyboard
                if 'inline_keyboard' in response:
                    import requests
                    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            'chat_id': user_id,
                            'text': response['message'],
                            'parse_mode': response.get('parse_mode', 'Markdown'),
                            'reply_markup': {'inline_keyboard': response['inline_keyboard']}
                        },
                        timeout=30
                    )
                else:
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=response['message'],
                        parse_mode=response.get('parse_mode')
                    )
                
                return {"ok": True, "message": "Verification response sent"}
        
        # Check if user is in RFQ creation session
        from voice.telegram.rfq_handler import rfq_sessions, handle_rfq_message
        
        if int(user_id) in rfq_sessions:
            logger.info(f"User {user_id} in RFQ creation session, routing to RFQ handler")
            response = await handle_rfq_message(int(user_id), text)
            
            # Send response with voice support (consistent with voice input)
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=response['message'],
                parse_mode=response.get('parse_mode', 'Markdown'),
                reply_markup=response.get('keyboard') or response.get('inline_keyboard'),
                send_voice=True  # Text input should get voice responses too
            )
            
            return {"ok": True, "message": "RFQ response sent"}
        
        # Check if user is in registration conversation
        from voice.telegram.register_handler import conversation_states, handle_registration_text
        
        if int(user_id) in conversation_states:
            logger.info(f"User {user_id} in registration conversation, routing to registration handler")
            response = await handle_registration_text(int(user_id), text)
            
            # Send response with optional keyboard (inline or reply/contact-share)
            if 'inline_keyboard' in response:
                import requests
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': {'inline_keyboard': response['inline_keyboard']}
                    },
                    timeout=30
                )
            elif 'reply_keyboard' in response:
                # ReplyKeyboardMarkup — used for contact-sharing / location buttons
                import requests
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                keyboard_rows = [
                    [
                        {k: v for k, v in btn.items() if k != 'text'}
                        | {'text': btn['text']}
                        for btn in row
                    ]
                    for row in response['reply_keyboard']
                ]
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        'chat_id': user_id,
                        'text': response['message'],
                        'parse_mode': response.get('parse_mode', 'Markdown'),
                        'reply_markup': {
                            'keyboard': keyboard_rows,
                            'resize_keyboard': True,
                            'one_time_keyboard': True
                        }
                    },
                    timeout=30
                )
            else:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response['message'],
                    parse_mode=response.get('parse_mode')
                )
            
            return {"ok": True, "message": "Registration response sent"}
        
        # Natural text query processing (non-slash commands)
        # Process like voice input: through conversational AI with NLU
        if not text.startswith('/'):
            logger.info(f"Processing natural text query from user {user_id}: {text[:50]}...")
            return await process_natural_text_query(update_data)
        
        # Unknown command - notify user
        logger.debug(f"Unknown Telegram text command: {text}")
        await processor.send_notification(
            channel_name='telegram',
            user_id=user_id,
            message=f"❓ *Unknown command:* `{text}`\n\nSend /help to see available commands.",
            parse_mode='Markdown',
            send_voice=True
        )
        return {"ok": True, "message": "Unknown command notified"}
        
    except Exception as e:
        logger.error(f"Error handling Telegram text command: {e}")
        return {"ok": True, "message": f"Error: {str(e)}"}


async def process_natural_text_query(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process natural text queries through conversational AI pipeline.
    
    This allows users to type natural queries like "help", "show my batches",
    or "what are EPCIS events?" and get conversational responses.
    
    Similar to Trust Voice implementation - unified text/voice processing.
    
    Args:
        update_data: Telegram Update dict with text message
        
    Returns:
        Response dict for Telegram
    """
    try:
        message = update_data['message']
        text = message.get('text', '')
        user_id = str(message['from']['id'])
        
        logger.info(f"Processing natural text query from {user_id}: '{text[:50]}...'")
        
        import os as _os
        agent_handled = False
        _agent_error_detail = None        
        # Get user's language preference
        from database.models import SessionLocal
        from ssi.user_identity import get_user_by_telegram_id
        
        db = SessionLocal()
        try:
            user = get_user_by_telegram_id(user_id, db_session=db)
            language = user.preferred_language if user else 'en'
            db.close()
        except Exception as e:
            logger.warning(f"Could not get user language preference: {e}")
            language = 'en'
            db.close()
        
        logger.info(f"User {user_id} language preference: {language}")
        
        # Check if user is in active workflow conversation
        from voice.workflows.state_machine import StateManager, ConversationState
        from voice.workflows.batch_recording import BatchRecordingWorkflow
        from voice.workflows.shipment_tracking import ShipmentTrackingWorkflow
        
        state_data = StateManager.get_user_state(int(user_id))
        if state_data:
            current_state = state_data.get('state')
            workflow_name = state_data.get('workflow')
            
            logger.info(f"User {user_id} in workflow: {workflow_name}, state: {current_state}")
            
            # Route to appropriate workflow
            if workflow_name == 'batch_recording':
                workflow = BatchRecordingWorkflow()
                result = await workflow.handle_message(
                    user_id=int(user_id),
                    message=text,
                    current_state=ConversationState(current_state)
                )
                response_message = result.get('message', 'Error processing your message.')
            elif workflow_name == 'shipment_tracking':
                workflow = ShipmentTrackingWorkflow()
                result = await workflow.handle_message(
                    user_id=int(user_id),
                    message=text,
                    current_state=ConversationState(current_state)
                )
                response_message = result.get('message', 'Error processing your message.')
            else:
                # Unknown workflow, clear state
                StateManager.clear_user_state(int(user_id))
                response_message = "Session expired. Please start again."

            # Send workflow response (dual delivery via channel default)
            if response_message:
                processor = get_processor()
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=response_message,
                    parse_mode=None,
                    language=language,
                )
        
        else:
            # No active workflow — try AI agent first, then legacy keyword routing
            response_message = None

            # =================================================================
            # AI AGENT PATH for text input (mirrors voice_tasks.py agent path)
            # The agent has 25 tools and can handle batch recording, shipments,
            # RFQs, compliance checks, DPP queries, etc. autonomously.
            # =================================================================
            if _os.getenv("AGENT_ENABLED", "false").lower() == "true":
                try:
                    from voice.agent import AgentExecutor
                    from database.models import SessionLocal
                    from ssi.user_identity import get_user_by_telegram_id

                    db = SessionLocal()
                    try:
                        _user = get_user_by_telegram_id(user_id, db_session=db)
                        _db_user_id = _user.id if _user else None
                        _user_did = _user.did if _user else None
                    finally:
                        db.close()

                    if _db_user_id:
                        logger.info(f"🤖 Agent processing text from user {_db_user_id}: {text[:50]}")

                        executor = AgentExecutor()
                        # Run synchronous executor in thread pool to avoid
                        # blocking the async event loop (OpenAI SDK is sync).
                        import asyncio
                        from functools import partial
                        _loop = asyncio.get_event_loop()
                        agent_result = await _loop.run_in_executor(
                            None,
                            partial(
                                executor.run,
                                transcript=text,
                                user_id=_db_user_id,
                                user_did=_user_did,
                                language=language,
                            ),
                        )

                        logger.info(
                            f"🤖 Agent text completed: {len(agent_result.tool_calls)} tool call(s), "
                            f"write={agent_result.performed_write}, "
                            f"tokens={agent_result.total_tokens}, "
                            f"time={agent_result.duration_ms:.0f}ms"
                        )

                        if agent_result.response:
                            processor = get_processor()
                            await processor.send_notification(
                                channel_name='telegram',
                                user_id=user_id,
                                message=agent_result.response,
                                parse_mode='Markdown',
                                send_voice=True,
                                language=language,
                            )
                            agent_handled = True

                except Exception as agent_err:
                    _agent_error_detail = f"{type(agent_err).__name__}: {agent_err}"
                    logger.error(f"🤖 Agent failed for text, falling back to legacy: {agent_err}", exc_info=True)
                    logger.warning(f"⚠️ FALLBACK ACTIVE for text from {user_id}: {_agent_error_detail}")

            # =================================================================
            # LEGACY PATH — keyword routing + RAG + conversational AI
            # Used when AGENT_ENABLED=false or agent fails/returns no response
            # =================================================================
            _fallback_banner = ""
            if not agent_handled and _os.getenv("AGENT_ENABLED", "false").lower() == "true":
                # Agent was enabled but didn't handle — show fallback banner
                _fallback_banner = "⚠️ <i>[Fallback mode — AI agent unavailable]</i>\n\n"

            if not agent_handled:
                if any(kw in text.lower() for kw in ['record batch', 'new batch', 'record harvest', 'create batch', 'log batch', 'record coffee']):
                    logger.info(f"Starting batch recording workflow for user {user_id}")
                    workflow = BatchRecordingWorkflow()
                    result = await workflow.start(int(user_id), initial_message=text)
                    response_message = result.get('message', 'Error starting batch recording.')

                elif any(kw in text.lower() for kw in ['track shipment', 'my shipments', 'where is my coffee', 'check shipment', 'track my']):
                    logger.info(f"Starting shipment tracking workflow for user {user_id}")
                    workflow = ShipmentTrackingWorkflow()
                    result = await workflow.start(int(user_id), initial_message=text)
                    response_message = result.get('message', 'Error starting shipment tracking.')

                # RFQ creation detection (buyer wants to purchase)
                elif any(kw in text.lower() for kw in [
                    'want to buy', 'need to buy', 'looking for', 'i want to purchase', 'need to purchase', 'want to order',
                    'create rfq', 'create an rfq', 'make rfq', 'make an rfq', 'new rfq', 'rfq for', 'post rfq',
                    'request quote', 'request for quote', 'looking to buy', 'interested in buying'
                ]):
                    logger.info(f"RFQ intent detected for user {user_id}: {text[:50]}")
                    from voice.marketplace.voice_rfq_extractor import extract_rfq_from_voice
                    from voice.telegram.rfq_handler import handle_voice_rfq_creation

                    extraction = extract_rfq_from_voice(text, language='en')
                    result = await handle_voice_rfq_creation(int(user_id), text, extraction, {
                        'channel': 'telegram',
                        'user_id': user_id,
                        'language': language
                    })
                    response_message = None  # Handler sends its own message

                else:
                    # Documentation vs operational query routing
                    query_lower = text.lower()

                    operational_keywords = [
                        'ship', 'record', 'register', 'create', 'pack', 'unpack',
                        'split', 'my batch', 'show batch', 'list batch', 'find batch',
                        'transform', 'aggregate', 'disaggregate',
                        'gtin:', 'batch id:', 'container', 'sscc'
                    ]
                    is_operational = any(keyword in query_lower for keyword in operational_keywords)

                    doc_keywords = [
                        'what is', 'what are', 'how to', 'how do', 'why', 'explain',
                        'tell me about', 'help', 'describe', 'documentation', 'guide',
                        'epcis', 'blockchain', 'dpp', 'gs1',
                        'ምን', 'እንዴት', 'ለምን', 'ምንድን', 'ማብራሪያ'
                    ]
                    is_doc_query = any(keyword in query_lower for keyword in doc_keywords) and not is_operational

                    if is_doc_query:
                        logger.info(f"Routing to MultiTurnRAG for doc query: {text[:50]}...")
                        from voice.rag.multi_turn_rag import MultiTurnRAG
                        from database.models import SessionLocal
                        from ssi.user_identity import get_user_by_telegram_id

                        db = SessionLocal()
                        try:
                            user = get_user_by_telegram_id(user_id, db_session=db)
                            db_user_id = user.id if user else int(user_id)
                            db.close()
                        except Exception as e:
                            logger.warning(f"Could not get DB user ID: {e}")
                            db_user_id = int(user_id)
                            db.close()

                        rag_result = await MultiTurnRAG.process_rag_query(
                            user_id=db_user_id,
                            query=text,
                            language=language
                        )
                        response_message = rag_result.get('message', 'Sorry, I could not find relevant information.')

                        sources = rag_result.get('sources', [])
                        if sources and len(sources) > 0:
                            sources_text = "\n\n📚 *Sources:*\n" + "\n".join([
                                f"• {src.get('file', 'Unknown')}"
                                for src in sources[:3]
                            ])
                            response_message += sources_text

                        if rag_result.get('is_follow_up'):
                            logger.info(f"MultiTurnRAG detected follow-up for user {db_user_id}")

                    else:
                        if language == 'am':
                            from voice.integrations.amharic_conversation import process_amharic_conversation
                            result = await process_amharic_conversation(int(user_id), text)
                            response_message = result.get('message', 'ይቅርታ፣ ስህተት ተከስቷል።')
                        else:
                            from voice.integrations.english_conversation import process_english_conversation
                            result = process_english_conversation(int(user_id), text, use_rag=True)
                            response_message = result.get('message_text') or result.get('message_spoken') or result.get('message', 'Sorry, I encountered an error.')

                # Send legacy response (dual delivery via channel default)
                if response_message:
                    if _fallback_banner:
                        response_message = _fallback_banner + response_message
                    processor = get_processor()
                    await processor.send_notification(
                        channel_name='telegram',
                        user_id=user_id,
                        message=response_message,
                        parse_mode='HTML' if _fallback_banner else None,
                        language=language,
                    )

        _response_source = "agent" if agent_handled else ("fallback_nlu" if _os.getenv("AGENT_ENABLED", "false").lower() == "true" else "legacy")
        logger.info(f"Natural text query processed for user {user_id} via {_response_source}")
        return {
            "ok": True,
            "message": "Natural text query processed",
            "response_source": _response_source,
            "agent_error": _agent_error_detail if not agent_handled else None,
        }
        
    except Exception as e:
        logger.error(f"Error processing natural text query: {e}", exc_info=True)
        
        # Send error message to user
        try:
            processor = get_processor()
            user_id = str(update_data['message']['from']['id'])
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message="Sorry, I encountered an error processing your message. Please try again or use a voice message."
            )
        except:
            pass
        
        return {"ok": True, "message": f"Error: {str(e)}"}


async def handle_callback_query(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle inline keyboard button clicks (callback queries).
    
    Args:
        update_data: Telegram Update dict with callback_query
        
    Returns:
        Response dict for Telegram
    """
    try:
        callback_query = update_data['callback_query']
        callback_data = callback_query.get('data', '')
        user_id = callback_query['from']['id']
        callback_id = callback_query['id']
        
        logger.info(f"Handling callback query: {callback_data} from user {user_id}")
        
        # Handle registration-related callbacks
        if callback_data.startswith('reg_'):
            from voice.telegram.register_handler import handle_registration_callback
            
            response = await handle_registration_callback(user_id, callback_data)
            
            # Answer the callback query (removes "loading" state from button)
            import requests
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                json={'callback_query_id': callback_id},
                timeout=30
            )
            
            # Edit the message with new text and optional keyboard
            message_id = callback_query['message']['message_id']
            chat_id = callback_query['message']['chat']['id']
            
            payload = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': response['message'],
                'parse_mode': response.get('parse_mode', 'Markdown')
            }
            
            if 'inline_keyboard' in response:
                payload['reply_markup'] = {'inline_keyboard': response['inline_keyboard']}
            
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/editMessageText",
                json=payload,
                timeout=30
            )
            
            return {"ok": True, "message": "Callback handled"}
        
        # Handle verification-related callbacks
        if callback_data.startswith(('verify_', 'confirm_', 'cancel_')):
            from voice.telegram.verification_handler import handle_verification_callback, handle_confirmation_callback
            
            # Determine which handler to use
            if callback_data.startswith(('confirm_', 'cancel_')):
                response = await handle_confirmation_callback(user_id, callback_data)
            else:
                response = await handle_verification_callback(user_id, callback_data)
            
            # Answer callback query
            import requests
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                json={'callback_query_id': callback_id},
                timeout=30
            )
            
            # Edit or send message
            message_id = callback_query['message']['message_id']
            chat_id = callback_query['message']['chat']['id']
            
            payload = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': response['message'],
                'parse_mode': response.get('parse_mode', 'Markdown')
            }
            
            if 'inline_keyboard' in response:
                payload['reply_markup'] = {'inline_keyboard': response['inline_keyboard']}
            
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/editMessageText",
                json=payload,
                timeout=30
            )
            
            return {"ok": True, "message": "Verification callback handled"}
        
        # Unknown callback data
        logger.debug(f"Unknown callback data: {callback_data}")
        return {"ok": True, "message": "Callback not recognized"}
        
    except Exception as e:
        logger.error(f"Error handling callback query: {e}", exc_info=True)
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


async def route_voice_to_command(command: str, user_id: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route voice command to appropriate Telegram handler.
    
    Maps detected voice commands to text command handlers:
    - "start" → /start
    - "help" → /help
    - "register" → /register
    - "myidentity" → /myidentity
    - "mybatches" → /mybatches
    - "mycredentials" → /mycredentials
    - "status" → /status
    - "export" → /export
    
    Args:
        command: Detected command name
        user_id: Telegram user ID
        metadata: Request metadata
        
    Returns:
        Command response dict
    """
    try:
        processor = get_processor()
        
        # Create fake message structure to simulate text command
        fake_message = {
            'from': {
                'id': user_id,
                'username': metadata.get('username', ''),
                'first_name': metadata.get('first_name', ''),
                'last_name': metadata.get('last_name', '')
            },
            'text': f'/{command}'
        }
        
        # Route to existing command handlers
        text = f'/{command}'
        
        # Import handlers on demand to avoid circular imports
        if command == 'start':
            logger.info(f"Routing voice to /start for user {user_id}")
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "👋 *Welcome to Voice Ledger!*\n\n"
                    "I help coffee farmers and cooperatives create digital records using voice commands.\n\n"
                    "🎙️ *What You Can Do:*\n\n"
                    "📦 *Create New Batch* (Commission)\n"
                    "Say: \"New batch of 50 kg Yirgacheffe from Gedeo farm\"\n\n"
                    "📤 *Ship Existing Batch* (Shipment)\n"
                    "Say: \"Shipped batch ABC123 to Addis warehouse\"\n\n"
                    "📥 *Receive Batch* (Receipt)\n"
                    "Say: \"Received batch XYZ456 from Abebe cooperative\"\n\n"
                    "⚙️ *Process Coffee* (Transformation)\n"
                    "Say: \"Washed batch DEF789 at processing station\"\n\n"
                    "💬 *Voice Commands (NEW!):*\n"
                    "You can also say:\n"
                    "- \"I want to register my cooperative\" → Start registration\n"
                    "- \"Help me understand the system\" → Get help\n"
                    "- \"Show me my batches\" → View your batches\n\n"
                    "📝 *Text Commands:*\n"
                    "Type /help to see all commands\n"
                    "Type /register to register your organization\n\n"
                    "Just record a voice message or type a command to get started! 🎤"
                )
            )
            return {"ok": True, "command": "start"}
            
        elif command == 'help':
            logger.info(f"Routing voice to /help for user {user_id}")
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "ℹ️ *Voice Ledger Help*\n\n"
                    "*Text Commands:*\n"
                    "/start - Welcome & examples\n"
                    "/help - This help message\n"
                    "/register - Register as cooperative/exporter/buyer\n"
                    "/status - Check system status\n"
                    "/myidentity - Show your DID\n"
                    "/mycredentials - View track record\n"
                    "/mybatches - List your batches\n"
                    "/export - Get QR code for credentials\n\n"
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
            return {"ok": True, "command": "help"}
            
        elif command == 'status':
            logger.info(f"Routing voice to /status for user {user_id}")
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "✅ *System Status*\n\n"
                    "All systems operational! 🚀"
                )
            )
            return {"ok": True, "command": "status"}
            
        elif command == 'register':
            logger.info(f"Routing voice to /register for user {user_id}")
            from voice.telegram.register_handler import handle_register_command
            
            response = await handle_register_command(
                user_id=user_id,
                username=metadata.get('username'),
                first_name=metadata.get('first_name', ''),
                last_name=metadata.get('last_name', '')
            )
            
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=response['message']
            )
            return {"ok": True, "command": "register", "response": response}
            
        elif command in ['myidentity', 'mybatches', 'mycredentials', 'export']:
            # These commands require database lookups - send notification that they're processed
            logger.info(f"Routing voice to /{command} for user {user_id}")
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=f"🎙️ Voice command recognized: `/{command}`\n\nProcessing..."
            )
            # The actual handler would be called from telegram_api.py handle_text_message
            # For now, just acknowledge
            return {"ok": True, "command": command, "message": "Command queued"}
        
        else:
            logger.warning(f"Unknown voice command: {command}")
            return {"ok": False, "error": f"Unknown command: {command}"}
            
    except Exception as e:
        logger.error(f"Error routing voice command: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
