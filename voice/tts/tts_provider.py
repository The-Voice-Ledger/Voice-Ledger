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
import base64
from typing import Optional, Dict, Literal
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger(__name__)

# Import TTS cache
try:
    from voice.cache.tts_cache import get_cached_tts_audio, set_cached_tts_audio
    TTS_CACHE_AVAILABLE = True
    logger.info("TTS cache module loaded successfully")
except ImportError as e:
    logger.warning(f"TTS cache not available: {e}")
    TTS_CACHE_AVAILABLE = False

# OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Addis AI configuration
ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
ADDIS_AI_TTS_URL = "https://api.addisassistant.com/api/v1/audio"


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
        # Check cache first
        if TTS_CACHE_AVAILABLE:
            cached_audio = get_cached_tts_audio(text, language, voice)
            if cached_audio:
                logger.info(f"TTS cache HIT for text: {text[:50]}...")
                return cached_audio
            else:
                logger.info(f"TTS cache MISS for text: {text[:50]}...")
        
        # Generate new audio
        audio = None
        if language == 'am':
            audio = await TTSProvider._addis_ai_tts(text, voice)
        else:
            # Try OpenAI first
            try:
                audio = await TTSProvider._openai_tts(text, voice, output_format)
            except Exception as openai_error:
                logger.warning(f"OpenAI TTS failed: {openai_error}")
                
                # Try Deepgram TTS fallback (same as LiveKit agent)
                try:
                    import os
                    
                    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
                    deepgram_model = os.getenv("LIVEKIT_DEEPGRAM_TTS_MODEL", "aura-2-andromeda-en")
                    
                    if deepgram_key:
                        logger.info("Attempting Deepgram TTS fallback")
                        
                        # Generate speech using Deepgram API directly
                        try:
                            import httpx
                            
                            # Deepgram API endpoint
                            deepgram_url = f"https://api.deepgram.com/v1/speak?model={deepgram_model}"
                            
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                response = await client.post(
                                    deepgram_url,
                                    headers={
                                        "Authorization": f"Token {deepgram_key}",
                                        "Content-Type": "application/json"
                                    },
                                    json={"text": text}
                                )
                                response.raise_for_status()
                                
                                # Get audio data from response
                                audio_data = response.content
                                if audio_data:
                                    logger.info("Deepgram TTS fallback successful")
                                    audio = audio_data
                                else:
                                    logger.warning("Deepgram TTS fallback returned empty audio")
                                    raise openai_error
                                    
                        except httpx.HTTPStatusError as http_error:
                            logger.error(f"Deepgram TTS HTTP error: {http_error.response.status_code} - {http_error.response.text}")
                            raise openai_error
                        except Exception as synthesis_error:
                            logger.error(f"Deepgram TTS synthesis failed: {synthesis_error}")
                            raise openai_error
                            
                    else:
                        logger.warning("Deepgram TTS API key not available for fallback")
                        raise openai_error
                        
                except Exception as fallback_error:
                    logger.error(f"Deepgram TTS fallback failed: {fallback_error}")
                    # Re-raise original OpenAI error if fallback fails
                    raise openai_error
        
        # Cache the generated audio
        if TTS_CACHE_AVAILABLE and audio:
            set_cached_tts_audio(text, language, audio, voice)
            
        return audio
    
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
                
                # Parse JSON response and decode base64 audio
                response_data = response.json()
                audio_base64 = response_data.get("audio")
                
                if not audio_base64:
                    raise Exception("No audio field in Addis AI response")
                
                # Decode base64 to get actual audio bytes
                audio_bytes = base64.b64decode(audio_base64)
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
