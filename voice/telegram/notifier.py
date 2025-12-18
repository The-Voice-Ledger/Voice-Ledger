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


def send_batch_verification_qr(chat_id: int, batch_info: Dict[str, Any]) -> bool:
    """
    Send batch confirmation with verification QR code.
    
    Sends a photo (QR code) with caption containing batch details.
    The QR code links to the verification page.
    
    Args:
        chat_id: Telegram user/chat ID
        batch_info: Dictionary with batch details including verification_token
        
    Returns:
        True if sent successfully, False otherwise
    """
    import requests
    
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
    
    # Escape special Markdown characters in user data
    def escape_markdown(text):
        """Escape special characters for Telegram MarkdownV2."""
        if not text:
            return text
        # Escape all special MarkdownV2 characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        text = str(text)
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    # Get GLN for display
    gln = batch_info.get('gln', 'Not assigned')
    
    caption = (
        f"📦 *Batch Created \\- Awaiting Verification*\n\n"
        f"*Batch ID:* `{batch_id}`\n"
        f"🏷️ *GTIN:* `{gtin}`\n"
        f"📍 *GLN:* `{gln}`\n"
        f"☕ *Variety:* {escape_markdown(variety)}\n"
        f"⚖️ *Quantity:* {escape_markdown(str(quantity))} kg\n"
        f"🌍 *Origin:* {escape_markdown(origin)}\n"
        f"📊 *Status:* {escape_markdown(status)}\n\n"
        f"🔍 *Next Step: Physical Verification*\n"
        f"Take this QR code to the cooperative collection center\\. "
        f"The manager will scan it to verify your batch\\.\n\n"
        f"⏱️ *Valid for:* 48 hours\n"
        f"🔗 *Verification Token:* `{verification_token}`"
    )
    
    # Send photo with caption
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        files = {'photo': ('verification_qr.png', qr_bytes, 'image/png')}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'MarkdownV2'  # Use MarkdownV2 with proper escaping
        }
        
        response = requests.post(url, data=data, files=files, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Verification QR code sent to {chat_id}")
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
