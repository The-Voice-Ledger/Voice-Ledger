"""
Simple Telegram notification utility for Celery tasks.

Uses python-telegram-bot's Bot class with direct API calls (no async complexity).
Designed to work reliably in Celery worker context.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def send_telegram_notification(chat_id: int, message: str) -> bool:
    """
    Send a simple text notification to a Telegram user.
    
    Uses synchronous HTTP requests to avoid asyncio issues in Celery.
    
    Args:
        chat_id: Telegram user/chat ID
        message: Text message to send
        
    Returns:
        True if sent successfully, False otherwise
    """
    import requests
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Telegram notification sent to {chat_id}")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


def send_batch_confirmation(chat_id: int, batch_info: Dict[str, Any]) -> bool:
    """
    Send a formatted batch confirmation notification.
    
    Args:
        chat_id: Telegram user/chat ID
        batch_info: Dictionary with batch details
        
    Returns:
        True if sent successfully, False otherwise
    """
    batch_id = batch_info.get('id', 'Unknown')
    variety = batch_info.get('variety', 'Unknown')
    quantity = batch_info.get('quantity', 0)
    farm = batch_info.get('farm', 'Unknown')
    gtin = batch_info.get('gtin', 'N/A')
    gln = batch_info.get('gln', 'Not assigned')
    
    message = (
        f"✅ *Batch Created Successfully!*\n\n"
        f"📦 *Batch ID:* `{batch_id}`\n"
        f"🏷️ *GTIN:* `{gtin}`\n"
        f"📍 *GLN:* `{gln}`\n"
        f"☕ *Variety:* {variety}\n"
        f"⚖️ *Quantity:* {quantity} kg\n"
        f"🌍 *Origin:* {farm}\n\n"
        f"Your coffee batch has been registered in the traceability system."
    )
    
    return send_telegram_notification(chat_id, message)


async def send_batch_verification_qr(chat_id: int, batch_info: Dict[str, Any]) -> bool:
    """
    Send batch confirmation with verification QR code AND voice message.
    
    Sends a photo (QR code) with caption containing batch details,
    followed by a voice message for accessibility.
    
    Args:
        chat_id: Telegram user/chat ID
        batch_info: Dictionary with batch details including verification_token
        
    Returns:
        True if sent successfully, False otherwise
    """
    import httpx
    from telegram import Bot
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    # Extract batch information
    batch_id = batch_info.get('batch_id', 'Unknown')
    variety = batch_info.get('variety', 'Unknown')
    quantity = batch_info.get('quantity_kg', 0)
    origin = batch_info.get('origin', 'Unknown')
    gtin = batch_info.get('gtin', 'N/A')
    verification_token = batch_info.get('verification_token')
    status = batch_info.get('status', 'UNKNOWN')
    
    if not verification_token:
        logger.error("No verification token provided for QR code")
        return False
    
    # Generate QR code
    try:
        from voice.verification.qr_codes import generate_qr_code_bytes
        qr_bytes = generate_qr_code_bytes(verification_token)
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return False
    
    # Prepare caption message with nice formatting
    base_url = os.getenv('BASE_URL', 'http://localhost:8000')
    
    # Get GLN for display
    gln = batch_info.get('gln', 'Not assigned')
    
    # Use HTML parse mode - MarkdownV2 requires escaping dozens of
    # special characters (. - ! ( ) etc.) which is fragile with
    # dynamic data like GTINs and GLNs.
    import html as _html
    _e = lambda v: _html.escape(str(v))  # shorthand for HTML-escaping

    caption = (
        f"📦 <b>Batch Created - Awaiting Verification</b>\n\n"
        f"<b>Batch ID:</b> <code>{_e(batch_id)}</code>\n"
        f"🏷️ <b>GTIN:</b> <code>{_e(gtin)}</code>\n"
        f"📍 <b>GLN:</b> <code>{_e(gln)}</code>\n"
        f"☕ <b>Variety:</b> {_e(variety)}\n"
        f"⚖️ <b>Quantity:</b> {_e(quantity)} kg\n"
        f"🌍 <b>Origin:</b> {_e(origin)}\n"
        f"📊 <b>Status:</b> {_e(status)}\n\n"
        f"🔍 <b>Next Step: Physical Verification</b>\n"
        f"Take this QR code to the cooperative collection center. "
        f"The manager will scan it to verify your batch.\n\n"
        f"⏱️ <b>Valid for:</b> 48 hours\n"
        f"🔗 <b>Verification Token:</b> <code>{_e(verification_token)}</code>"
    )
    
    # Send photo with caption
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        files = {'photo': ('verification_qr.png', qr_bytes, 'image/png')}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
        
        if response.status_code == 200:
            logger.info(f"Verification QR code sent to {chat_id}")
            
            # Now send voice message with TTS for accessibility
            try:
                from voice.telegram.voice_responses import send_voice_reply
                bot = Bot(token=bot_token)
                
                # Simplified text for voice (without markdown and emojis)
                voice_text = (
                    f"Batch Created - Awaiting Verification. "
                    f"Batch ID: {batch_id}. "
                    f"GTIN: {gtin}. "
                    f"Variety: {variety}. "
                    f"Quantity: {quantity} kilograms. "
                    f"Origin: {origin}. "
                    f"Status: {status}. "
                    f"Next Step: Physical Verification. "
                    f"Take this QR code to the cooperative collection center. "
                    f"The manager will scan it to verify your batch. "
                    f"Valid for 48 hours. "
                    f"Verification Token: {verification_token}"
                )
                
                await send_voice_reply(
                    bot=bot,
                    chat_id=chat_id,
                    message=voice_text,
                    parse_mode=None,  # Plain text for voice
                    send_voice=True
                )
                logger.info(f"Voice message sent for batch confirmation to {chat_id}")
            except Exception as voice_err:
                logger.warning(f"Failed to send voice message (QR sent successfully): {voice_err}")
            
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send verification QR code: {e}")
        return False


def send_error_notification(chat_id: int, error: str) -> bool:
    """
    Send an error notification.
    
    Args:
        chat_id: Telegram user/chat ID
        error: Error message
        
    Returns:
        True if sent successfully, False otherwise
    """
    message = f"❌ *Error Processing Voice Command*\n\n{error}"
    return send_telegram_notification(chat_id, message)


async def send_batch_dpp_pdf(chat_id: int, batch_id: str) -> bool:
    """
    Generate and send the Digital Product Passport PDF via Telegram.

    Called after a successful batch commission so the farmer receives a
    downloadable PDF they can share with cooperatives or customs brokers.

    Args:
        chat_id: Telegram user/chat ID
        batch_id: Batch identifier (e.g. "BATCH-2025-001")

    Returns:
        True if sent successfully, False otherwise
    """
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set - cannot send DPP PDF")
        return False

    try:
        from dpp.dpp_pdf import build_and_render_pdf

        pdf_bytes = build_and_render_pdf(batch_id)
    except Exception as e:
        logger.error(f"Failed to generate DPP PDF for {batch_id}: {e}")
        return False

    import html as _html
    _e = lambda v: _html.escape(str(v))

    caption = (
        f"📄 <b>Digital Product Passport</b>\n\n"
        f"<b>Batch:</b> <code>{_e(batch_id)}</code>\n"
        f"Your full DPP is attached as a PDF.  Share it with "
        f"cooperatives, customs brokers, or buyers for instant "
        f"traceability verification."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    try:
        files = {
            "document": (f"DPP_{batch_id}.pdf", pdf_bytes, "application/pdf"),
        }
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)

        if response.status_code == 200:
            logger.info(f"DPP PDF sent to {chat_id} for batch {batch_id}")
            return True
        else:
            logger.error(
                f"Telegram sendDocument error: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Failed to send DPP PDF to {chat_id}: {e}")
        return False
