"""
Tests for Plan 006: Agent Tool Plugin System + Deduplication

Covers:
- READ_ONLY_TOOLS is a single module-level constant (not duplicated)
- All tools are registered in the registry
- Plugin system loads without error
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-tests-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class TestReadOnlyToolsConstant:

    def test_module_level_constant_exists(self):
        """READ_ONLY_TOOLS must be defined at module level in executor.py."""
        from voice.agent.executor import READ_ONLY_TOOLS
        assert READ_ONLY_TOOLS is not None

    def test_is_frozenset(self):
        """READ_ONLY_TOOLS must be a frozenset (immutable)."""
        from voice.agent.executor import READ_ONLY_TOOLS
        assert isinstance(READ_ONLY_TOOLS, frozenset)

    def test_not_empty(self):
        """READ_ONLY_TOOLS must contain at least 15 tools."""
        from voice.agent.executor import READ_ONLY_TOOLS
        assert len(READ_ONLY_TOOLS) >= 15

    def test_contains_expected_tools(self):
        """Key read-only tools must be in the set."""
        from voice.agent.executor import READ_ONLY_TOOLS
        for tool in ("query_batches", "search_knowledge", "browse_rfqs",
                     "get_dpp", "check_eudr_compliance", "check_payment_status"):
            assert tool in READ_ONLY_TOOLS, f"'{tool}' missing from READ_ONLY_TOOLS"

    def test_financing_tools_included(self):
        """check_financing_pool and check_trade_financing must be included (drift fix)."""
        from voice.agent.executor import READ_ONLY_TOOLS
        assert "check_financing_pool" in READ_ONLY_TOOLS
        assert "check_trade_financing" in READ_ONLY_TOOLS

    def test_no_class_level_duplicate(self):
        """The class-level READ_ONLY_TOOLS duplicate must be gone from executor.py."""
        executor_path = Path(__file__).parent.parent / 'voice' / 'agent' / 'executor.py'
        content = executor_path.read_text(encoding='utf-8')
        # Should have exactly one definition of READ_ONLY_TOOLS (the module-level one)
        import re
        definitions = re.findall(r'^READ_ONLY_TOOLS\s*[=:]', content, re.MULTILINE)
        assert len(definitions) == 1, \
            f"Expected 1 definition of READ_ONLY_TOOLS, found {len(definitions)}"

    def test_write_tracking_uses_constant(self):
        """The write-tracking check must reference READ_ONLY_TOOLS, not a hardcoded tuple."""
        executor_path = Path(__file__).parent.parent / 'voice' / 'agent' / 'executor.py'
        content = executor_path.read_text(encoding='utf-8')
        # The old inline tuple had this pattern right after 'tool_name not in ('
        import re
        old_pattern = r'tool_name not in \(\s*"query_batches"'
        assert not re.search(old_pattern, content), \
            "Old hardcoded tuple still used in write-tracking check in executor.py"
        # Should have the constant reference
        assert 'tool_name not in READ_ONLY_TOOLS' in content


class TestToolRegistry:

    def test_registry_loads(self):
        """ToolRegistry must load without errors."""
        from voice.agent.registry import ToolRegistry
        registry = ToolRegistry()
        assert registry is not None

    def test_all_tools_registered(self):
        """Registry must have at least 37 tools registered."""
        from voice.agent.registry import get_tool_registry
        registry = get_tool_registry()
        assert len(registry.tool_names) >= 37, \
            f"Expected >= 37 tools, found {len(registry.tool_names)}"

    def test_core_tools_present(self):
        """Key tools from each domain must be registered."""
        from voice.agent.registry import get_tool_registry
        registry = get_tool_registry()
        required = [
            "record_commission", "query_batches",        # supply chain
            "create_rfq", "submit_offer", "accept_offer", # marketplace
            "commit_to_pool", "browse_pools",             # pools
            "confirm_payment", "dispute_payment",         # settlement
            "check_financing_pool",                       # DeFi
            "get_dpp", "check_eudr_compliance",           # compliance
        ]
        for tool in required:
            assert registry.has(tool), f"Tool '{tool}' not registered"


class TestPluginSystem:

    def test_plugin_package_exists(self):
        """voice/agent/tool_plugins/__init__.py must exist."""
        plugin_path = Path(__file__).parent.parent / 'voice' / 'agent' / 'tool_plugins' / '__init__.py'
        assert plugin_path.exists(), "Plugin package not found"

    def test_plugin_package_importable(self):
        """Plugin package must be importable without errors."""
        try:
            from voice.agent.tool_plugins import register_all_plugins
            assert callable(register_all_plugins)
        except ImportError as e:
            pytest.fail(f"Plugin package not importable: {e}")

    def test_register_all_plugins_callable(self):
        """register_all_plugins must accept a registry without raising."""
        from voice.agent.tool_plugins import register_all_plugins
        from unittest.mock import MagicMock
        registry = MagicMock()
        # Should not raise
        register_all_plugins(registry)

    def test_registry_calls_plugins(self):
        """ToolRegistry._register_defaults must attempt to load plugins."""
        registry_path = Path(__file__).parent.parent / 'voice' / 'agent' / 'registry.py'
        content = registry_path.read_text(encoding='utf-8')
        assert 'register_all_plugins' in content, \
            "registry.py does not call register_all_plugins from plugin system"
