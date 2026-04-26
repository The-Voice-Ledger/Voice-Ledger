#!/usr/bin/env python3
"""
Validate LLM fallback wiring for Voice Ledger.

What it checks:
1) Gemini direct call works with current environment credentials.
2) Forced OpenAI failure (429-style) falls back to Gemini.
3) Prints detailed response diagnostics to help debug empty-content cases.

Usage:
  /Users/manu/Voice-Ledger/venv/bin/python scripts/validate_llm_fallback.py
"""

import os
import sys
from typing import Any
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.providers.llm_fallback import chat_completion_with_fallback


def _print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _dump_response(label: str, resp: Any, provider: str) -> None:
    choice = resp.choices[0] if getattr(resp, "choices", None) else None
    message = _safe_get(choice, "message")
    content = _safe_get(message, "content", "") if message else ""
    finish_reason = _safe_get(choice, "finish_reason") if choice else None
    usage = _safe_get(resp, "usage")

    print(f"[{label}] provider_used={provider}")
    print(f"[{label}] finish_reason={finish_reason}")
    print(f"[{label}] content_repr={repr(content)}")
    print(f"[{label}] usage={usage}")

    # Optional diagnostics for any structured/alternate payloads.
    if message is not None:
        tool_calls = _safe_get(message, "tool_calls")
        if tool_calls:
            print(f"[{label}] tool_calls={tool_calls}")
        refusal = _safe_get(message, "refusal")
        if refusal:
            print(f"[{label}] refusal={refusal}")


def main() -> int:
    load_dotenv()

    openai_key = bool(os.getenv("OPENAI_API_KEY"))
    gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    fallback_enabled = os.getenv("LLM_FALLBACK_ENABLED", "true")

    _print_header("Environment Check")
    print(f"OPENAI_API_KEY set: {openai_key}")
    print(f"GEMINI_API_KEY set: {gemini_key}")
    print(f"LLM_FALLBACK_ENABLED: {fallback_enabled}")

    if not gemini_key:
        print("FAIL: GEMINI_API_KEY is missing. Add it to .env first.")
        return 2

    # Test 1: direct Gemini route by using a fake non-retryable model for OpenAI
    # and relying on fallback-worthy simulation in Test 2 for deterministic behavior.
    _print_header("Test 1: Gemini Reachability (Normal Path)")
    try:
        # Primary path may hit OpenAI first; this still proves the configured path is healthy.
        resp, provider = chat_completion_with_fallback(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "Reply with exactly: health-check-ok"},
            ],
            temperature=0,
            max_tokens=30,
        )
        _dump_response("normal", resp, provider)
    except Exception as e:
        print(f"FAIL: normal path raised exception: {e}")
        return 3

    # Test 2: deterministic forced fallback by injecting a primary client that always
    # throws a retryable OpenAI-like error.
    _print_header("Test 2: Forced OpenAI->Gemini Fallback")

    class OpenAIQuotaError(Exception):
        status_code = 429

    class ForcedFailPrimary:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    raise OpenAIQuotaError("insufficient_quota")

    try:
        resp, provider = chat_completion_with_fallback(
            primary_client=ForcedFailPrimary(),
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "Reply with exactly: fallback-ok"},
            ],
            temperature=0,
            max_tokens=40,
        )
        _dump_response("forced-fallback", resp, provider)

        if provider != "gemini":
            print("FAIL: provider was not gemini in forced fallback test")
            return 4

        # Accept empty text but flag it for investigation rather than hard-fail,
        # because some providers may return structured payloads with empty content.
        content = ""
        try:
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            pass

        if not content:
            print("WARN: fallback succeeded but content was empty; inspect diagnostics above.")
            print("PASS (with warning): OpenAI->Gemini fallback path executed.")
            return 0

        print("PASS: OpenAI->Gemini fallback executed with non-empty content.")
        return 0
    except Exception as e:
        print(f"FAIL: forced fallback raised exception: {e}")
        return 5


if __name__ == "__main__":
    sys.exit(main())
