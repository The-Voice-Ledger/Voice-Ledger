"""
TTS cache: Redis-backed caching for text-to-speech generation.

Reduces OpenAI/AddisAI API cost and latency when the same text
is converted to speech multiple times (e.g., common responses like
/start, /register, help messages, etc.).

Key format: voice:tts:{language}:{voice}:{sha256(normalized_text)}
TTL: 24 hours (configurable).
"""

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path for logging config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging
from voice.logging_config import get_logger
logger = get_logger(__name__)

_redis_client: Optional[Any] = None


def _get_redis_client():
    """Lazy-init Redis from REDIS_URL or CELERY_BROKER_URL."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL")
    if not redis_url:
        logger.debug("TTS cache disabled: no REDIS_URL / CELERY_BROKER_URL")
        return None
    try:
        import redis
        _redis_client = redis.from_url(redis_url)
        _redis_client.ping()
        logger.info("TTS cache: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning("TTS cache disabled: Redis unavailable: %s", e)
        _redis_client = None
        return None


def _normalize_text(text: str) -> str:
    """Normalize text for consistent hashing: trim, lowercase, normalize whitespace."""
    import unicodedata
    
    # Normalize Unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Trim and normalize whitespace
    return " ".join(text.strip().split())


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cache_key(text_hash: str, language: str, voice: Optional[str] = None) -> str:
    """Generate cache key for TTS request."""
    lang = (language or "en").lower()
    voice_str = (voice or "default").lower()
    return f"voice:tts:{lang}:{voice_str}:{text_hash}"


def get_cached_tts_audio(
    text: str,
    language: str,
    voice: Optional[str] = None
) -> Optional[bytes]:
    """
    Return cached TTS audio bytes if present.
    
    Args:
        text: Text that was converted to speech
        language: Language code ('en', 'am', etc.)
        voice: Voice ID used for generation
        
    Returns:
        Audio bytes if cached, None otherwise
    """
    client = _get_redis_client()
    if not client:
        return None
    
    text_hash = compute_text_hash(text)
    key = _cache_key(text_hash, language, voice)
    
    try:
        raw = client.get(key)
        if not raw:
            return None
        
        # Data is stored as JSON with metadata
        data = json.loads(raw)
        audio_bytes = data.get("audio")
        
        if audio_bytes:
            # Convert base64 back to bytes
            import base64
            audio_data = base64.b64decode(audio_bytes)
            logger.info(
                "TTS cache HIT key=%s (lang=%s, voice=%s, size=%s bytes)",
                key[:60] + "...",
                language,
                voice or "default",
                len(audio_data)
            )
            return audio_data
        
        return None
        
    except Exception as e:
        logger.warning("TTS cache get failed: %s", e)
        return None


def set_cached_tts_audio(
    text: str,
    language: str,
    audio_bytes: bytes,
    voice: Optional[str] = None,
    ttl_seconds: int = 24 * 3600,
) -> None:
    """
    Store TTS audio result in cache.
    
    Args:
        text: Original text that was converted
        language: Language code ('en', 'am', etc.)
        audio_bytes: Generated audio data
        voice: Voice ID used for generation
        ttl_seconds: Cache TTL in seconds (default: 24 hours)
    """
    client = _get_redis_client()
    if not client:
        return
    
    text_hash = compute_text_hash(text)
    key = _cache_key(text_hash, language, voice)
    
    try:
        # Store audio as base64 in JSON with metadata
        import base64
        data = {
            "audio": base64.b64encode(audio_bytes).decode('utf-8'),
            "text_length": len(text),
            "language": language,
            "voice": voice or "default",
            "audio_size": len(audio_bytes),
            "cached_at": str(Path(__file__).stat().st_mtime)
        }
        
        client.setex(key, ttl_seconds, json.dumps(data))
        logger.info(
            "TTS cache SET key=%s (lang=%s, voice=%s, size=%s bytes, ttl=%ds)",
            key[:60] + "...",
            language,
            voice or "default",
            len(audio_bytes),
            ttl_seconds
        )
        
    except Exception as e:
        logger.warning("TTS cache set failed: %s", e)


def invalidate_tts_cache(
    text: Optional[str] = None,
    language: Optional[str] = None,
    voice: Optional[str] = None
) -> None:
    """
    Invalidate TTS cache entries.
    
    Args:
        text: Specific text to invalidate (if None, matches all)
        language: Specific language to invalidate (if None, matches all)
        voice: Specific voice to invalidate (if None, matches all)
    """
    client = _get_redis_client()
    if not client:
        return
    
    try:
        # Build pattern for keys to delete
        if text:
            text_hash = compute_text_hash(text)
            pattern = _cache_key(text_hash, language or "*", voice or "*")
        else:
            lang = (language or "*").lower()
            voice_str = (voice or "*").lower()
            pattern = f"voice:tts:{lang}:{voice_str}:*"
        
        # Find and delete matching keys
        keys = client.keys(pattern)
        if keys:
            deleted = client.delete(*keys)
            logger.info("TTS cache invalidated: %d keys matching %s", deleted, pattern)
        else:
            logger.info("TTS cache: no keys found matching %s", pattern)
            
    except Exception as e:
        logger.warning("TTS cache invalidation failed: %s", e)
