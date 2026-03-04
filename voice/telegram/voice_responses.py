"""
Telegram voice response helpers for dual delivery.

Implements TrustVoice pattern:
- Text sent immediately (fast feedback)
- Voice follows ~2 seconds later (accessibility)
"""

import asyncio
import logging
import re
import os
from typing import Optional
from telegram import Bot
from database.models import SessionLocal, UserIdentity
from voice.tts.tts_provider import TTSProvider

logger = logging.getLogger(__name__)


def escape_markdown(text):
    """
    Escape special characters for Telegram Markdown (V1/Standard).
    
    Telegram's 'Markdown' mode (V1) is sensitive to:
    - Underscores (_) which are often in variables like GRADE_1
    - Asterisks (*)
    - Square brackets ([)
    - Backticks (`)
    
    Args:
        text: Input string to escape
        
    Returns:
        Escaped string safe for Markdown parse_mode
    """
    if not text:
        return text
    
    # We only escape these for the standard 'Markdown' mode
    # For MarkdownV2, a much larger set of characters must be escaped.
    # Note: Underscores are the main culprit for "Can't parse entities"
    special_chars = ['_', '*', '[', '`']
    
    text = str(text)
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def translate_text_to_amharic(text: str) -> str:
    """
    Translate English text to Amharic using Addis AI.
    
    Args:
        text: English text to translate
        
    Returns:
        Amharic translation
    """
    try:
        import httpx
        
        # Use Addis AI for translation
        ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
        ADDIS_AI_CHAT_URL = "https://api.addisassistant.com/api/v1/chat_generate"
        
        if not ADDIS_AI_API_KEY:
            return text
        
        headers = {
            "X-API-Key": ADDIS_AI_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": text,
            "target_language": "am"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ADDIS_AI_CHAT_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                # Extract translation from nested structure
                translation = (
                    data.get("data", {}).get("response_text") or 
                    data.get("response_text") or 
                    data.get("response") or 
                    data.get("text") or 
                    data.get("answer") or 
                    text
                )
                return translation
            else:
                return text
                
    except Exception as e:
        return text  # Return original if translation fails


def detect_language(text: str) -> str:
    """
    Detect language from text using Unicode ranges.
    
    Amharic: U+1200 to U+137F
    
    Args:
        text: Input text
        
    Returns:
        "am" for Amharic, "en" for English
    """
    if not text:
        return "en"
    
    # Count Amharic characters
    amharic_chars = sum(1 for char in text if '\u1200' <= char <= '\u137F')
    
    # If > 30% Amharic characters, classify as Amharic
    if amharic_chars > len(text) * 0.3:
        return "am"
    
    return "en"


def clean_text_for_tts(text: str) -> str:
    """
    Clean text for TTS generation.
    
    Removes:
    - HTML tags
    - Markdown formatting
    - URLs
    - Multiple spaces
    - Excessive emojis
    
    Args:
        text: Input text with formatting
        
    Returns:
        Clean text for speech synthesis
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove Markdown bold/italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # Remove Markdown links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)
    
    # Keep common emojis but remove them for TTS (optional)
    # text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove bullet points
    text = text.replace('•', '')
    text = text.replace('◦', '')
    
    return text.strip()


def format_for_voice(text: str) -> str:
    """
    Format text for natural voice synthesis.
    
    Conversions:
    - Currency: "$50" → "50 dollars", "€100" → "100 euros", "450 ETB" → "450 birr"
    - Units: "5kg" → "5 kilograms", "10m" → "10 meters", "25%" → "25 percent"
    - Numbers: Spell out numbers < 20, keep larger numbers as digits
    - Ordinals: "1st" → "first", "2nd" → "second", "3rd" → "third"
    - Codes: "ABC-123" remains as is (spelled out by TTS)
    - Times: "14:30" → "14 30" or "2:30pm" → "2 30 PM"
    
    Args:
        text: Input text with symbols and formatting
        
    Returns:
        Voice-friendly text
        
    Example:
        >>> format_for_voice("Batch ABC-123: 50kg for $450")
        "Batch ABC-123: 50 kilograms for 450 dollars"
    """
    if not text:
        return ""
    
    # Strip whitespace first
    text = text.strip()
    if not text:
        return ""
    
    # Currency symbols - order matters (do specific ones first)
    currency_map = {
        r'\$(\d+(?:\.\d+)?)': r'\1 dollars',
        r'(\d+(?:\.\d+)?)\s*ETB': r'\1 birr',  # Ethiopian Birr
        r'(\d+(?:\.\d+)?)\s*USD': r'\1 US dollars',
        r'(\d+(?:\.\d+)?)\s*EUR': r'\1 euros',
        r'€(\d+(?:\.\d+)?)': r'\1 euros',  # After EUR to avoid double replacement
        r'£(\d+(?:\.\d+)?)': r'\1 pounds',
        r'¥(\d+(?:\.\d+)?)': r'\1 yen',
    }
    
    for pattern, replacement in currency_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Units (with and without spaces)
    units_map = {
        r'(\d+(?:\.\d+)?)\s*kg(?!\w)': r'\1 kilograms',
        r'(\d+(?:\.\d+)?)\s*g(?!\w)': r'\1 grams',
        r'(\d+(?:\.\d+)?)\s*m(?!\w)': r'\1 meters',
        r'(\d+(?:\.\d+)?)\s*km(?!\w)': r'\1 kilometers',
        r'(\d+(?:\.\d+)?)\s*cm(?!\w)': r'\1 centimeters',
        r'(\d+(?:\.\d+)?)\s*lb(?!\w)': r'\1 pounds',
        r'(\d+(?:\.\d+)?)\s*oz(?!\w)': r'\1 ounces',
        r'(\d+(?:\.\d+)?)\s*%': r'\1 percent',
    }
    
    for pattern, replacement in units_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Ordinals (1st, 2nd, 3rd, etc.) - do BEFORE small number conversion
    ordinals = {
        r'\b1st\b': 'first',
        r'\b2nd\b': 'second',
        r'\b3rd\b': 'third',
        r'\b4th\b': 'fourth',
        r'\b5th\b': 'fifth',
        r'\b6th\b': 'sixth',
        r'\b7th\b': 'seventh',
        r'\b8th\b': 'eighth',
        r'\b9th\b': 'ninth',
        r'\b10th\b': 'tenth',
        r'\b11th\b': 'eleventh',
        r'\b12th\b': 'twelfth',
        r'\b13th\b': 'thirteenth',
        r'\b14th\b': 'fourteenth',
        r'\b15th\b': 'fifteenth',
        r'\b16th\b': 'sixteenth',
        r'\b17th\b': 'seventeenth',
        r'\b18th\b': 'eighteenth',
        r'\b19th\b': 'nineteenth',
        r'\b20th\b': 'twentieth',
    }
    
    for pattern, replacement in ordinals.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Spell out small numbers (1-19) when standalone
    # Only replace if not part of larger numbers or codes
    number_words = {
        r'\b1\b': 'one',
        r'\b2\b': 'two',
        r'\b3\b': 'three',
        r'\b4\b': 'four',
        r'\b5\b': 'five',
        r'\b6\b': 'six',
        r'\b7\b': 'seven',
        r'\b8\b': 'eight',
        r'\b9\b': 'nine',
        r'\b10\b': 'ten',
        r'\b11\b': 'eleven',
        r'\b12\b': 'twelve',
        r'\b13\b': 'thirteen',
        r'\b14\b': 'fourteen',
        r'\b15\b': 'fifteen',
        r'\b16\b': 'sixteen',
        r'\b17\b': 'seventeen',
        r'\b18\b': 'eighteen',
        r'\b19\b': 'nineteen',
    }
    
    # Only apply to text not surrounded by digits, hyphens, or followed by 'kilograms'/'meters'/etc
    for pattern, word in number_words.items():
        # Negative lookbehind/ahead to avoid replacing in codes or measurements
        # Don't replace if followed by ' kilograms', ' meters', etc (already converted)
        safe_pattern = r'(?<!\d)(?<!-)(?<!\.)' + pattern + r'(?!\d)(?!-)(?!\.)(?! kilograms)(?! grams)(?! meters)(?! kilometers)(?! centimeters)(?! pounds)(?! ounces)'
        text = re.sub(safe_pattern, word, text)
    
    # Time formats (optional - make them more speech-friendly)
    text = re.sub(r'(\d{1,2}):(\d{2})\s*(am|pm)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d{1,2}):(\d{2})', r'\1 \2', text)  # 14:30 → 14 30
    
    return text


async def _generate_and_send_voice(
    bot: Bot,
    chat_id: int,
    message: str,
    language: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    user_preference_language: Optional[str] = None
):
    """
    Background task to generate and send voice message.
    
    This runs asynchronously - doesn't block text delivery.
    
    Args:
        bot: Telegram bot instance
        chat_id: User's chat ID
        message: Text to convert to speech
        language: Language code ("en" or "am"), auto-detected if None
        reply_to_message_id: Optional message ID to reply to
        user_preference_language: User's preferred language from registration (priority)
    """
    try:
        # Clean text for TTS
        clean_text = clean_text_for_tts(message)
        
        if not clean_text:
            logger.warning(f"No text to synthesize after cleaning: {message[:50]}")
            return
        
        # Format text for voice synthesis
        voice_friendly_text = format_for_voice(clean_text)
        
        if not voice_friendly_text:
            logger.warning(f"No text after voice formatting: {clean_text[:50]}")
            return
        
        # Prioritize: explicit language > user preference > text detection
        if language is None:
            if user_preference_language:
                language = user_preference_language
                logger.info(f"Using user preference language: {language}")
            else:
                language = detect_language(voice_friendly_text)
                logger.info(f"Using text-detected language: {language}")
        
        logger.info(f"🎤 Generating TTS: {len(voice_friendly_text)} chars (formatted), lang: {language}, chat: {chat_id}")
        
        # Translate English to Amharic if user prefers Amharic but text is English
        if user_preference_language == "am" and detect_language(voice_friendly_text) == "en":
            voice_friendly_text = await translate_text_to_amharic(voice_friendly_text)
        
        # Route TTS based on language
        audio_bytes = None
        
        if language == "am":
            # Use AddisAI for Amharic
            try:
                audio_bytes = await TTSProvider.text_to_speech(
                    text=voice_friendly_text,
                    language="am"
                )
                logger.info(f"✅ Amharic TTS generated: {len(audio_bytes)} bytes")
            except Exception as e:
                logger.error(f"Amharic TTS failed: {e}")
        else:
            # Use OpenAI for English (and other languages)
            try:
                audio_bytes = await TTSProvider.text_to_speech(
                    text=voice_friendly_text,
                    language="en"
                )
                logger.info(f"✅ English TTS generated: {len(audio_bytes)} bytes")
            except Exception as e:
                logger.error(f"English TTS failed: {e}")
        
        if audio_bytes:
            # Save to temporary file for Telegram upload
            import tempfile
            
            # Addis AI returns MP3 audio, use MP3 extension for proper file format
            if language == "am":
                suffix = '.mp3'  # Addis AI returns MP3
                with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    audio_path = tmp_file.name
            else:
                suffix = '.mp3'
                with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    audio_path = tmp_file.name
            
            # Send voice message
            try:
                with open(audio_path, 'rb') as audio_file:
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=audio_file,
                        caption="🎤",  # Optional caption
                        reply_to_message_id=reply_to_message_id
                    )
                
                logger.info(f"✅ Voice reply sent: {len(voice_friendly_text)} chars (formatted), lang: {language}")
            finally:
                # Cleanup temp file
                try:
                    os.unlink(audio_path)
                except:
                    pass
        else:
            logger.warning("⚠️ TTS generation failed, text-only sent")
    
    except Exception as e:
        logger.error(f"❌ Voice delivery error: {str(e)}", exc_info=True)
        # Don't raise - text already sent, no user-facing error


async def send_voice_reply(
    bot: Bot,
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    language: Optional[str] = None,
    send_voice: bool = True,
    reply_to_message_id: Optional[int] = None,
    reply_markup = None
) -> None:
    """
    Send dual text + voice response.
    
    Flow:
    1. Send text immediately (user sees response instantly)
    2. Look up user's language preference from registration
    3. Generate TTS in background (non-blocking)
    4. Send voice when ready (~2 seconds later)
    
    This implements the TrustVoice pattern for universal accessibility:
    - Literate users: Read text immediately
    - Illiterate users: Wait for voice (accessible)
    - Everyone gets both - no configuration needed
    
    Language Priority:
    1. Explicit `language` parameter (highest priority)
    2. User's `preferred_language` from registration
    3. Unicode-based text detection (fallback)
    
    Args:
        bot: Telegram bot instance
        chat_id: User's chat ID
        message: Response text
        parse_mode: "HTML" or "Markdown" (default: "HTML")
        language: Language code ("en" or "am"), auto-detected if None
        send_voice: Whether to include voice message (default: True)
        reply_to_message_id: Optional message ID to reply to
        reply_markup: Optional reply markup (inline keyboard)
    
    Example:
        await send_voice_reply(
            bot=context.bot,
            chat_id=user_id,
            message="✅ Batch recorded successfully!"
        )
    """
    
    # Convert reply_markup if it's a list (keyboard)
    telegram_reply_markup = None
    if reply_markup:
        if isinstance(reply_markup, list):
            # Check if this is inline keyboard (has callback_data/url) or regular keyboard
            # Inline keyboards have callback_data or url, regular keyboards just have text
            is_inline = False
            for row in reply_markup:
                for button in row:
                    if isinstance(button, dict) and ('callback_data' in button or 'url' in button):
                        is_inline = True
                        break
                if is_inline:
                    break
            
            if is_inline:
                # Convert to InlineKeyboardMarkup
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = []
                for row in reply_markup:
                    keyboard_row = []
                    for button in row:
                        keyboard_row.append(
                            InlineKeyboardButton(
                                text=button.get('text', ''),
                                callback_data=button.get('callback_data'),
                                url=button.get('url')
                            )
                        )
                    keyboard.append(keyboard_row)
                telegram_reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                # Convert to ReplyKeyboardMarkup (regular keyboard)
                from telegram import KeyboardButton, ReplyKeyboardMarkup
                keyboard = []
                for row in reply_markup:
                    keyboard_row = []
                    for button in row:
                        keyboard_row.append(
                            KeyboardButton(
                                text=button.get('text', ''),
                                request_contact=button.get('request_contact', False),
                                request_location=button.get('request_location', False)
                            )
                        )
                    keyboard.append(keyboard_row)
                telegram_reply_markup = ReplyKeyboardMarkup(
                    keyboard,
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
        else:
            telegram_reply_markup = reply_markup
    
    # 1. Send text immediately (low latency)
    text_message = await bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=telegram_reply_markup,
        parse_mode=parse_mode,
        reply_to_message_id=reply_to_message_id
    )
    
    logger.info(f"✅ Text sent: {len(message)} chars to chat {chat_id}")
    
    # 2. Generate and send voice (non-blocking)
    # Send voice if enabled, regardless of keyboard presence
    # (Dual delivery is important for accessibility)
    if send_voice:
        # Look up user preference from database
        user_preference_language = None
        try:
            db = SessionLocal()
            try:
                user = db.query(UserIdentity).filter_by(
                    telegram_user_id=str(chat_id)
                ).first()
                if user and user.preferred_language:
                    user_preference_language = user.preferred_language
                    logger.info(f"Found user preference: {user_preference_language} for chat {chat_id}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not lookup user preference: {e}")
        
        # Run in background - but must await in Celery context
        # In Celery workers, the event loop closes when task completes,
        # so we must await the voice generation to ensure it completes
        try:
            logger.info(f"Using user preference language: {user_preference_language}")
            await _generate_and_send_voice(
                bot, 
                chat_id, 
                message, 
                language,
                text_message.message_id,  # Reply to the text message
                user_preference_language  # Pass user preference
            )
        except Exception as e:
            logger.error(f"Voice generation failed: {e}")


def send_voice_reply_sync(
    bot: Bot,
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    language: Optional[str] = None,
    send_voice: bool = True,
    reply_to_message_id: Optional[int] = None
):
    """
    Synchronous wrapper for send_voice_reply.
    
    Use this in non-async contexts.
    
    Args:
        Same as send_voice_reply
    """
    return asyncio.run(
        send_voice_reply(
            bot, chat_id, message, parse_mode,
            language, send_voice, reply_to_message_id
        )
    )
