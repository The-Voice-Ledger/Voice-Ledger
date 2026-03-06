"""
Tests for DeFi Financing Pool Agent Tools

Verifies:
  1. Tool definitions are well-formed and present in SUPPLY_CHAIN_TOOLS
  2. Tool handlers are registered in the ToolRegistry
  3. Handler logic (check pool, request advance, check trade)
"""

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────
# 1. Tool schema tests
# ─────────────────────────────────────────────────────────────

class TestDeFiToolSchemas:
    """Verify the 3 DeFi tool schemas are present and well-formed."""

    def test_supply_chain_tools_has_defi_tools(self):
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        tool_names = [t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS]
        assert "check_financing_pool" in tool_names
        assert "request_financing_advance" in tool_names
        assert "check_trade_financing" in tool_names

    def test_total_tool_count(self):
        """Should now have 40 tools (37 previous + 3 DeFi)."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        assert len(SUPPLY_CHAIN_TOOLS) == 40

    def test_check_financing_pool_schema(self):
        from voice.agent.tools import CHECK_FINANCING_POOL
        func = CHECK_FINANCING_POOL["function"]
        assert func["name"] == "check_financing_pool"
        assert func["parameters"]["properties"] == {}

    def test_request_financing_advance_schema(self):
        from voice.agent.tools import REQUEST_FINANCING_ADVANCE
        func = REQUEST_FINANCING_ADVANCE["function"]
        assert func["name"] == "request_financing_advance"
        props = func["parameters"]["properties"]
        assert "acceptance_number" in props
        assert "token_id" in props
        assert "buyer_address" in props

    def test_check_trade_financing_schema(self):
        from voice.agent.tools import CHECK_TRADE_FINANCING
        func = CHECK_TRADE_FINANCING["function"]
        assert func["name"] == "check_trade_financing"
        props = func["parameters"]["properties"]
        assert "trade_id" in props
        assert "acceptance_number" in props


# ─────────────────────────────────────────────────────────────
# 2. Registry tests
# ─────────────────────────────────────────────────────────────

class TestDeFiRegistryHandlers:
    """Verify DeFi tool handlers are registered and callable."""

    def _fresh_registry(self):
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry
        return get_tool_registry()

    def test_registry_has_defi_tools(self):
        registry = self._fresh_registry()
        assert registry.has("check_financing_pool")
        assert registry.has("request_financing_advance")
        assert registry.has("check_trade_financing")

    def test_total_registered_tools(self):
        """Should have 40 tools registered."""
        registry = self._fresh_registry()
        assert len(registry.tool_names) == 40


# ─────────────────────────────────────────────────────────────
# 3. Handler logic tests
# ─────────────────────────────────────────────────────────────

class TestCheckFinancingPool:
    """Test check_financing_pool handler."""

    def _fresh_registry(self):
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry
        return get_tool_registry()

    @patch("blockchain.financing_manager.get_financing_manager")
    def test_returns_pool_stats(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_mgr.pool_stats.return_value = {
            "total_assets_usdc": 100_000.0,
            "total_advanced_usdc": 30_000.0,
            "available_for_advance_usdc": 70_000.0,
            "utilisation_pct": 30.0,
            "cumulative_fees_usdc": 1_200.0,
            "total_shares": 100_000.0,
            "share_price_usdc": 1.012,
        }
        mock_get_mgr.return_value = mock_mgr

        registry = self._fresh_registry()
        handler = registry.get("check_financing_pool")
        msg, data = handler(MagicMock(), {}, user_id=1)

        assert "100,000" in msg
        assert "70,000" in msg
        assert data["utilisation_pct"] == 30.0

    @patch("blockchain.financing_manager.get_financing_manager")
    def test_handles_connection_error(self, mock_get_mgr):
        """Should return error message when blockchain is unreachable."""
        mock_get_mgr.side_effect = Exception("RPC connection refused")

        registry = self._fresh_registry()
        handler = registry.get("check_financing_pool")
        msg, data = handler(MagicMock(), {}, user_id=1)
        assert "error" in data


class TestRequestFinancingAdvance:
    """Test request_financing_advance handler."""

    def _fresh_registry(self):
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry
        return get_tool_registry()

    def test_rejects_non_cooperative(self):
        """Only cooperatives can request advances."""
        registry = self._fresh_registry()
        handler = registry.get("request_financing_advance")

        db = MagicMock()
        user = MagicMock()
        user.role = "farmer"
        db.query.return_value.filter_by.return_value.first.return_value = user

        msg, data = handler(db, {"acceptance_number": "ACC-000001"}, user_id=1)
        assert "cooperative" in msg.lower()
        assert data["error"] == "forbidden"

    def test_rejects_missing_id(self):
        """Should ask for acceptance_number or token_id."""
        registry = self._fresh_registry()
        handler = registry.get("request_financing_advance")

        db = MagicMock()
        user = MagicMock()
        user.role = "cooperative"
        db.query.return_value.filter_by.return_value.first.return_value = user

        msg, data = handler(db, {}, user_id=1)
        assert "missing_id" in data.get("error", "")

    def test_rejects_wrong_delivery_status(self):
        """Cannot finance a trade that hasn't shipped."""
        registry = self._fresh_registry()
        handler = registry.get("request_financing_advance")

        db = MagicMock()
        user = MagicMock()
        user.role = "cooperative"
        user.organization_id = 1

        acceptance = MagicMock()
        acceptance.acceptance_number = "ACC-000001"
        acceptance.offer_id = 1
        acceptance.delivery_status = "PENDING"

        offer = MagicMock()
        offer.cooperative_id = 1

        def query_side_effect(model):
            mock = MagicMock()
            if model.__name__ == "UserIdentity":
                mock.filter_by.return_value.first.return_value = user
            elif model.__name__ == "RFQAcceptance":
                mock.filter_by.return_value.first.return_value = acceptance
            elif model.__name__ == "RFQOffer":
                mock.filter_by.return_value.first.return_value = offer
            return mock

        db.query.side_effect = query_side_effect

        msg, data = handler(db, {"acceptance_number": "ACC-000001"}, user_id=1)
        assert "invalid_status" in data.get("error", "")
        assert "PENDING" in msg


class TestCheckTradeFinancing:
    """Test check_trade_financing handler."""

    def _fresh_registry(self):
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry
        return get_tool_registry()

    def test_rejects_missing_id(self):
        """Should ask for trade_id or acceptance_number."""
        registry = self._fresh_registry()
        handler = registry.get("check_trade_financing")
        msg, data = handler(MagicMock(), {}, user_id=1)
        assert "missing_id" in data.get("error", "")

    @patch("blockchain.financing_manager.get_financing_manager")
    def test_returns_trade_details(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_mgr.get_trade.return_value = {
            "trade_id": 1,
            "token_id": 42,
            "token_amount": 1,
            "seller": "0xabc",
            "buyer": "0xdef",
            "agreed_price_usdc": 25_000.0,
            "advance_amount_usdc": 20_000.0,
            "fee_bps": 200,
            "fee_amount_usdc": 500.0,
            "shipment_hash": "0x123",
            "farm_id": "FARMER-001",
            "created_at": 1709000000,
            "settled_at": 0,
            "deadline": 1711592000,
            "status": "Active",
        }
        mock_get_mgr.return_value = mock_mgr

        registry = self._fresh_registry()
        handler = registry.get("check_trade_financing")
        msg, data = handler(MagicMock(), {"trade_id": 1}, user_id=1)

        assert "Active" in msg
        assert "25,000" in msg
        assert "20,000" in msg
        assert data["trade_id"] == 1

    @patch("blockchain.financing_manager.get_financing_manager")
    def test_trade_not_found(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_mgr.get_trade.return_value = None
        mock_get_mgr.return_value = mock_mgr

        registry = self._fresh_registry()
        handler = registry.get("check_trade_financing")
        msg, data = handler(MagicMock(), {"trade_id": 999}, user_id=1)
        assert "not found" in msg.lower()
        assert data["error"] == "not_found"
