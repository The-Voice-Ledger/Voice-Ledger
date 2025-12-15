"""
Multi-channel voice interface support.

Provides abstraction layer for handling voice messages from different channels:
- Twilio (phone calls)
- Telegram (voice notes)
- WhatsApp (voice notes via Twilio)
"""

from voice.channels.base import VoiceChannel
from voice.channels.twilio_channel import TwilioChannel

# Conditional imports based on availability
try:
    from voice.channels.telegram_channel import TelegramChannel
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

__all__ = [
    'VoiceChannel',
    'TwilioChannel',
    'TelegramChannel' if TELEGRAM_AVAILABLE else None,
]
