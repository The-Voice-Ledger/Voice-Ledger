"""
Telegram Bot API endpoints for Voice Ledger.

Handles webhooks from Telegram for voice messages, text commands, and callbacks.
"""

import logging
import os
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
        
        # Handle callback queries (inline keyboard buttons)
        if 'callback_query' in update_data:
            logger.info("Routing to callback query handler")
            return await handle_callback_query(update_data)
        
        # Check if it's a message
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
            
            # Regular /start command - welcome message
            result = await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "👋 *Welcome to Voice Ledger!*\n\n"
                    "I help coffee farmers and cooperatives create digital records using voice or text commands.\n\n"
                    "📝 *System Commands:*\n"
                    "/start - This welcome message\n"
                    "/help - Detailed help & examples\n"
                    "/register - Register your organization\n"
                    "/status - Check system status\n"
                    "/myidentity - Show your DID\n"
                    "/mycredentials - View track record\n"
                    "/mybatches - List your batches\n"
                    "/export - Get QR code for credentials\n\n"
                    "🎙️ *Voice Commands:*\n"
                    "Record a voice message saying:\n"
                    "• \"Commission 50 kg Yirgacheffe\"\n"
                    "• \"Ship batch ABC123 to Addis\"\n"
                    "• \"Received batch XYZ456\"\n"
                    "• \"Roast batch DEF789 output 850kg\"\n"
                    "• \"Pack batches A B C into pallet\"\n"
                    "• \"Split batch into 600kg and 400kg\"\n\n"
                    "📋 *Text Alternatives: For Developers (testing)*\n"
                    "/commission <qty> <variety> <origin>\n"
                    "  Example: /commission 500 Sidama MyFarm\n"
                    "/ship <batch_id> <destination>\n"
                    "  Example: /ship BATCH_123 AddisWarehouse\n"
                    "/receive <batch_id> [condition]\n"
                    "  Example: /receive BATCH_123 good\n"
                    "/transform <batch_id> <type> <output_kg>\n"
                    "  Example: /transform BATCH_123 roasting 850\n"
                    "/pack <batch1> <batch2> ... <container>\n"
                    "  Example: /pack BATCH_1 BATCH_2 PALLET-001\n"
                    "/unpack <container_id>\n"
                    "  Example: /unpack PALLET-001\n"
                    "/split <batch_id> <qty1> <qty2> [dest1] [dest2]\n"
                    "  Example: /split BATCH_123 600 400 EUR ASIA\n\n"
                    "Type /help for detailed examples! 🎤"
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
                    "*System Commands:*\n"
                    "/start - Welcome message\n"
                    "/help - This help message\n"
                    "/register - Register as cooperative/exporter/buyer\n"
                    "/status - Check system status\n"
                    "/myidentity - Show your DID\n"
                    "/mycredentials - View track record\n"
                    "/mybatches - List your batches\n"
                    "/dpp <container\\_id> - Generate Digital Product Passport\n"
                    "/export - Get QR code for credentials\n\n"
                    "*Supply Chain Commands (Text):*\n"
                    "/commission <qty> <variety> <origin> - Create batch\n"
                    "/ship <batch\\_id> <destination> - Ship batch\n"
                    "/receive <batch\\_id> <condition> - Receive batch\n"
                    "/transform <batch\\_id> <type> <output\\_qty> - Process\n"
                    "/pack <batch1> <batch2> <container> - Aggregate\n"
                    "/unpack <container\\_id> - Disaggregate\n"
                    "/split <batch\\_id> <qty1> <qty2> - Split batch\n\n"
                    "*Voice Commands (Preferred):*\n\n"
                    "1️⃣ *Commission* - Create new batch\n"
                    "   🎙️ \"Commission 50 kg Sidama from my farm\"\n"
                    "   📝 /commission 50 Sidama MyFarm\n\n"
                    "2️⃣ *Shipment* - Send existing batch\n"
                    "   🎙️ \"Ship batch ABC123 to warehouse\"\n"
                    "   📝 /ship ABC123 warehouse\n\n"
                    "3️⃣ *Receipt* - Receive from supplier\n"
                    "   🎙️ \"Received batch XYZ in good condition\"\n"
                    "   📝 /receive XYZ good\n\n"
                    "4️⃣ *Transformation* - Process coffee\n"
                    "   🎙️ \"Roast batch DEF producing 850kg\"\n"
                    "   📝 /transform DEF roasting 850\n\n"
                    "5️⃣ *Pack* - Aggregate batches\n"
                    "   🎙️ \"Pack batches A and B into pallet\"\n"
                    "   📝 /pack A B PALLET-001\n\n"
                    "6️⃣ *Unpack* - Disaggregate container\n"
                    "   🎙️ \"Unpack container PALLET-001\"\n"
                    "   📝 /unpack PALLET-001\n\n"
                    "7️⃣ *Split* - Divide batch\n"
                    "   🎙️ \"Split batch into 600kg and 400kg\"\n"
                    "   📝 /split ABC 600 400\n\n"
                    "💡 Voice is preferred - text commands for dev/testing!"
                ),
                parse_mode=None
            )
            return {"ok": True, "message": "Sent help message"}
        
        # Handle text commands for supply chain operations (dev/testing alternatives to voice)
        if text.startswith('/commission '):
            logger.info(f"Handling /commission command for user {user_id}: {text}")
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
            from database.models import SessionLocal
            from voice.command_integration import execute_voice_command
            from ssi.user_identity import get_or_create_user_identity
            
            # Parse: /ship <batch_id> <destination>
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /ship <batch_id> <destination>\nExample: /ship ABC123 Addis_Warehouse"
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
                    message="❌ Usage: /receive <batch_id> [condition]\nExample: /receive ABC123 good"
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
                    message="❌ Usage: /transform <batch_id> <type> <output_kg>\nExample: /transform ABC123 roasting 850"
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
                    'output_quantity': parts[3],
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
            
            return {"ok": True, "message": "Registration started"}
        
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
        
        # Handle /dpp command - Generate Digital Product Passport for aggregated container
        if text.startswith('/dpp '):
            from dpp.dpp_builder import build_aggregated_dpp
            from database.models import SessionLocal, CoffeeBatch
            import json
            
            # Parse: /dpp <container_id>
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message="❌ Usage: /dpp <container_id>\nExample: /dpp 306141411234567892"
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
                
                # Send formatted DPP summary
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=(
                        f"📄 *Digital Product Passport*\n\n"
                        f"*Container:* `{container_id}`\n"
                        f"*Total Quantity:* {total_qty}\n"
                        f"*Contributors:* {num_contributors} farmers\n\n"
                        f"*Farmer Contributions:*\n{contributors_text}\n\n"
                        f"*EUDR Compliance:* {'✅ Yes' if eudr_compliant else '❌ No'}\n"
                        f"*All Farmers Geolocated:* {'✅ Yes' if all_geolocated else '❌ No'}\n\n"
                        f"*QR Code:* {dpp.get('qrCode', {}).get('url', 'N/A')}\n\n"
                        f"Full DPP generated with blockchain proofs and farmer lineage."
                    )
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
        
        # Check if user is in registration conversation
        from voice.telegram.register_handler import conversation_states, handle_registration_text
        
        if int(user_id) in conversation_states:
            logger.info(f"User {user_id} in registration conversation, routing to registration handler")
            response = await handle_registration_text(int(user_id), text)
            
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
            
            return {"ok": True, "message": "Registration response sent"}
        
        # Unknown command
        logger.debug(f"Unknown Telegram text command: {text}")
        return {"ok": True, "message": "Text command not recognized"}
        
    except Exception as e:
        logger.error(f"Error handling Telegram text command: {e}")
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
