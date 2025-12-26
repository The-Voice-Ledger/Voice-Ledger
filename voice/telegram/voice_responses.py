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
from openai import AsyncOpenAI
from dotenv import load_dotenv

from voice.providers.addis_ai import AddisAIProvider
from database.models import SessionLocal, UserIdentity

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize TTS providers
addisai_provider = AddisAIProvider()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
        
        # Prioritize: explicit language > user preference > text detection
        if language is None:
            if user_preference_language:
                language = user_preference_language
                logger.info(f"Using user preference language: {language}")
            else:
                language = detect_language(clean_text)
                logger.info(f"Using text-detected language: {language}")
        
        logger.info(f"🎤 Generating TTS: {len(clean_text)} chars, lang: {language}, chat: {chat_id}")
        
        # Route TTS based on language
        audio_bytes = None
        
        if language == "am":
            # Use AddisAI for Amharic
            try:
                audio_bytes = await addisai_provider.text_to_speech(
                    text=clean_text,
                    language="am"
                )
                logger.info(f"✅ AddisAI TTS generated: {len(audio_bytes)} bytes")
            except Exception as e:
                logger.error(f"AddisAI TTS failed: {e}")
        else:
            # Use OpenAI for English (and other languages)
            try:
                response = await openai_client.audio.speech.create(
                    model="tts-1",
                    voice="nova",
                    input=clean_text
                )
                audio_bytes = response.content
                logger.info(f"✅ OpenAI TTS generated: {len(audio_bytes)} bytes")
            except Exception as e:
                logger.error(f"OpenAI TTS failed: {e}")
        
        if audio_bytes:
            # Save to temporary file for Telegram upload
            import tempfile
            suffix = '.wav' if language == "am" else '.mp3'
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
                
                logger.info(f"✅ Voice reply sent: {len(clean_text)} chars, lang: {language}")
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
    reply_to_message_id: Optional[int] = None
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
    
    Example:
        await send_voice_reply(
            bot=context.bot,
            chat_id=user_id,
            message="✅ Batch recorded successfully!"
        )
    """
    
    # 1. Send text immediately (low latency)
    text_message = await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode=parse_mode,
        reply_to_message_id=reply_to_message_id
    )
    
    logger.info(f"✅ Text sent: {len(message)} chars to chat {chat_id}")
    
    # 2. Generate and send voice (non-blocking)
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
        
        # Run in background - doesn't block
        asyncio.create_task(
            _generate_and_send_voice(
                bot, 
                chat_id, 
                message, 
                language,
                text_message.message_id,  # Reply to the text message
                user_preference_language  # Pass user preference
            )
        )


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
