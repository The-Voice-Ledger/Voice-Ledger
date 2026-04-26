import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_build_livekit_llm_prefers_openai_when_healthy(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    monkeypatch.delenv("LIVEKIT_LLM_PROVIDER", raising=False)

    monkeypatch.setattr(m, "_openai_llm_healthy", lambda: True)

    captured = {}

    class FakeLLM:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.openai, "LLM", FakeLLM)

    _llm, provider, model = m._build_livekit_llm()

    assert provider == "openai"
    assert model == "gpt-4o-mini"
    assert captured.get("model") == "gpt-4o-mini"
    assert "base_url" not in captured


def test_build_livekit_llm_falls_back_to_gemini_when_openai_unhealthy(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    monkeypatch.delenv("LIVEKIT_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(m, "lk_google", None)

    monkeypatch.setattr(m, "_openai_llm_healthy", lambda: False)

    captured = {}

    class FakeLLM:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.openai, "LLM", FakeLLM)

    _llm, provider, model = m._build_livekit_llm()

    assert provider == "gemini"
    assert model == "gemini-2.5-flash"
    assert captured.get("model") == "gemini-2.5-flash"
    assert captured.get("api_key") == "test-gemini"
    assert "generativelanguage.googleapis.com" in (captured.get("base_url") or "")


def test_build_livekit_llm_respects_gemini_mode(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("LIVEKIT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setattr(m, "lk_google", None)

    captured = {}

    class FakeLLM:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.openai, "LLM", FakeLLM)

    _llm, provider, model = m._build_livekit_llm()

    assert provider == "gemini"
    assert model == "gemini-2.5-flash"
    assert captured.get("api_key") == "test-gemini"


def test_openai_healthcheck_respects_circuit_breaker(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("LIVEKIT_OPENAI_CIRCUIT_TTL_SEC", "60")
    monkeypatch.setattr(m, "_OPENAI_CIRCUIT_OPEN_UNTIL", 0.0)

    m._trip_openai_circuit("insufficient_quota")
    assert m._openai_circuit_open() is True
    assert m._openai_llm_healthy() is False


def test_build_livekit_tts_uses_deepgram_with_gemini_provider(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("DEEPGRAM_API_KEY", "deepgram-test")
    monkeypatch.delenv("LIVEKIT_TTS_PROVIDER", raising=False)

    captured = {}

    class FakeTTS:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.deepgram, "TTS", FakeTTS)

    _tts = m._build_livekit_tts("gemini")
    assert captured.get("api_key") == "deepgram-test"


def test_build_livekit_tts_falls_back_to_openai_when_no_deepgram_key(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("LIVEKIT_TTS_PROVIDER", "auto")

    captured = {}

    class FakeOpenAITTS:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.openai, "TTS", FakeOpenAITTS)

    _tts = m._build_livekit_tts("gemini")
    assert captured.get("model") == "tts-1"


def test_build_livekit_tts_prefers_deepgram_in_auto_when_fallback_enabled(monkeypatch):
    import voice.livekit_agent as m

    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "deepgram-test")
    monkeypatch.setenv("LIVEKIT_TTS_PROVIDER", "auto")

    captured = {}

    class FakeDeepgramTTS:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(m.deepgram, "TTS", FakeDeepgramTTS)

    _tts = m._build_livekit_tts("openai")
    assert captured.get("api_key") == "deepgram-test"
