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
    
    message = (
        f"✅ *Batch Created Successfully!*\n\n"
        f"📦 *Batch ID:* `{batch_id}`\n"
        f"🏷️ *GTIN:* `{gtin}`\n"
        f"☕ *Variety:* {variety}\n"
        f"⚖️ *Quantity:* {quantity} kg\n"
        f"🌍 *Origin:* {farm}\n\n"
        f"Your coffee batch has been registered in the traceability system."
    )
    
    return send_telegram_notification(chat_id, message)


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
