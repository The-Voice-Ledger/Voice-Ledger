"""
RAG query cache: Redis-backed caching for knowledge base retrieval.

Goal (from architecture doc):
- Cache common RAG queries to reduce ChromaDB latency and OpenAI
  embedding calls.

Key:
- voice:rag:{query_type}:{top_k}:{sha256(normalized_query)}
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_redis_client: Optional[Any] = None


def _get_redis_client():
    """Lazy-init Redis client using REDIS_URL or CELERY_BROKER_URL."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL")
    if not redis_url:
        logger.debug("RAG cache disabled: REDIS_URL / CELERY_BROKER_URL not set")
        return None

    try:
        import redis

        _redis_client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        _redis_client.ping()
        logger.info("RAG cache: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning("RAG cache disabled: cannot connect to Redis: %s", e)
        _redis_client = None
        return None


def _normalize_query(query: str) -> str:
    """Lightweight normalization: trim + lowercase."""
    return " ".join(query.strip().lower().split())


def compute_query_hash(query: str) -> str:
    """Compute stable hash for a normalized query."""
    norm = _normalize_query(query)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _cache_key(query_hash: str, query_type: str, top_k: int) -> str:
    qt = (query_type or "any").lower()
    return f"voice:rag:{qt}:{top_k}:{query_hash}"


def get_cached_rag_results(
    query: str,
    query_type: Optional[str],
    top_k: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    Return cached RAG results for (query, query_type, top_k) if present.

    Results are the same structure as search_knowledge_base() returns:
    [{content, similarity, distance, metadata?}, ...]
    """
    client = _get_redis_client()
    if not client:
        return None

    qh = compute_query_hash(query)
    key = _cache_key(qh, query_type or "any", top_k)
    try:
        raw = client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        logger.info(
            "RAG cache HIT key=%s (type=%s, top_k=%s, results=%s)",
            key[:64] + "...",
            query_type,
            top_k,
            len(data) if isinstance(data, list) else "unknown",
        )
        return data
    except Exception as e:
        logger.warning("RAG cache get failed for key=%s: %s", key, e)
        # Return None on any error so normal flow continues
        return None


def set_cached_rag_results(
    query: str,
    query_type: Optional[str],
    top_k: int,
    results: List[Dict[str, Any]],
    ttl_seconds: int = 6 * 3600,
) -> None:
    """Store RAG results in cache (no-op if Redis unavailable)."""
    if not results:
        return

    client = _get_redis_client()
    if not client:
        return

    qh = compute_query_hash(query)
    key = _cache_key(qh, query_type or "any", top_k)

    try:
        payload = json.dumps(results)
        client.setex(key, ttl_seconds, payload)
        logger.info(
            "RAG cache SET key=%s (type=%s, top_k=%s, ttl=%ss, results=%s)",
            key[:64] + "...",
            query_type,
            top_k,
            ttl_seconds,
            len(results),
        )
    except Exception as e:
        logger.warning("RAG cache set failed for key=%s: %s", key, e)
        # Don't raise - caching is optional, don't break main flow

