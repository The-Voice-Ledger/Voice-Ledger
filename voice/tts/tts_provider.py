"""
Text-to-Speech (TTS) Provider

Provides TTS capabilities for both English and Amharic:
- English: OpenAI TTS API
- Amharic: Addis AI TTS API

Returns audio files that can be played in browser or sent via Telegram.

Date: December 24, 2025
Lab 17: Bilingual Voice UI - Track 2
"""

import os
import logging
import httpx
from typing import Optional, Dict, Literal
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Addis AI configuration
ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
ADDIS_AI_TTS_URL = "https://api.addisassistant.com/api/v1/audio/speech"


class TTSProvider:
    """
    Text-to-Speech provider abstraction.
    
    Routes TTS requests to appropriate provider based on language:
    - Amharic (am) → Addis AI
    - English (en) → OpenAI
    """
    
    @staticmethod
    async def text_to_speech(
        text: str,
        language: Literal['en', 'am'],
        voice: Optional[str] = None,
        output_format: str = "mp3"
    ) -> bytes:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            language: 'en' for English, 'am' for Amharic
            voice: Voice ID (provider-specific)
            output_format: Audio format (mp3, opus, aac, flac)
            
        Returns:
            Audio bytes (MP3 format)
            
        Raises:
            Exception: If TTS fails
        """
        if language == 'am':
            return await TTSProvider._addis_ai_tts(text, voice)
        else:
            return await TTSProvider._openai_tts(text, voice, output_format)
    
    @staticmethod
    async def _openai_tts(
        text: str,
        voice: Optional[str] = None,
        output_format: str = "mp3"
    ) -> bytes:
        """
        OpenAI TTS for English.
        
        Available voices: alloy, echo, fable, onyx, nova, shimmer
        """
        try:
            voice = voice or "alloy"  # Default voice
            
            logger.info(f"Generating English TTS with OpenAI (voice: {voice})")
            
            response = openai_client.audio.speech.create(
                model="tts-1",  # or "tts-1-hd" for higher quality
                voice=voice,
                input=text,
                response_format=output_format
            )
            
            # Stream to bytes
            audio_bytes = b""
            for chunk in response.iter_bytes():
                audio_bytes += chunk
            
            logger.info(f"Generated {len(audio_bytes)} bytes of English audio")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
            raise Exception(f"English TTS failed: {str(e)}")
    
    @staticmethod
    async def _addis_ai_tts(text: str, voice: Optional[str] = None) -> bytes:
        """
        Addis AI TTS for Amharic.
        
        Available voices: female-1, male-1 (depends on Addis AI)
        """
        try:
            if not ADDIS_AI_API_KEY:
                raise ValueError("ADDIS_AI_API_KEY not set in environment")
            
            voice = voice or "female-1"  # Default Amharic voice
            
            logger.info(f"Generating Amharic TTS with Addis AI (voice: {voice})")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    ADDIS_AI_TTS_URL,
                    headers={
                        "X-API-Key": ADDIS_AI_API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": text,
                        "language": "am",
                        "voice_id": voice
                    }
                )
                response.raise_for_status()
                
                audio_bytes = response.content
                logger.info(f"Generated {len(audio_bytes)} bytes of Amharic audio")
                return audio_bytes
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Addis AI TTS HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Amharic TTS failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Addis AI TTS failed: {e}")
            raise Exception(f"Amharic TTS failed: {str(e)}")
    
    @staticmethod
    async def save_audio_to_file(
        audio_bytes: bytes,
        output_path: Path,
        format: str = "mp3"
    ):
        """
        Save audio bytes to file.
        
        Args:
            audio_bytes: Audio data
            output_path: Output file path
            format: Audio format extension
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        
        logger.info(f"Saved audio to {output_path}")


# Convenience functions
async def generate_speech(
    text: str,
    language: Literal['en', 'am'],
    voice: Optional[str] = None
) -> bytes:
    """
    Generate speech audio from text.
    
    Simple wrapper around TTSProvider.text_to_speech()
    
    Example:
        >>> audio = await generate_speech("Hello world", "en")
        >>> audio = await generate_speech("ሰላም", "am")
    """
    return await TTSProvider.text_to_speech(text, language, voice)
