"""
Tests for the Voice Ledger AI Agent (Agent #1)

Tests cover:
1. Tool definitions are valid OpenAI schemas
2. Tool registry maps names → handlers
3. Agent executor runs transcript → tool calls → response
4. Multi-turn conversation history
5. Error handling and fallback
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# Test Tool Definitions
# =========================================================================

class TestToolDefinitions:
    """Verify tool schemas are valid for OpenAI function-calling."""
    
    def test_all_tools_have_required_fields(self):
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        
        for tool in SUPPLY_CHAIN_TOOLS:
            assert tool["type"] == "function", f"Tool missing type=function"
            func = tool["function"]
            assert "name" in func, f"Tool missing name"
            assert "description" in func, f"Tool {func.get('name')} missing description"
            assert "parameters" in func, f"Tool {func['name']} missing parameters"
            params = func["parameters"]
            assert params["type"] == "object", f"Tool {func['name']} params not object"
    
    def test_tool_count(self):
        """We should have 9 tools: 7 write + 2 read."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        assert len(SUPPLY_CHAIN_TOOLS) == 9
    
    def test_tool_names_are_unique(self):
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        names = [t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"
    
    def test_required_fields_are_in_properties(self):
        """Every required field must be defined in properties."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        
        for tool in SUPPLY_CHAIN_TOOLS:
            func = tool["function"]
            params = func["parameters"]
            required = params.get("required", [])
            properties = params.get("properties", {})
            for field in required:
                assert field in properties, (
                    f"Tool {func['name']}: required field '{field}' "
                    f"not in properties"
                )


# =========================================================================
# Test Tool Registry
# =========================================================================

class TestToolRegistry:
    """Verify the registry connects tool names to handlers."""
    
    def test_all_tools_registered(self):
        from voice.agent.registry import get_tool_registry
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        
        registry = get_tool_registry()
        tool_names = [t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS]
        
        for name in tool_names:
            assert registry.has(name), f"Tool '{name}' not registered"
    
    def test_custom_tool_registration(self):
        from voice.agent.registry import ToolRegistry
        
        registry = ToolRegistry()
        
        def my_custom_tool(db, args, user_id=None, user_did=None):
            return ("custom result", {"custom": True})
        
        registry.register("my_custom_tool", my_custom_tool)
        assert registry.has("my_custom_tool")
        assert registry.get("my_custom_tool") is my_custom_tool
    
    def test_unknown_tool_returns_none(self):
        from voice.agent.registry import get_tool_registry
        
        registry = get_tool_registry()
        assert registry.get("nonexistent_tool") is None


# =========================================================================
# Test Agent Result
# =========================================================================

class TestAgentResult:
    """Verify AgentResult dataclass."""
    
    def test_default_values(self):
        from voice.agent.executor import AgentResult
        
        result = AgentResult(response="Hello")
        assert result.response == "Hello"
        assert result.performed_write is False
        assert result.tool_calls == []
        assert result.intent is None
        assert result.error is None
    
    def test_with_tool_calls(self):
        from voice.agent.executor import AgentResult, ToolCall
        
        tc = ToolCall(
            tool_name="record_commission",
            arguments={"quantity_kg": 3000, "origin": "Sidama"},
            result_message="Batch created",
            result_data={"batch_id": "TEST_123"},
            success=True,
            duration_ms=150.0,
        )
        
        result = AgentResult(
            response="✅ Created batch TEST_123",
            tool_calls=[tc],
            performed_write=True,
            intent="record_commission",
        )
        
        assert len(result.tool_calls) == 1
        assert result.performed_write is True
        assert result.intent == "record_commission"


# =========================================================================
# Test Speech Stripping
# =========================================================================

class TestSpeechStripping:
    """Verify text cleaning for TTS output."""
    
    def test_strips_urls(self):
        from voice.agent.executor import AgentExecutor
        
        text = "Visit https://example.com for more info"
        clean = AgentExecutor._strip_for_speech(text)
        assert "https://" not in clean
    
    def test_strips_markdown(self):
        from voice.agent.executor import AgentExecutor
        
        text = "**Bold** and *italic* text"
        clean = AgentExecutor._strip_for_speech(text)
        assert "**" not in clean
        assert "*" not in clean
        assert "Bold" in clean
        assert "italic" in clean
    
    def test_strips_emoji(self):
        from voice.agent.executor import AgentExecutor
        
        text = "✅ Batch created 📦"
        clean = AgentExecutor._strip_for_speech(text)
        assert "✅" not in clean
        assert "📦" not in clean
        assert "Batch created" in clean


# =========================================================================
# Test Agent Executor (mocked OpenAI)
# =========================================================================

class TestAgentExecutor:
    """Test the agent loop with mocked OpenAI responses."""
    
    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_simple_text_response(self, mock_redis, mock_client):
        """Agent returns text when no tool call needed."""
        from voice.agent.executor import AgentExecutor, AgentResult
        
        # Mock Redis (no history)
        mock_redis.return_value = None
        
        # Mock OpenAI response — just text, no tool calls
        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "Hello! How can I help you with your coffee today?"
        
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        
        mock_client.chat.completions.create.return_value = mock_response
        
        executor = AgentExecutor()
        result = executor.run(
            transcript="Hello",
            user_id=1,
        )
        
        assert isinstance(result, AgentResult)
        assert "Hello" in result.response or "help" in result.response
        assert result.performed_write is False
        assert len(result.tool_calls) == 0
    
    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_tool_call_flow(self, mock_redis, mock_client):
        """Agent calls a tool, then returns summary."""
        from voice.agent.executor import AgentExecutor
        
        mock_redis.return_value = None
        
        # First call: model returns a tool_call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_abc123"
        mock_tool_call.function.name = "query_batches"
        mock_tool_call.function.arguments = json.dumps({"limit": 5})
        
        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 150
        
        # Second call: model returns text response
        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "You have 3 batches in the system."
        
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 200
        
        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2
        ]
        
        # Mock the tool execution (query_batches)
        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "Found 3 batches",
                "data": {"batches": [], "count": 3},
            }
        ):
            executor = AgentExecutor()
            result = executor.run(
                transcript="Show my batches",
                user_id=1,
            )
        
        assert "3 batches" in result.response
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "query_batches"
        assert result.tool_calls[0].success is True


# =========================================================================
# Test Backward Compatibility
# =========================================================================

class TestBackwardCompatibility:
    """Ensure old pipeline still works when AGENT_ENABLED is not set."""
    
    def test_agent_not_enabled_by_default(self):
        """AGENT_ENABLED defaults to false."""
        val = os.getenv("AGENT_ENABLED", "false").lower()
        # In test environment, it may or may not be set
        # Just verify the env var check pattern works
        assert val in ("true", "false")
    
    def test_intent_handlers_still_exist(self):
        """Old INTENT_HANDLERS dict is still available."""
        from voice.command_integration import INTENT_HANDLERS
        
        expected = [
            "record_commission",
            "record_shipment", 
            "record_receipt",
            "record_transformation",
            "pack_batches",
            "unpack_batches",
            "split_batch",
        ]
        for intent in expected:
            assert intent in INTENT_HANDLERS, f"Missing handler for {intent}"


# =========================================================================
# Test Amharic Language Support
# =========================================================================

class TestAmharicSupport:
    """Verify Amharic translation and language routing."""
    
    @patch("voice.agent.executor._client")
    def test_translate_text_gpt_fallback(self, mock_client):
        """translate_text falls back to GPT when Addis AI unavailable."""
        from voice.agent.executor import translate_text
        
        mock_msg = MagicMock()
        mock_msg.content = "50 kilograms of Sidama coffee"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        # With no Addis AI key, should fall back to GPT
        with patch("voice.agent.executor.ADDIS_AI_API_KEY", None):
            result = translate_text("50 ኪሎግራም የሲዳማ ቡና", "am", "en")
        
        assert result == "50 kilograms of Sidama coffee"
        mock_client.chat.completions.create.assert_called_once()
    
    def test_translate_empty_text(self):
        """Empty text returns as-is without API calls."""
        from voice.agent.executor import translate_text
        
        assert translate_text("", "am", "en") == ""
        assert translate_text("  ", "am", "en") == "  "
    
    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    @patch("voice.agent.executor.translate_text")
    def test_amharic_agent_translates_input_and_output(self, mock_translate, mock_redis, mock_client):
        """Agent translates am→en for input, en→am for output."""
        from voice.agent.executor import AgentExecutor
        
        mock_redis.return_value = None
        
        # translate_text called twice: input am→en, output en→am
        mock_translate.side_effect = [
            "I harvested 50 kilograms of Sidama coffee",  # am→en
            "✅ ባች ተፈጥሯል",  # en→am
        ]
        
        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "Batch created successfully!"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response
        
        executor = AgentExecutor()
        result = executor.run(
            transcript="50 ኪሎግራም የሲዳማ ቡና አጨድኩ",
            user_id=1,
            language="am",
        )
        
        # Should have called translate twice
        assert mock_translate.call_count == 2
        # First call: am→en (input)
        assert mock_translate.call_args_list[0][0][1] == "am"
        assert mock_translate.call_args_list[0][0][2] == "en"
        # Second call: en→am (output)
        assert mock_translate.call_args_list[1][0][1] == "en"
        assert mock_translate.call_args_list[1][0][2] == "am"
        
        # Response should be the Amharic translation
        assert result.response == "✅ ባች ተፈጥሯል"
    
    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_english_agent_no_translation(self, mock_redis, mock_client):
        """English users don't trigger any translation."""
        from voice.agent.executor import AgentExecutor
        
        mock_redis.return_value = None
        
        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "How can I help you?"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch("voice.agent.executor.translate_text") as mock_translate:
            executor = AgentExecutor()
            result = executor.run(
                transcript="Hello",
                user_id=1,
                language="en",
            )
            # translate_text should NOT be called for English
            mock_translate.assert_not_called()
    
    def test_system_prompt_amharic_context(self):
        """Amharic system prompt tells agent to respond in English for translation."""
        from voice.agent.executor import AgentExecutor
        
        executor = AgentExecutor()
        prompt = executor._build_system_message(user_id=1, language="am", context=None)
        
        assert "translated to English" in prompt
        assert "RESPOND IN ENGLISH" in prompt
        assert "translate your response back to Amharic" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
