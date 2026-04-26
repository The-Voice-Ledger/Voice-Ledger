import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.providers import llm_fallback


class _Resp:
    def __init__(self, content="ok"):
        choice = MagicMock()
        choice.message.content = content
        usage = MagicMock()
        usage.total_tokens = 1
        self.choices = [choice]
        self.usage = usage


class _QuotaError(Exception):
    status_code = 429


def test_chat_completion_primary_openai_success(monkeypatch):
    """When OpenAI succeeds, no fallback should be used."""
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")

    primary = MagicMock()

    def fake_create(client, model, messages, provider, kwargs):
        assert provider == "openai"
        return _Resp("from-openai")

    monkeypatch.setattr(llm_fallback, "_create_chat_completion", fake_create)

    resp, provider = llm_fallback.chat_completion_with_fallback(
        primary_client=primary,
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert provider == "openai"
    assert resp.choices[0].message.content == "from-openai"


def test_chat_completion_falls_back_to_gemini_on_quota(monkeypatch):
    """OpenAI quota/rate failures should transparently fail over to Gemini."""
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class Primary:
        pass

    primary = Primary()
    gemini = MagicMock()

    monkeypatch.setattr(llm_fallback, "_gemini_client", lambda: gemini)

    calls = []

    def fake_create(client, model, messages, provider, kwargs):
        calls.append((provider, model))
        if provider == "openai":
            raise _QuotaError("insufficient_quota")
        return _Resp("from-gemini")

    monkeypatch.setattr(llm_fallback, "_create_chat_completion", fake_create)

    resp, provider = llm_fallback.chat_completion_with_fallback(
        primary_client=primary,
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert calls[0][0] == "openai"
    assert calls[1][0] == "gemini"
    assert provider == "gemini"
    assert resp.choices[0].message.content == "from-gemini"


def test_chat_completion_does_not_fallback_for_non_retryable(monkeypatch):
    """Prompt/schema type errors should be raised directly, not fail over."""
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    primary = MagicMock()

    def fake_create(client, model, messages, provider, kwargs):
        raise ValueError("invalid request schema")

    monkeypatch.setattr(llm_fallback, "_create_chat_completion", fake_create)

    with pytest.raises(ValueError, match="invalid request schema"):
        llm_fallback.chat_completion_with_fallback(
            primary_client=primary,
            model="gpt-4o",
            messages=[{"role": "user", "content": "hello"}],
        )


def test_chat_completion_respects_disable_flag(monkeypatch):
    """Fallback must be disabled when LLM_FALLBACK_ENABLED=false."""
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    primary = MagicMock()

    def fake_create(client, model, messages, provider, kwargs):
        raise _QuotaError("insufficient_quota")

    monkeypatch.setattr(llm_fallback, "_create_chat_completion", fake_create)

    with pytest.raises(_QuotaError):
        llm_fallback.chat_completion_with_fallback(
            primary_client=primary,
            model="gpt-4o",
            messages=[{"role": "user", "content": "hello"}],
        )
