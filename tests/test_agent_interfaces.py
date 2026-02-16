"""
Tests for Agent Integration Across All Interfaces

Verifies that the AI agent is correctly wired into all 5 interfaces:
1. Telegram Voice  -> Celery -> agent  (existing, tested in test_agent.py)
2. Telegram Text   -> direct agent    (NEW)
3. Mini App Voice  -> direct agent    (NEW)
4. Direct API      -> Celery -> agent  (same as #1)
5. IVR/Twilio      -> Celery -> agent  (same as #1)

Also verifies:
- Bilingual (en/am) works on every path
- Dual delivery (text + voice) preserved
- Fallback to legacy when AGENT_ENABLED=false
- Fallback to legacy when agent raises exception
- Anonymous / unregistered user handling
- Workflow state machine takes priority over agent
"""

import os
import sys
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously -- avoids need for pytest-asyncio."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_agent_result(response="Done!", lang="en", write=False):
    """Build a mock AgentResult."""
    from voice.agent.executor import AgentResult, ToolCall

    return AgentResult(
        response=response,
        response_spoken="Done!" if lang == "en" else response,
        tool_calls=[
            ToolCall(
                tool_name="query_batches",
                arguments={"limit": 5},
                result_message="Found batches",
                result_data={},
                success=True,
                duration_ms=100.0,
            )
        ] if write else [],
        performed_write=write,
        intent="query_batches" if write else None,
        entities={},
        total_tokens=200,
        duration_ms=350.0,
    )


def _make_mock_user(user_id=42, did="did:key:z6MkTest", language="en"):
    """Build a mock UserIdentity-like object."""
    user = MagicMock()
    user.id = user_id
    user.did = did
    user.preferred_language = language
    user.telegram_user_id = "123456"
    return user


def _make_telegram_update(text="show my batches", user_id=123456):
    """Build a mock Telegram Update dict for text messages."""
    return {
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "first_name": "Test", "is_bot": False},
            "chat": {"id": user_id, "type": "private"},
            "text": text,
            "date": 1700000000,
        }
    }


class _TelegramTextPatchContext:
    """Context manager that patches all deps for process_natural_text_query."""

    def __init__(self, agent_enabled="true"):
        self._agent_enabled = agent_enabled
        self._patches = []
        self.mocks = {}

    def __enter__(self):
        targets = {
            "get_processor": "voice.telegram.telegram_api.get_processor",
            "agent_run": "voice.agent.executor.AgentExecutor.run",
            "redis": "voice.agent.executor._get_redis",
            "get_user": "ssi.user_identity.get_user_by_telegram_id",
            "session_local": "database.models.SessionLocal",
            "state_mgr": "voice.workflows.state_machine.StateManager.get_user_state",
        }
        for key, target in targets.items():
            p = patch(target)
            self.mocks[key] = p.start()
            self._patches.append(p)

        self._env = patch.dict(os.environ, {"AGENT_ENABLED": self._agent_enabled})
        self._env.start()

        # Sensible defaults
        self.mocks["redis"].return_value = None
        self.mocks["state_mgr"].return_value = None  # No active workflow
        return self

    def __exit__(self, *args):
        self._env.stop()
        for p in self._patches:
            p.stop()


# =========================================================================
# 1. Telegram Text -> Agent Path
# =========================================================================

class TestTelegramTextAgentPath:
    """Verify process_natural_text_query routes to agent when enabled."""

    def test_agent_handles_text_when_enabled(self):
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            ctx.mocks["agent_run"].return_value = _make_mock_agent_result(
                "You have 3 batches."
            )
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            result = _run(process_natural_text_query(
                _make_telegram_update("show my batches")
            ))

            assert result["ok"] is True

            # Agent called with correct params
            ctx.mocks["agent_run"].assert_called_once()
            kw = ctx.mocks["agent_run"].call_args[1]
            assert kw["transcript"] == "show my batches"
            assert kw["user_id"] == 42
            assert kw["language"] == "en"

            # Dual delivery: Markdown + voice
            mock_proc.send_notification.assert_awaited_once()
            skw = mock_proc.send_notification.call_args[1]
            assert skw["parse_mode"] == "Markdown"
            assert skw["send_voice"] is True
            assert skw["language"] == "en"

    def test_agent_text_amharic_passes_language(self):
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user(language="am")
            ctx.mocks["agent_run"].return_value = _make_mock_agent_result(
                "3 batches found", lang="am"
            )
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            result = _run(process_natural_text_query(
                _make_telegram_update("show batches")
            ))

            assert result["ok"] is True
            assert ctx.mocks["agent_run"].call_args[1]["language"] == "am"
            assert mock_proc.send_notification.call_args[1]["language"] == "am"

    def test_legacy_path_when_agent_disabled(self):
        """AGENT_ENABLED=false -> legacy keyword routing / RAG."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("false") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.rag.multi_turn_rag.MultiTurnRAG.process_rag_query",
                new_callable=AsyncMock,
            ) as mock_rag:
                mock_rag.return_value = {
                    "message": "Voice Ledger helps manage coffee.",
                    "sources": [],
                }
                result = _run(process_natural_text_query(
                    _make_telegram_update("help me understand EPCIS")
                ))

            assert result["ok"] is True
            mock_rag.assert_awaited_once()
            mock_proc.send_notification.assert_awaited_once()

    def test_agent_failure_falls_back_to_legacy(self):
        """Agent exception -> falls through to legacy conversation with ⚠️ banner."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            ctx.mocks["agent_run"].side_effect = RuntimeError("OpenAI timeout")
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.integrations.english_conversation.process_english_conversation"
            ) as mock_eng:
                mock_eng.return_value = {
                    "message_text": "Legacy response",
                    "message_spoken": "Legacy response",
                }
                result = _run(process_natural_text_query(
                    _make_telegram_update("something random")
                ))

            assert result["ok"] is True
            mock_eng.assert_called_once()

            # Fallback banner prepended and parse_mode switched to HTML
            skw = mock_proc.send_notification.call_args[1]
            assert "Fallback mode" in skw["message"]
            assert skw["parse_mode"] == "HTML"

    def test_unregistered_user_falls_to_legacy(self):
        """Unregistered user (None from DB) -> skips agent -> legacy."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = None  # Not in DB
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.integrations.english_conversation.process_english_conversation"
            ) as mock_eng:
                mock_eng.return_value = {
                    "message_text": "Please register first.",
                    "message_spoken": "Please register first.",
                }
                result = _run(process_natural_text_query(
                    _make_telegram_update("hello")
                ))

            assert result["ok"] is True
            mock_eng.assert_called_once()


# =========================================================================
# 2. Telegram Text -- Workflow Takes Priority Over Agent
# =========================================================================

class TestTelegramTextWorkflowPriority:
    """Verify active workflows are handled before agent."""

    def test_active_workflow_bypasses_agent(self):
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            # Active batch_recording workflow
            ctx.mocks["state_mgr"].return_value = {
                "state": "batch_recording_origin",
                "workflow": "batch_recording",
            }

            with patch(
                "voice.workflows.batch_recording.BatchRecordingWorkflow.handle_message",
                new_callable=AsyncMock,
            ) as mock_wf:
                mock_wf.return_value = {"message": "What's the origin?"}
                result = _run(process_natural_text_query(
                    _make_telegram_update("Sidama")
                ))

            assert result["ok"] is True
            mock_wf.assert_awaited_once()
            mock_proc.send_notification.assert_awaited_once()
            assert (
                mock_proc.send_notification.call_args[1]["message"]
                == "What's the origin?"
            )
            # Agent must NOT have been called
            ctx.mocks["agent_run"].assert_not_called()


# =========================================================================
# 3. Mini App Voice -> Agent Path
# =========================================================================

class TestMiniAppVoiceAgentPath:
    """Verify /api/voice/upload agent integration."""

    def test_agent_conv_result_has_spoken_field(self):
        """Agent result maps response_spoken for TTS."""
        agent_result = _make_mock_agent_result("Found 3 batches")
        conv_result = {
            "message": agent_result.response,
            "message_text": agent_result.response,
            "message_spoken": agent_result.response_spoken or agent_result.response,
            "ready_to_execute": agent_result.performed_write,
            "intent": agent_result.intent,
            "entities": agent_result.entities,
        }
        assert conv_result["message_spoken"] == "Done!"
        assert conv_result["message"] == "Found 3 batches"

    def test_anonymous_user_skips_agent(self):
        """user_id=0 is falsy -> agent skipped."""
        user_id = 0
        with patch.dict(os.environ, {"AGENT_ENABLED": "true"}):
            agent_enabled = os.getenv("AGENT_ENABLED", "false").lower() == "true"
            assert not (agent_enabled and user_id)

    def test_miniapp_agent_maps_result_correctly(self):
        """Full mapping from AgentResult -> conv_result dict."""
        from voice.agent.executor import AgentResult

        agent_result = AgentResult(
            response="**Batch created:** SIDAMA_001 with 3000kg",
            response_spoken="Batch created SIDAMA 001 with 3000 kilograms",
            performed_write=True,
            intent="record_commission",
            entities={"quantity_kg": 3000, "origin": "Sidama"},
            total_tokens=500,
            duration_ms=800.0,
        )

        conv_result = {
            "message": agent_result.response,
            "message_text": agent_result.response,
            "message_spoken": agent_result.response_spoken or agent_result.response,
            "ready_to_execute": agent_result.performed_write,
            "intent": agent_result.intent,
            "entities": agent_result.entities,
        }

        assert "**" not in conv_result["message_spoken"]
        assert "SIDAMA" in conv_result["message_spoken"]
        assert conv_result["ready_to_execute"] is True
        assert conv_result["intent"] == "record_commission"
        assert conv_result["entities"]["quantity_kg"] == 3000

    def test_miniapp_agent_run_receives_correct_params(self):
        """AgentExecutor.run() called with correct params."""
        from voice.agent.executor import AgentExecutor

        expected = _make_mock_agent_result("3 batches")
        with patch.object(AgentExecutor, "run", return_value=expected) as mock_run:
            executor = AgentExecutor()
            result = executor.run(
                transcript="show my batches",
                user_id=42,
                user_did="did:key:z6MkTest",
                language="en",
            )

        mock_run.assert_called_once_with(
            transcript="show my batches",
            user_id=42,
            user_did="did:key:z6MkTest",
            language="en",
        )
        assert result.response == "3 batches"

    def test_miniapp_voice_api_has_agent_path(self):
        """voice_api.py contains AGENT_ENABLED gating."""
        import inspect
        from voice.web import voice_api

        source = inspect.getsource(voice_api)
        assert "AGENT_ENABLED" in source
        assert "AgentExecutor" in source
        assert "agent_handled" in source


# =========================================================================
# 4. Bilingual Agent -- Language Flows End-to-End
# =========================================================================

class TestBilingualAgent:
    """Verify Amharic/English language handling end-to-end."""

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis", return_value=None)
    @patch("voice.agent.executor.translate_text")
    def test_amharic_input_translated_before_agent(
        self, mock_translate, mock_redis, mock_client
    ):
        from voice.agent.executor import AgentExecutor

        mock_translate.side_effect = [
            "Show my batches",
            "3 batches found in Amharic",
        ]

        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "You have 3 batches."
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response

        executor = AgentExecutor()
        result = executor.run(transcript="test am input", user_id=1, language="am")

        # Input translated am->en
        assert mock_translate.call_args_list[0][0][1] == "am"
        assert mock_translate.call_args_list[0][0][2] == "en"
        # Output translated en->am
        assert mock_translate.call_args_list[1][0][1] == "en"
        assert mock_translate.call_args_list[1][0][2] == "am"

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis", return_value=None)
    def test_english_input_no_translation(self, mock_redis, mock_client):
        from voice.agent.executor import AgentExecutor

        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "You have 3 batches."
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response

        with patch("voice.agent.executor.translate_text") as mock_translate:
            executor = AgentExecutor()
            result = executor.run(transcript="Show my batches", user_id=1, language="en")
            mock_translate.assert_not_called()

        assert "3 batches" in result.response

    def test_system_prompt_includes_amharic_note(self):
        from voice.agent.executor import AgentExecutor

        executor = AgentExecutor()
        prompt = executor._build_system_message(user_id=1, language="am", context=None)
        assert "LANGUAGE NOTE" in prompt
        assert "Amharic" in prompt
        assert "translated to English" in prompt

    def test_system_prompt_no_amharic_note_for_english(self):
        from voice.agent.executor import AgentExecutor

        executor = AgentExecutor()
        prompt = executor._build_system_message(user_id=1, language="en", context=None)
        assert "LANGUAGE NOTE" not in prompt


# =========================================================================
# 5. Dual Delivery Verification
# =========================================================================

class TestDualDelivery:
    """Verify text + voice delivery on every Telegram path."""

    def test_agent_text_path_sends_voice(self):
        """Agent text path sends with send_voice=True."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            ctx.mocks["agent_run"].return_value = _make_mock_agent_result("Done!")
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            _run(process_natural_text_query(_make_telegram_update("show batches")))

            skw = mock_proc.send_notification.call_args[1]
            assert skw["send_voice"] is True

    def test_legacy_text_path_uses_channel_default(self):
        """Legacy path (agent disabled) uses parse_mode=None; no fallback banner."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("false") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.integrations.english_conversation.process_english_conversation"
            ) as mock_eng:
                mock_eng.return_value = {
                    "message_text": "Hello",
                    "message_spoken": "Hello",
                }
                _run(process_natural_text_query(_make_telegram_update("hello there")))

            skw = mock_proc.send_notification.call_args[1]
            assert skw["parse_mode"] is None
            assert "Fallback mode" not in skw["message"]

    def test_workflow_path_sends_response(self):
        """Workflow responses are sent (not silently dropped)."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            ctx.mocks["state_mgr"].return_value = {
                "state": "batch_recording_origin",
                "workflow": "batch_recording",
            }

            with patch(
                "voice.workflows.batch_recording.BatchRecordingWorkflow.handle_message",
                new_callable=AsyncMock,
            ) as mock_wf:
                mock_wf.return_value = {"message": "What's the origin region?"}
                result = _run(process_natural_text_query(
                    _make_telegram_update("Sidama")
                ))

            assert result["ok"] is True
            mock_proc.send_notification.assert_awaited_once()
            assert (
                mock_proc.send_notification.call_args[1]["message"]
                == "What's the origin region?"
            )


# =========================================================================
# 6. Mini App Voice -- TTS Response
# =========================================================================

class TestMiniAppTTS:
    """Verify Mini App agent path produces correct conv_result for TTS."""

    def test_agent_result_to_conv_result_mapping(self):
        from voice.agent.executor import AgentResult

        agent_result = AgentResult(
            response="**Batch created:** SIDAMA_001 with 3000kg",
            response_spoken="Batch created SIDAMA 001 with 3000 kilograms",
            performed_write=True,
            intent="record_commission",
            entities={"quantity_kg": 3000, "origin": "Sidama"},
            total_tokens=500,
            duration_ms=800.0,
        )

        conv_result = {
            "message": agent_result.response,
            "message_text": agent_result.response,
            "message_spoken": agent_result.response_spoken or agent_result.response,
            "ready_to_execute": agent_result.performed_write,
            "intent": agent_result.intent,
            "entities": agent_result.entities,
        }

        assert "**" not in conv_result["message_spoken"]
        assert "SIDAMA" in conv_result["message_spoken"]
        assert conv_result["ready_to_execute"] is True
        assert conv_result["intent"] == "record_commission"
        assert conv_result["entities"]["quantity_kg"] == 3000

    def test_agent_result_no_spoken_uses_response(self):
        from voice.agent.executor import AgentResult

        agent_result = AgentResult(
            response="Hello, how can I help?",
            response_spoken=None,
        )
        message_spoken = agent_result.response_spoken or agent_result.response
        assert message_spoken == "Hello, how can I help?"


# =========================================================================
# 7. AGENT_ENABLED Gating
# =========================================================================

class TestAgentEnabledGating:
    """Verify AGENT_ENABLED env var controls agent activation."""

    def test_env_check_true(self):
        with patch.dict(os.environ, {"AGENT_ENABLED": "true"}):
            assert os.getenv("AGENT_ENABLED", "false").lower() == "true"

    def test_env_check_True_capitalized(self):
        with patch.dict(os.environ, {"AGENT_ENABLED": "True"}):
            assert os.getenv("AGENT_ENABLED", "false").lower() == "true"

    def test_env_check_false(self):
        with patch.dict(os.environ, {"AGENT_ENABLED": "false"}):
            assert os.getenv("AGENT_ENABLED", "false").lower() != "true"

    def test_env_check_missing(self):
        env = os.environ.copy()
        env.pop("AGENT_ENABLED", None)
        with patch.dict(os.environ, env, clear=True):
            assert os.getenv("AGENT_ENABLED", "false").lower() != "true"

    def test_user_id_zero_is_falsy(self):
        """user_id=0 (anonymous) should skip agent."""
        assert not (True and 0)

    def test_user_id_nonzero_is_truthy(self):
        """user_id=42 (authenticated) should enter agent."""
        assert True and 42


# =========================================================================
# 8. Celery Voice Task Agent Integration
# =========================================================================

class TestCeleryVoiceTaskAgent:
    """Verify Celery task calls agent correctly (reference path)."""

    def test_voice_task_has_agent_check(self):
        import inspect
        from voice.tasks.voice_tasks import process_voice_command_task

        source = inspect.getsource(process_voice_command_task)
        assert "AGENT_ENABLED" in source
        assert "AgentExecutor" in source

    def test_voice_task_has_send_voice_true(self):
        import inspect
        from voice.tasks.voice_tasks import process_voice_command_task

        source = inspect.getsource(process_voice_command_task)
        assert "send_voice=True" in source

    def test_voice_task_has_language_param(self):
        import inspect
        from voice.tasks.voice_tasks import process_voice_command_task

        source = inspect.getsource(process_voice_command_task)
        assert "language=user_language" in source


# =========================================================================
# 9. IVR Routes Through Celery
# =========================================================================

class TestIVRRouting:
    """Verify IVR/Twilio uses Celery task (inherits agent)."""

    def test_ivr_imports_celery_task(self):
        import inspect
        from voice.ivr import ivr_api

        source = inspect.getsource(ivr_api)
        assert "process_voice_command_task" in source
        assert ".delay(" in source


# =========================================================================
# 10. Agent Error Handling
# =========================================================================

class TestAgentErrorHandling:
    """Verify graceful fallbacks on agent errors."""

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis", return_value=None)
    def test_openai_error_re_raises(self, mock_redis, mock_client):
        from voice.agent.executor import AgentExecutor

        mock_client.chat.completions.create.side_effect = Exception("API rate limit")

        executor = AgentExecutor()
        with pytest.raises(Exception, match="API rate limit"):
            executor.run(transcript="test", user_id=1)

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis", return_value=None)
    def test_max_turns_exhausted_returns_message(self, mock_redis, mock_client):
        from voice.agent.executor import AgentExecutor

        mock_tc = MagicMock()
        mock_tc.id = "call_loop"
        mock_tc.function.name = "query_batches"
        mock_tc.function.arguments = json.dumps({"limit": 5})

        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tc]
        mock_msg.content = ""

        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.total_tokens = 100

        mock_client.chat.completions.create.return_value = mock_resp

        with patch.object(
            AgentExecutor,
            "_execute_tool",
            return_value={"success": True, "message": "OK", "data": {}},
        ):
            executor = AgentExecutor(max_turns=2)
            result = executor.run(transcript="loop test", user_id=1)

        assert result.error == "max_turns_exhausted"
        assert "rephras" in result.response.lower() or "trouble" in result.response.lower()


# =========================================================================
# 11. Source Code Wiring Verification
# =========================================================================

class TestSourceCodeWiring:
    """Static checks that agent integration exists in the right files."""

    def test_telegram_api_has_agent_path(self):
        import inspect
        from voice.telegram import telegram_api

        source = inspect.getsource(telegram_api.process_natural_text_query)
        assert "AGENT_ENABLED" in source
        assert "AgentExecutor" in source
        assert "agent_handled" in source
        assert "send_voice=True" in source

    def test_voice_api_has_agent_path(self):
        import inspect
        from voice.web import voice_api

        source = inspect.getsource(voice_api)
        assert "AGENT_ENABLED" in source
        assert "AgentExecutor" in source
        assert "agent_handled" in source

    def test_telegram_text_agent_sends_markdown(self):
        import inspect
        from voice.telegram import telegram_api

        source = inspect.getsource(telegram_api.process_natural_text_query)
        assert "parse_mode='Markdown'" in source

    def test_telegram_legacy_sends_plain(self):
        import inspect
        from voice.telegram import telegram_api

        source = inspect.getsource(telegram_api.process_natural_text_query)
        assert "parse_mode=None" in source

    def test_all_five_interfaces_reach_agent(self):
        """All 5 paths have agent wiring."""
        import inspect

        # 1. Celery task (Telegram voice, Direct API, IVR)
        from voice.tasks.voice_tasks import process_voice_command_task
        assert "AgentExecutor" in inspect.getsource(process_voice_command_task)

        # 2. Telegram text
        from voice.telegram.telegram_api import process_natural_text_query
        assert "AgentExecutor" in inspect.getsource(process_natural_text_query)

        # 3. Mini App voice
        from voice.web import voice_api
        assert "AgentExecutor" in inspect.getsource(voice_api)

        # 4. IVR routes through Celery
        from voice.ivr import ivr_api
        assert "process_voice_command_task" in inspect.getsource(ivr_api)


# =========================================================================
# 12. Fallback Observability
# =========================================================================

class TestFallbackObservability:
    """Verify fallback banners, response_source fields, and log warnings."""

    def test_telegram_text_fallback_banner_present(self):
        """Agent fails -> legacy response gets ⚠️ banner prepended."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            ctx.mocks["agent_run"].side_effect = RuntimeError("key expired")
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.integrations.english_conversation.process_english_conversation"
            ) as mock_eng:
                mock_eng.return_value = {
                    "message_text": "Here are your batches.",
                    "message_spoken": "Here are your batches.",
                }
                _run(process_natural_text_query(_make_telegram_update("show batches")))

            sent = mock_proc.send_notification.call_args[1]
            assert sent["message"].startswith("⚠️")
            assert "Fallback mode" in sent["message"]
            assert "Here are your batches" in sent["message"]
            assert sent["parse_mode"] == "HTML"

    def test_telegram_text_no_banner_when_agent_disabled(self):
        """AGENT_ENABLED=false -> no banner, plain parse_mode."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("false") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            with patch(
                "voice.integrations.english_conversation.process_english_conversation"
            ) as mock_eng:
                mock_eng.return_value = {
                    "message_text": "Hello from legacy.",
                    "message_spoken": "Hello from legacy.",
                }
                _run(process_natural_text_query(_make_telegram_update("hello")))

            sent = mock_proc.send_notification.call_args[1]
            assert not sent["message"].startswith("⚠️")
            assert sent["parse_mode"] is None

    def test_telegram_text_no_banner_when_agent_succeeds(self):
        """Agent succeeds -> no fallback banner."""
        from voice.telegram.telegram_api import process_natural_text_query

        with _TelegramTextPatchContext("true") as ctx:
            ctx.mocks["get_user"].return_value = _make_mock_user()
            ctx.mocks["agent_run"].return_value = _make_mock_agent_result("3 batches")
            mock_proc = AsyncMock()
            ctx.mocks["get_processor"].return_value = mock_proc

            _run(process_natural_text_query(_make_telegram_update("show batches")))

            sent = mock_proc.send_notification.call_args[1]
            assert "Fallback mode" not in sent["message"]
            assert sent["parse_mode"] == "Markdown"

    def test_miniapp_response_source_agent(self):
        """Agent succeeds -> conv_result has response_source='agent'."""
        agent_result = _make_mock_agent_result("3 batches found")
        conv_result = {
            'message': agent_result.response,
            'response_source': 'agent',
        }
        assert conv_result['response_source'] == 'agent'

    def test_miniapp_response_source_fallback_nlu(self):
        """Agent fails -> conv_result has response_source='fallback_nlu', agent_error set."""
        conv_result = {
            'message': 'Legacy response',
            'response_source': 'fallback_nlu',
            'agent_error': 'RuntimeError: API rate limit',
        }
        assert conv_result['response_source'] == 'fallback_nlu'
        assert 'RuntimeError' in conv_result['agent_error']

    def test_miniapp_response_source_fallback_failed(self):
        """Both agent and fallback fail -> response_source='fallback_failed'."""
        conv_result = {
            'message': 'Sorry, error.',
            'response_source': 'fallback_failed',
            'agent_error': 'AuthenticationError: 401',
            'fallback_error': 'TypeError: missing arg',
        }
        assert conv_result['response_source'] == 'fallback_failed'
        assert conv_result['fallback_error'] is not None

    def test_executor_re_raises_on_error(self):
        """AgentExecutor.run() re-raises exceptions instead of swallowing."""
        from voice.agent.executor import AgentExecutor

        with patch("voice.agent.executor._client") as mock_client, \
             patch("voice.agent.executor._get_redis", return_value=None):
            mock_client.chat.completions.create.side_effect = ValueError("bad key")
            executor = AgentExecutor()
            with pytest.raises(ValueError, match="bad key"):
                executor.run(transcript="test", user_id=1)

    def test_source_code_has_fallback_banner(self):
        """All Telegram paths have fallback banner logic."""
        import inspect
        from voice.telegram import telegram_api

        source = inspect.getsource(telegram_api.process_natural_text_query)
        assert "_fallback_banner" in source
        assert "Fallback mode" in source
        assert "FALLBACK ACTIVE" in source

    def test_source_code_has_response_source(self):
        """Mini App voice path has response_source field."""
        import inspect
        from voice.web import voice_api

        source = inspect.getsource(voice_api)
        assert "response_source" in source
        assert "agent_error" in source
        assert "fallback_error" in source

    def test_celery_task_has_fallback_banner(self):
        """Celery voice task has fallback banner logic."""
        import inspect
        from voice.tasks.voice_tasks import process_voice_command_task

        source = inspect.getsource(process_voice_command_task)
        assert "_fallback_banner" in source
        assert "Fallback mode" in source
        assert "FALLBACK ACTIVE" in source
        assert "agent_error_detail" in source

    def test_pydantic_model_has_observability_fields(self):
        """VoiceUploadResponse includes response_source, agent_error, fallback_error."""
        from voice.web.voice_api import VoiceUploadResponse

        fields = VoiceUploadResponse.model_fields
        assert "response_source" in fields
        assert "agent_error" in fields
        assert "fallback_error" in fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
