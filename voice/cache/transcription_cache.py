"""
Transcription cache: hash-based Redis cache for ASR results.

Reduces Whisper/AddisAI API cost and latency when the same audio is
processed again (e.g. retries, duplicate uploads, tests).

Key format: voice:transcription:{language}:{sha256(audio_bytes)}
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
        logger.debug("Transcription cache disabled: no REDIS_URL / CELERY_BROKER_URL")
        return None
    try:
        import redis
        _redis_client = redis.from_url(redis_url)
        _redis_client.ping()
        logger.info("Transcription cache: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning("Transcription cache disabled: Redis unavailable: %s", e)
        _redis_client = None
        return None


def compute_audio_hash(audio_path: str) -> str:
    """SHA-256 hash of audio file contents (same file => same hash)."""
    h = hashlib.sha256()
    with open(audio_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_key(audio_hash: str, language: str) -> str:
    lang = (language or "auto").lower()
    return f"voice:transcription:{lang}:{audio_hash}"


def get_cached_transcription(audio_hash: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return cached result if present: {"text": str, "language": str}.
    language is used as part of the key (e.g. "en", "am", "auto").
    """
    client = _get_redis_client()
    if not client:
        return None
    key = _cache_key(audio_hash, language or "auto")
    try:
        raw = client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        logger.info("Transcription cache HIT key=%s", key[:60] + "...")
        return data
    except Exception as e:
        logger.warning("Transcription cache get failed: %s", e)
        return None


def set_cached_transcription(
    audio_hash: str,
    language: str,
    data: Dict[str, Any],
    ttl_seconds: int = 24 * 3600,
) -> None:
    """Store transcription result. data must include 'text' and 'language'."""
    client = _get_redis_client()
    if not client:
        return
    key = _cache_key(audio_hash, language)
    try:
        client.setex(key, ttl_seconds, json.dumps(data))
        logger.info("Transcription cache SET key=%s ttl=%ds", key[:60] + "...", ttl_seconds)
    except Exception as e:
        logger.warning("Transcription cache set failed: %s", e)
