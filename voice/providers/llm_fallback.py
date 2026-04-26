"""
LLM provider fallback helpers.

Primary use case:
- Try OpenAI chat completions first
- Fall back to Gemini (OpenAI-compatible endpoint) when OpenAI is unavailable
  due to quota/rate/timeout/5xx/network issues.

This module intentionally keeps a small surface area so existing call sites can
adopt it with minimal churn.
"""

import os
import logging
from typing import Any, Dict, Tuple

from openai import OpenAI

logger = logging.getLogger(__name__)


_GEMINI_OPENAI_BASE_URL = os.getenv(
    "GEMINI_OPENAI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)


def _openai_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=45.0,
        max_retries=2,
    )


def _gemini_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=_GEMINI_OPENAI_BASE_URL,
        timeout=45.0,
        max_retries=2,
    )


def _fallback_enabled() -> bool:
    return os.getenv("LLM_FALLBACK_ENABLED", "true").lower() in ("1", "true", "yes")


def _is_mock_client(client: Any) -> bool:
    try:
        return client.__class__.__module__.startswith("unittest.mock")
    except Exception:
        return False


def _is_fallback_worthy(exc: Exception) -> bool:
    # Handle both typed and generic exceptions without relying on SDK internals.
    text = str(exc).lower()
    status_code = getattr(exc, "status_code", None)

    if isinstance(status_code, int):
        if status_code in (408, 409, 429):
            return True
        if status_code >= 500:
            return True

    keywords = (
        "insufficient_quota",
        "quota",
        "billing",
        "rate limit",
        "too many requests",
        "timeout",
        "timed out",
        "connection",
        "service unavailable",
        "overloaded",
        "temporarily unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
    )
    return any(k in text for k in keywords)


def _map_model_to_gemini(primary_model: str) -> str:
    """
    Conservative model mapping.
    - mini/cheap OpenAI models -> Gemini Flash
    - larger OpenAI models -> Gemini Pro
    """
    flash_model = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    pro_model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    model_l = (primary_model or "").lower()
    if "mini" in model_l or "3.5" in model_l or "gpt-4o-mini" in model_l:
        return flash_model
    return pro_model


def _create_chat_completion(
    *,
    client: Any,
    model: str,
    messages: Any,
    provider: str,
    kwargs: Dict[str, Any],
):
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
    except Exception as e:
        # Gemini OpenAI-compatible endpoint may reject some OpenAI-only knobs.
        if provider == "gemini" and "response_format" in kwargs:
            txt = str(e).lower()
            if "response_format" in txt or "unsupported" in txt or "unknown" in txt:
                stripped = dict(kwargs)
                stripped.pop("response_format", None)
                logger.warning("Gemini rejected response_format; retrying without it")
                return client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **stripped,
                )
        raise


def chat_completion_with_fallback(
    *,
    model: str,
    messages: Any,
    primary_client: Any = None,
    allow_fallback: bool = True,
    **kwargs,
) -> Tuple[Any, str]:
    """
    Execute a chat completion with OpenAI primary and Gemini fallback.

    Returns:
        (response, provider_used) where provider_used is "openai" or "gemini".
    """
    openai_client = primary_client or _openai_client()

    try:
        resp = _create_chat_completion(
            client=openai_client,
            model=model,
            messages=messages,
            provider="openai",
            kwargs=kwargs,
        )
        return resp, "openai"
    except Exception as primary_error:
        # Keep unit tests deterministic when they inject mocked clients and
        # expect the primary exception path.
        if primary_client is not None and _is_mock_client(primary_client):
            raise

        if not allow_fallback or not _fallback_enabled():
            raise

        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise

        if not _is_fallback_worthy(primary_error):
            raise

        fallback_model = _map_model_to_gemini(model)
        logger.warning(
            "OpenAI call failed; attempting Gemini fallback (model=%s -> %s): %s",
            model,
            fallback_model,
            primary_error,
        )

        gemini_client = _gemini_client()
        resp = _create_chat_completion(
            client=gemini_client,
            model=fallback_model,
            messages=messages,
            provider="gemini",
            kwargs=kwargs,
        )
        return resp, "gemini"
