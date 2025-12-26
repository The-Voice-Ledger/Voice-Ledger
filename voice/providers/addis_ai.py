"""
AddisAI Provider Module

Provides unified access to AddisAI API capabilities:
- Speech-to-Text (STT) via chat_generate endpoint with audio input
- Text-to-Speech (TTS) via audio endpoint
- Conversational AI via chat_generate endpoint

The chat_generate endpoint accepts audio and returns BOTH transcription and conversational response,
enabling efficient 2-in-1 API calls for voice interfaces.

Author: Voice Ledger Team
Date: December 25, 2025
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import base64

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AddisAIError(Exception):
    """Base exception for AddisAI API errors"""
    pass


class AddisAIProvider:
    """
    AddisAI API client for speech and conversational AI capabilities.
    
    Supports:
    - STT: Audio → Text transcription (Amharic, Afan Oromo)
    - TTS: Text → Audio synthesis (Amharic, Afan Oromo)
    - Chat: Conversational AI with context management
    - Multi-modal: Audio + Text → Transcription + AI Response (single call)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize AddisAI provider.
        
        Args:
            api_key: AddisAI API key (defaults to ADDIS_AI_API_KEY env var)
            base_url: API base URL (defaults to ADDIS_AI_BASE_URL env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("ADDIS_AI_API_KEY")
        self.base_url = (base_url or os.getenv(
            "ADDIS_AI_BASE_URL",
            "https://api.addisassistant.com/api"
        )).rstrip('/')
        
        self.timeout = timeout
        
        # Endpoint paths
        self.chat_endpoint = os.getenv("ADDIS_AI_CHAT_ENDPOINT", "/v1/chat_generate")
        self.tts_endpoint = os.getenv("ADDIS_AI_TTS_ENDPOINT", "/v1/audio")
        
        if not self.api_key:
            logger.warning("AddisAI API key not set. Provider will not be functional.")
        else:
            logger.info("AddisAI provider initialized successfully")
    
    async def transcribe(
        self,
        audio_path: str,
        language: str = "am",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        return_ai_response: bool = False
    ) -> Dict[str, Any]:
        """
        Transcribe audio file to text using AddisAI.
        
        This uses the chat_generate endpoint with audio input, which returns
        both transcription AND conversational AI response in a single call.
        
        Args:
            audio_path: Path to audio file
            language: Target language ("am" for Amharic, "om" for Afan Oromo)
            conversation_history: Optional conversation context
            return_ai_response: If True, return AI conversational response
            
        Returns:
            {
                "text": str,              # Transcribed text (cleaned)
                "language": str,          # Language code
                "confidence": float,      # Confidence score (0-1)
                "provider": str,          # "addisai"
                "raw_transcription": str, # Raw transcription with markdown
                "ai_response": str,       # AI conversational response (if return_ai_response=True)
                "raw_response": dict      # Full API response
            }
            
        Raises:
            AddisAIError: If transcription fails
        """
        if not self.api_key:
            raise AddisAIError("AddisAI API key not configured")
        
        audio_path_obj = Path(audio_path)
        if not audio_path_obj.exists():
            raise AddisAIError(f"Audio file not found: {audio_path}")
        
        try:
            # Prepare request data
            request_data = {
                "target_language": language,
                "generation_config": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500
                }
            }
            
            if conversation_history:
                request_data["conversation_history"] = conversation_history
            
            # Prepare multipart form data
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(audio_path, 'rb') as audio_file:
                    files = {
                        "chat_audio_input": (
                            audio_path_obj.name,
                            audio_file,
                            self._get_mime_type(audio_path_obj.suffix)
                        ),
                        "request_data": (
                            None,
                            json.dumps(request_data),
                            "application/json"
                        )
                    }
                    
                    url = f"{self.base_url}{self.chat_endpoint}"
                    logger.info(f"AddisAI STT request: {url}, language: {language}")
                    
                    response = await client.post(
                        url,
                        headers={"X-API-Key": self.api_key},
                        files=files
                    )
                    
                    response.raise_for_status()
                    data = response.json()
            
            # Extract transcription
            raw_transcript = data.get("transcription_clean", "")
            if not raw_transcript:
                raw_transcript = data.get("transcription_raw", "")
            
            # Clean transcription (remove markdown code blocks)
            transcript = self._clean_transcription(raw_transcript)
            
            # Calculate confidence (AddisAI doesn't provide this directly)
            # Use token count as proxy: more tokens generated = higher confidence
            usage = data.get("usage_metadata", {})
            confidence = min(0.95, 0.7 + (usage.get("candidates_token_count", 0) / 1000))
            
            result = {
                "text": transcript,
                "language": language,
                "confidence": confidence,
                "provider": "addisai",
                "raw_transcription": raw_transcript,
                "raw_response": data
            }
            
            # Optionally include AI conversational response
            if return_ai_response:
                result["ai_response"] = data.get("response_text", "")
            
            logger.info(f"AddisAI transcription successful: {len(transcript)} chars, confidence: {confidence:.2f}")
            return result
            
        except httpx.HTTPStatusError as e:
            error_msg = f"AddisAI API error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            raise AddisAIError(error_msg)
        except httpx.TimeoutException:
            error_msg = "AddisAI API timeout"
            logger.error(error_msg)
            raise AddisAIError(error_msg)
        except Exception as e:
            error_msg = f"AddisAI transcription failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AddisAIError(error_msg)
    
    async def text_to_speech(
        self,
        text: str,
        language: str = "am",
        stream: bool = False
    ) -> bytes:
        """
        Convert text to speech using AddisAI TTS.
        
        Args:
            text: Text to synthesize
            language: Language code ("am" or "om")
            stream: Whether to stream audio (currently not implemented)
            
        Returns:
            Audio data as bytes (WAV format, base64-decoded)
            
        Raises:
            AddisAIError: If TTS fails
        """
        if not self.api_key:
            raise AddisAIError("AddisAI API key not configured")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}{self.tts_endpoint}"
                
                response = await client.post(
                    url,
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": text,
                        "language": language,
                        "stream": stream
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Decode base64 audio
                audio_base64 = data.get("audio", "")
                if not audio_base64:
                    raise AddisAIError("No audio data in response")
                
                audio_bytes = base64.b64decode(audio_base64)
                logger.info(f"AddisAI TTS successful: {len(audio_bytes)} bytes")
                return audio_bytes
                
        except httpx.HTTPStatusError as e:
            error_msg = f"AddisAI TTS error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            raise AddisAIError(error_msg)
        except Exception as e:
            error_msg = f"AddisAI TTS failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AddisAIError(error_msg)
    
    async def chat(
        self,
        prompt: str,
        language: str = "am",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Generate conversational AI response using AddisAI.
        
        Args:
            prompt: User's text input
            language: Target language ("am" or "om")
            conversation_history: Previous conversation messages
            temperature: Response randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            {
                "response": str,          # AI response text
                "finish_reason": str,     # Why response ended
                "usage": dict,            # Token usage metadata
                "model_version": str      # Model version used
            }
            
        Raises:
            AddisAIError: If chat generation fails
        """
        if not self.api_key:
            raise AddisAIError("AddisAI API key not configured")
        
        try:
            request_data = {
                "prompt": prompt,
                "target_language": language,
                "generation_config": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
            
            if conversation_history:
                request_data["conversation_history"] = conversation_history
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}{self.chat_endpoint}"
                
                response = await client.post(
                    url,
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=request_data
                )
                
                response.raise_for_status()
                data = response.json()
                
                return {
                    "response": data.get("response_text", ""),
                    "finish_reason": data.get("finish_reason", ""),
                    "usage": data.get("usage_metadata", {}),
                    "model_version": data.get("modelVersion", "")
                }
                
        except httpx.HTTPStatusError as e:
            error_msg = f"AddisAI chat error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            raise AddisAIError(error_msg)
        except Exception as e:
            error_msg = f"AddisAI chat failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AddisAIError(error_msg)
    
    @staticmethod
    def _clean_transcription(text: str) -> str:
        """
        Clean AddisAI transcription output.
        
        AddisAI wraps transcriptions in markdown code blocks:
        ```
        transcribed text here
        ```
        
        This method removes those markers.
        """
        if not text:
            return ""
        
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```") and text.endswith("```"):
            # Remove first and last lines
            lines = text.split('\n')
            if len(lines) > 2:
                text = '\n'.join(lines[1:-1])
            else:
                # Just strip the backticks
                text = text.strip("`")
        
        return text.strip()
    
    @staticmethod
    def _get_mime_type(file_extension: str) -> str:
        """Get MIME type for audio file extension"""
        mime_types = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac"
        }
        return mime_types.get(file_extension.lower(), "audio/wav")


# Synchronous wrappers for backward compatibility
def transcribe_sync(
    audio_path: str,
    language: str = "am",
    **kwargs
) -> Dict[str, Any]:
    """
    Synchronous wrapper for transcribe().
    
    Use this in sync contexts where you can't use await.
    Handles both cases: new event loop and existing event loop.
    """
    provider = AddisAIProvider()
    
    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
        # If we get here, there's already a loop running
        # We need to use run_in_executor or return a coroutine
        # For now, just call the async method directly and let caller handle it
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(provider.transcribe(audio_path, language, **kwargs))
            )
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        return asyncio.run(provider.transcribe(audio_path, language, **kwargs))


def text_to_speech_sync(
    text: str,
    language: str = "am",
    **kwargs
) -> bytes:
    """
    Synchronous wrapper for text_to_speech().
    """
    provider = AddisAIProvider()
    return asyncio.run(provider.text_to_speech(text, language, **kwargs))


def chat_sync(
    prompt: str,
    language: str = "am",
    **kwargs
) -> Dict[str, Any]:
    """
    Synchronous wrapper for chat().
    """
    provider = AddisAIProvider()
    return asyncio.run(provider.chat(prompt, language, **kwargs))


# Module-level instance for convenience
_default_provider = None

def get_provider() -> AddisAIProvider:
    """Get or create default AddisAI provider instance"""
    global _default_provider
    if _default_provider is None:
        _default_provider = AddisAIProvider()
    return _default_provider
