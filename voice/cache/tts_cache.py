"""
TTS cache: File-based caching for Text-to-Speech audio.

Goal:
- Cache generated TTS audio files to reduce API costs (OpenAI/AddisAI) and latency.
- Store files on disk with a hashed filename based on content.

Key format:
- voice/cache/tts/{language}/{voice}/{sha256(text)}.{ext}
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from voice.logging_config import get_logger

logger = get_logger(__name__)


class TTSCache:
    """
    FileSystem-based cache for TTS audio files.
    """
    
    def __init__(self, cache_dir: str = "voice/cache/tts"):
        """
        Initialize TTS cache.
        
        Args:
            cache_dir: Base directory for storing cached audio files.
                       Defaults to 'voice/cache/tts' relative to CWD.
        """
        self.base_dir = Path(os.getcwd()) / cache_dir
        self._ensure_dir(self.base_dir)
        logger.info(f"TTS Cache initialized at: {self.base_dir}")

    def _ensure_dir(self, path: Path):
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, text: str, language: str, voice: str, format: str) -> Path:
        """
        Generate cache file path based on content hash.
        
        Structure: {base_dir}/{language}/{voice}/{text_hash}.{format}
        """
        normalized_text = text.strip()
        text_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
        safe_voice = str(voice) if voice else "default"
        safe_lang = str(language) if language else "unknown"
        
        safe_voice = "".join(c for c in safe_voice if c.isalnum() or c in ('-', '_'))
        safe_lang = "".join(c for c in safe_lang if c.isalnum() or c in ('-', '_'))
        
        directory = self.base_dir / safe_lang / safe_voice
        self._ensure_dir(directory)
        
        return directory / f"{text_hash}.{format}"

    def get_cached_audio(
        self, 
        text: str, 
        language: str, 
        voice: Optional[str] = None, 
        format: str = "mp3"
    ) -> Optional[bytes]:
        """
        Retrieve audio bytes from cache if exists.
        
        Args:
            text: Text content
            language: Language code
            voice: Voice ID/name
            format: Audio format extension (mp3, wav, etc.)
            
        Returns:
            Audio bytes if cached, None otherwise.
        """
        try:
            path = self._get_cache_path(text, language, voice, format)
            if path.exists():
                logger.info(f"TTS Cache HIT: {path.name}")
                return path.read_bytes()
        except Exception as e:
            logger.warning(f"Error reading from TTS cache: {e}")
        
        return None

    def save_audio(
        self, 
        text: str, 
        language: str, 
        audio_bytes: bytes, 
        voice: Optional[str] = None, 
        format: str = "mp3"
    ) -> Optional[Path]:
        """
        Save audio bytes to cache.
        
        Args:
            text: Text content
            language: Language code
            audio_bytes: Audio data to save
            voice: Voice ID/name
            format: Audio format extension
            
        Returns:
            Path to saved file if successful, None otherwise.
        """
        try:
            path = self._get_cache_path(text, language, voice, format)
            path.write_bytes(audio_bytes)
            logger.info(f"TTS Cache SAVED: {path.name} ({len(audio_bytes)} bytes)")
            return path
        except Exception as e:
            logger.error(f"Error writing to TTS cache: {e}")
            return None

_tts_cache = None

def get_tts_cache() -> TTSCache:
    """Get global TTS cache instance."""
    global _tts_cache
    if _tts_cache is None:
        _tts_cache = TTSCache()
    return _tts_cache
