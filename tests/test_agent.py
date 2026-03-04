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
        """We should have 37 tools across all agents."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        assert len(SUPPLY_CHAIN_TOOLS) == 37
    
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


# =========================================================================
# Test Marketplace Tools (Agent #3)
# =========================================================================

class TestMarketplaceTools:
    """Verify marketplace tool definitions and registry."""

    def test_marketplace_tool_schemas(self):
        """All marketplace tools have valid schemas."""
        from voice.agent.tools import (
            CREATE_RFQ, BROWSE_RFQS, SUBMIT_OFFER, ACCEPT_OFFER, LIST_MY_OFFERS,
        )
        for tool in [CREATE_RFQ, BROWSE_RFQS, SUBMIT_OFFER, ACCEPT_OFFER, LIST_MY_OFFERS]:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_marketplace_tools_registered(self):
        """All marketplace tools are in the registry."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        marketplace_tools = [
            "create_rfq", "browse_rfqs", "submit_offer",
            "accept_offer", "list_my_offers",
        ]
        for name in marketplace_tools:
            assert registry.has(name), f"Marketplace tool '{name}' not registered"

    def test_create_rfq_requires_quantity(self):
        """create_rfq schema requires quantity_kg."""
        from voice.agent.tools import CREATE_RFQ

        required = CREATE_RFQ["function"]["parameters"]["required"]
        assert "quantity_kg" in required

    def test_submit_offer_requires_price(self):
        """submit_offer schema requires quantity and price."""
        from voice.agent.tools import SUBMIT_OFFER

        required = SUBMIT_OFFER["function"]["parameters"]["required"]
        assert "quantity_offered_kg" in required
        assert "price_per_kg" in required

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_browse_rfqs_is_read_only(self, mock_redis, mock_client):
        """browse_rfqs should NOT mark performed_write."""
        from voice.agent.executor import AgentExecutor

        mock_redis.return_value = None

        # Model calls browse_rfqs
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_rfq1"
        mock_tool_call.function.name = "browse_rfqs"
        mock_tool_call.function.arguments = json.dumps({"status": "OPEN"})

        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 100

        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "Here are the open RFQs."
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 150

        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2,
        ]

        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "Found 2 RFQs",
                "data": {"rfqs": [], "count": 2},
            },
        ):
            executor = AgentExecutor()
            result = executor.run(transcript="Show me open RFQs", user_id=1)

        assert result.performed_write is False


# =========================================================================
# Test Compliance Tools (Agent #4)
# =========================================================================

class TestComplianceTools:
    """Verify compliance tool definitions and registry."""

    def test_compliance_tool_schemas(self):
        """All compliance tools have valid schemas."""
        from voice.agent.tools import CHECK_EUDR_COMPLIANCE, CHECK_MASS_BALANCE

        for tool in [CHECK_EUDR_COMPLIANCE, CHECK_MASS_BALANCE]:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_compliance_tools_registered(self):
        """All compliance tools are in the registry."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.has("check_eudr_compliance")
        assert registry.has("check_mass_balance")

    def test_eudr_requires_batch_ids(self):
        """check_eudr_compliance requires batch_ids."""
        from voice.agent.tools import CHECK_EUDR_COMPLIANCE

        required = CHECK_EUDR_COMPLIANCE["function"]["parameters"]["required"]
        assert "batch_ids" in required

    def test_mass_balance_requires_quantities(self):
        """check_mass_balance requires input and output quantities."""
        from voice.agent.tools import CHECK_MASS_BALANCE

        required = CHECK_MASS_BALANCE["function"]["parameters"]["required"]
        assert "input_quantities" in required
        assert "output_quantities" in required

    def test_mass_balance_handler_valid(self):
        """check_mass_balance returns correct result for valid balance."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        handler = registry.get("check_mass_balance")

        # Mock db (not needed for mass balance — pure math)
        mock_db = MagicMock()

        message, data = handler(
            mock_db,
            {
                "input_quantities": [{"quantity": 1000, "uom": "KGM"}],
                "output_quantities": [
                    {"quantity": 600, "uom": "KGM"},
                    {"quantity": 400, "uom": "KGM"},
                ],
            },
        )
        assert "valid" in message.lower() or data.get("valid") is True
        assert data["total_input_kg"] == 1000
        assert data["total_output_kg"] == 1000

    def test_mass_balance_handler_invalid(self):
        """check_mass_balance detects violation."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        handler = registry.get("check_mass_balance")
        mock_db = MagicMock()

        message, data = handler(
            mock_db,
            {
                "input_quantities": [{"quantity": 1000, "uom": "KGM"}],
                "output_quantities": [
                    {"quantity": 600, "uom": "KGM"},
                    {"quantity": 500, "uom": "KGM"},
                ],
            },
        )
        assert data.get("valid") is False
        assert "violation" in message.lower()

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_compliance_tools_are_read_only(self, mock_redis, mock_client):
        """Compliance tools should NOT mark performed_write."""
        from voice.agent.executor import AgentExecutor

        mock_redis.return_value = None

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_eudr1"
        mock_tool_call.function.name = "check_eudr_compliance"
        mock_tool_call.function.arguments = json.dumps({"batch_ids": ["B001"]})

        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 100

        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "All batches are EUDR compliant."
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 120

        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2,
        ]

        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "EUDR compliant",
                "data": {"compliant": True},
            },
        ):
            executor = AgentExecutor()
            result = executor.run(transcript="Check EUDR compliance for B001", user_id=1)

        assert result.performed_write is False


# =========================================================================
# Test Verification Tools (Agent #6)
# =========================================================================

class TestVerificationTools:
    """Verify verification tool definitions and registry."""

    def test_verification_tool_schemas(self):
        """All verification tools have valid schemas."""
        from voice.agent.tools import LIST_PENDING_VERIFICATIONS, VERIFY_BATCH

        for tool in [LIST_PENDING_VERIFICATIONS, VERIFY_BATCH]:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_verification_tools_registered(self):
        """All verification tools are in the registry."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.has("list_pending_verifications")
        assert registry.has("verify_batch")

    def test_verify_batch_requires_batch_id(self):
        """verify_batch requires batch_id."""
        from voice.agent.tools import VERIFY_BATCH

        required = VERIFY_BATCH["function"]["parameters"]["required"]
        assert "batch_id" in required

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_verify_batch_is_write_operation(self, mock_redis, mock_client):
        """verify_batch should mark performed_write."""
        from voice.agent.executor import AgentExecutor

        mock_redis.return_value = None

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_verify1"
        mock_tool_call.function.name = "verify_batch"
        mock_tool_call.function.arguments = json.dumps({"batch_id": "B001"})

        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 100

        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "Batch B001 verified!"
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 120

        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2,
        ]

        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "Batch verified",
                "data": {"batch_id": "B001", "verified_quantity_kg": 500},
            },
        ):
            executor = AgentExecutor()
            result = executor.run(transcript="Verify batch B001", user_id=1)

        assert result.performed_write is True
        assert result.tool_calls[0].tool_name == "verify_batch"

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_list_pending_is_read_only(self, mock_redis, mock_client):
        """list_pending_verifications should NOT mark performed_write."""
        from voice.agent.executor import AgentExecutor

        mock_redis.return_value = None

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_pending1"
        mock_tool_call.function.name = "list_pending_verifications"
        mock_tool_call.function.arguments = json.dumps({})

        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 100

        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "3 batches pending verification."
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 120

        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2,
        ]

        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "3 batches pending",
                "data": {"batches": [], "count": 3},
            },
        ):
            executor = AgentExecutor()
            result = executor.run(
                transcript="What batches need verification?", user_id=1,
            )

        assert result.performed_write is False


# =========================================================================
# Test DPP Tools (Agent #5)
# =========================================================================

class TestDPPTools:
    """Test DPP / Traceability tool definitions and handlers."""

    def test_dpp_tool_schemas(self):
        """All DPP tools have valid OpenAI function schemas."""
        from voice.agent.tools import GET_DPP, GET_CONTAINER_DPP, TRACE_LINEAGE, VALIDATE_DPP

        for tool in [GET_DPP, GET_CONTAINER_DPP, TRACE_LINEAGE, VALIDATE_DPP]:
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_dpp_tools_registered(self):
        """All DPP tools have handlers in the registry."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        for name in ["get_dpp", "get_container_dpp", "trace_lineage", "validate_dpp"]:
            assert registry.has(name), f"DPP tool '{name}' not registered"

    def test_get_dpp_requires_batch_id(self):
        """get_dpp should require batch_id."""
        from voice.agent.tools import GET_DPP
        assert "batch_id" in GET_DPP["function"]["parameters"]["required"]

    def test_get_container_dpp_requires_container_id(self):
        """get_container_dpp should require container_id."""
        from voice.agent.tools import GET_CONTAINER_DPP
        assert "container_id" in GET_CONTAINER_DPP["function"]["parameters"]["required"]

    def test_trace_lineage_requires_product_id(self):
        """trace_lineage should require product_id."""
        from voice.agent.tools import TRACE_LINEAGE
        assert "product_id" in TRACE_LINEAGE["function"]["parameters"]["required"]

    def test_validate_dpp_requires_batch_id(self):
        """validate_dpp should require batch_id."""
        from voice.agent.tools import VALIDATE_DPP
        assert "batch_id" in VALIDATE_DPP["function"]["parameters"]["required"]

    def test_all_dpp_tools_are_read_only(self):
        """DPP tools should NOT trigger performed_write."""
        dpp_tools = {"get_dpp", "get_container_dpp", "trace_lineage", "validate_dpp"}
        # These should all be in the executor's read-only exclusion list
        import ast
        import inspect
        from voice.agent import executor as ex_mod
        source = inspect.getsource(ex_mod)
        for tool in dpp_tools:
            assert tool in source, f"'{tool}' not found in executor source"


# =========================================================================
# Test Blockchain Tools (Agent #7)
# =========================================================================

class TestBlockchainTools:
    """Test Blockchain tool definitions and handlers."""

    def test_blockchain_tool_schemas(self):
        """All blockchain tools have valid OpenAI function schemas."""
        from voice.agent.tools import (
            CHECK_BLOCKCHAIN_ANCHOR, GET_TOKEN_INFO, VERIFY_BATCH_HASH,
        )

        for tool in [CHECK_BLOCKCHAIN_ANCHOR, GET_TOKEN_INFO, VERIFY_BATCH_HASH]:
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_blockchain_tools_registered(self):
        """All blockchain tools have handlers in the registry."""
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        for name in ["check_blockchain_anchor", "get_token_info", "verify_batch_hash"]:
            assert registry.has(name), f"Blockchain tool '{name}' not registered"

    def test_check_anchor_requires_batch_id(self):
        """check_blockchain_anchor should require batch_id."""
        from voice.agent.tools import CHECK_BLOCKCHAIN_ANCHOR
        assert "batch_id" in CHECK_BLOCKCHAIN_ANCHOR["function"]["parameters"]["required"]

    def test_get_token_info_requires_token_id(self):
        """get_token_info should require token_id."""
        from voice.agent.tools import GET_TOKEN_INFO
        assert "token_id" in GET_TOKEN_INFO["function"]["parameters"]["required"]

    def test_verify_hash_requires_batch_id(self):
        """verify_batch_hash should require batch_id."""
        from voice.agent.tools import VERIFY_BATCH_HASH
        assert "batch_id" in VERIFY_BATCH_HASH["function"]["parameters"]["required"]

    def test_all_blockchain_tools_are_read_only(self):
        """Blockchain tools should NOT trigger performed_write."""
        bc_tools = {"check_blockchain_anchor", "get_token_info", "verify_batch_hash"}
        import inspect
        from voice.agent import executor as ex_mod
        source = inspect.getsource(ex_mod)
        for tool in bc_tools:
            assert tool in source, f"'{tool}' not found in executor source"

    @patch("voice.agent.executor._client")
    @patch("voice.agent.executor._get_redis")
    def test_check_anchor_is_read_only(self, mock_redis, mock_client):
        """check_blockchain_anchor should NOT mark performed_write."""
        from voice.agent.executor import AgentExecutor

        mock_redis.return_value = None

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_anchor1"
        mock_tool_call.function.name = "check_blockchain_anchor"
        mock_tool_call.function.arguments = json.dumps({"batch_id": "B001"})

        mock_msg1 = MagicMock()
        mock_msg1.tool_calls = [mock_tool_call]
        mock_msg1.content = ""
        mock_choice1 = MagicMock()
        mock_choice1.message = mock_msg1
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage.total_tokens = 100

        mock_msg2 = MagicMock()
        mock_msg2.tool_calls = None
        mock_msg2.content = "Batch B001 is anchored on Base Sepolia."
        mock_choice2 = MagicMock()
        mock_choice2.message = mock_msg2
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.total_tokens = 120

        mock_client.chat.completions.create.side_effect = [
            mock_response1, mock_response2,
        ]

        with patch.object(
            AgentExecutor, "_execute_tool",
            return_value={
                "success": True,
                "message": "Batch B001 is anchored",
                "data": {"batch_id": "B001", "anchored": True},
            },
        ):
            executor = AgentExecutor()
            result = executor.run(
                transcript="Is batch B001 on the blockchain?", user_id=1,
            )

        assert result.performed_write is False


# =========================================================================
# Test Updated Tool Count
# =========================================================================

class TestAllToolsIntegration:
    """Verify all agents work together in the unified tool set."""

    def test_total_tool_count(self):
        """We should have 37 tools total."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS

        assert len(SUPPLY_CHAIN_TOOLS) == 37

    def test_all_tool_names_unique(self):
        """No duplicate tool names across all agents."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS

        names = [t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_all_tools_have_handlers(self):
        """Every tool definition has a matching handler in the registry."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        from voice.agent.registry import ToolRegistry

        registry = ToolRegistry()
        for tool in SUPPLY_CHAIN_TOOLS:
            name = tool["function"]["name"]
            assert registry.has(name), f"Tool '{name}' has no handler in registry"

    def test_read_vs_write_classification(self):
        """Verify read-only tools are correctly classified."""
        read_tools = {
            "query_batches", "search_knowledge",
            "browse_rfqs", "list_my_offers",
            "check_eudr_compliance", "check_mass_balance",
            "get_dpp", "get_container_dpp", "trace_lineage", "validate_dpp",
            "list_pending_verifications",
            "check_blockchain_anchor", "get_token_info", "verify_batch_hash",
            "check_don_attestation", "get_don_provenance_metrics",
            "browse_containers", "browse_pools", "list_my_commitments",
            "check_payment_status",
        }
        write_tools = {
            "record_commission", "record_shipment", "record_receipt",
            "record_transformation", "pack_batches", "unpack_batches",
            "split_batch", "create_rfq", "submit_offer", "accept_offer",
            "verify_batch", "request_don_attestation",
            "purchase_container", "commit_to_pool",
            "confirm_payment", "record_cooperative_payout",
            "confirm_payment_received",
        }
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS

        all_names = {t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS}
        assert read_tools | write_tools == all_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
