#!/usr/bin/env python3
"""
Tests for Chainlink CRE Client + Agent-CRE Bridge

Tests cover:
  1. CRE Client initialisation and ABI loading
  2. ProvenanceMetrics / DeforestationAttestation data classes
  3. Deforestation report ABI encoding
  4. Agent tool schemas (3 new CRE tools registered)
  5. Registry handler integration (3 CRE handlers callable)
  6. DPP DON attestation section builder
  7. Post-commission auto-attestation hook logic

Run:
    python -m pytest tests/test_cre_bridge.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# 1. Data class tests
# ─────────────────────────────────────────────────────────────

class TestDataClasses:
    """Test ProvenanceMetrics and DeforestationAttestation data classes."""

    def test_provenance_metrics_to_dict(self):
        from chainlink.cre_client import ProvenanceMetrics
        m = ProvenanceMetrics(
            total_farmers=10, total_batches=25, verified_batches=20,
            total_quantity_kg=5000, eudr_compliant_percent=80,
            batches_anchored=15, last_updated=1700000000, exists=True,
        )
        d = m.to_dict()
        assert d["total_farmers"] == 10
        assert d["exists"] is True
        assert isinstance(d, dict)

    def test_deforestation_attestation_risk_labels(self):
        from chainlink.cre_client import DeforestationAttestation
        for code, label in [(0, "LOW"), (1, "MEDIUM"), (2, "HIGH"), (3, "UNKNOWN")]:
            att = DeforestationAttestation(
                farm_id="F1", latitude=7.0, longitude=38.0,
                risk_level=code, eudr_compliant=True,
                tree_loss_hectares=0.0, timestamp=0, exists=True,
            )
            assert att.risk_label == label

    def test_deforestation_attestation_to_dict(self):
        from chainlink.cre_client import DeforestationAttestation
        att = DeforestationAttestation(
            farm_id="FARMER-001", latitude=7.123456, longitude=38.654321,
            risk_level=0, eudr_compliant=True,
            tree_loss_hectares=0.001, timestamp=1700000000, exists=True,
        )
        d = att.to_dict()
        assert d["farm_id"] == "FARMER-001"
        assert d["risk_label"] == "LOW"
        assert "risk_label" in d  # bonus field from property


# ─────────────────────────────────────────────────────────────
# 2. CRE Client initialisation (mocked Web3)
# ─────────────────────────────────────────────────────────────

class TestCREClientInit:
    """Test CREClient creation with mocked Web3."""

    @patch.dict(os.environ, {
        "BASE_SEPOLIA_RPC_URL": "https://mock-rpc.example.com",
        "PRIVATE_KEY_SEP": "0x" + "ab" * 32,
        "PROVENANCE_RECEIVER_ADDRESS": "0x" + "00" * 20,
    })
    @patch("chainlink.cre_client.Web3")
    def test_client_init_undeployed(self, mock_web3_cls):
        """Client should initialise but mark contract as not deployed (zero address)."""
        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_web3_cls.return_value = mock_w3
        mock_web3_cls.HTTPProvider = MagicMock()

        from chainlink.cre_client import CREClient
        # Reset singleton
        import chainlink.cre_client as mod
        mod._cre_client = None

        client = CREClient()
        assert client._deployed is False  # zero address

    @patch.dict(os.environ, {
        "BASE_SEPOLIA_RPC_URL": "https://mock-rpc.example.com",
        "PRIVATE_KEY_SEP": "0x" + "ab" * 32,
        "PROVENANCE_RECEIVER_ADDRESS": "0xfda9e00d22eb166796449e919295e9755fd9a699",
    })
    @patch("chainlink.cre_client.Web3")
    def test_client_init_deployed(self, mock_web3_cls):
        """Client should mark contract as deployed with real address."""
        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.contract.return_value = MagicMock()
        mock_web3_cls.return_value = mock_w3
        mock_web3_cls.HTTPProvider = MagicMock()
        mock_web3_cls.to_checksum_address = lambda x: x

        from chainlink.cre_client import CREClient
        import chainlink.cre_client as mod
        mod._cre_client = None

        client = CREClient()
        assert client._deployed is True


# ─────────────────────────────────────────────────────────────
# 3. Agent tool schema tests
# ─────────────────────────────────────────────────────────────

class TestToolSchemas:
    """Verify the 3 new CRE tool schemas are present and well-formed."""

    def test_supply_chain_tools_has_cre_tools(self):
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        tool_names = [t["function"]["name"] for t in SUPPLY_CHAIN_TOOLS]
        assert "request_don_attestation" in tool_names
        assert "check_don_attestation" in tool_names
        assert "get_don_provenance_metrics" in tool_names

    def test_total_tool_count(self):
        """Should now have 28 tools (25 original + 3 CRE)."""
        from voice.agent.tools import SUPPLY_CHAIN_TOOLS
        assert len(SUPPLY_CHAIN_TOOLS) == 28

    def test_request_don_attestation_schema(self):
        from voice.agent.tools import REQUEST_DON_ATTESTATION
        func = REQUEST_DON_ATTESTATION["function"]
        assert func["name"] == "request_don_attestation"
        assert "farm_id" in func["parameters"]["properties"]
        assert "farm_id" in func["parameters"]["required"]

    def test_check_don_attestation_schema(self):
        from voice.agent.tools import CHECK_DON_ATTESTATION
        func = CHECK_DON_ATTESTATION["function"]
        assert func["name"] == "check_don_attestation"
        assert "farm_id" in func["parameters"]["properties"]

    def test_get_don_provenance_metrics_schema(self):
        from voice.agent.tools import GET_DON_PROVENANCE_METRICS
        func = GET_DON_PROVENANCE_METRICS["function"]
        assert func["name"] == "get_don_provenance_metrics"
        # No required params
        assert func["parameters"]["properties"] == {}


# ─────────────────────────────────────────────────────────────
# 4. Registry handler tests
# ─────────────────────────────────────────────────────────────

class TestRegistryHandlers:
    """Verify CRE tool handlers are registered and callable."""

    def test_registry_has_cre_tools(self):
        """All 3 CRE tools should be registered."""
        # Reset registry singleton
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry

        registry = get_tool_registry()
        assert registry.has("request_don_attestation")
        assert registry.has("check_don_attestation")
        assert registry.has("get_don_provenance_metrics")

    def test_total_registered_tools(self):
        """Should have 28 tools registered."""
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry

        registry = get_tool_registry()
        assert len(registry.tool_names) == 28

    @patch("voice.agent.registry._get_cre_client")
    def test_check_don_attestation_no_farm_id(self, mock_client):
        """Handler should return error if no farm_id provided."""
        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry

        registry = get_tool_registry()
        handler = registry.get("check_don_attestation")
        msg, data = handler(MagicMock(), {}, user_id=1)
        assert "specify" in msg.lower()
        assert "error" in data

    @patch("voice.agent.registry._get_cre_client")
    def test_get_don_provenance_metrics_handler(self, mock_get_client):
        """Handler should return metrics when contract has data."""
        from chainlink.cre_client import ProvenanceMetrics
        mock_client = MagicMock()
        mock_client.get_provenance_metrics.return_value = ProvenanceMetrics(
            total_farmers=42, total_batches=100, verified_batches=80,
            total_quantity_kg=50000, eudr_compliant_percent=95,
            batches_anchored=75, last_updated=1700000000, exists=True,
        )
        mock_get_client.return_value = mock_client

        import voice.agent.registry as reg_mod
        reg_mod._registry = None
        from voice.agent.registry import get_tool_registry

        registry = get_tool_registry()
        handler = registry.get("get_don_provenance_metrics")
        msg, data = handler(MagicMock(), {}, user_id=1)
        assert "42" in msg  # total_farmers
        assert "95%" in msg  # eudr_compliant_percent
        assert data["total_farmers"] == 42


# ─────────────────────────────────────────────────────────────
# 5. DPP DON attestation section tests
# ─────────────────────────────────────────────────────────────

class TestDPPDONAttestation:
    """Test build_don_attestation_section function."""

    @patch("chainlink.cre_client.get_cre_client")
    def test_section_when_not_deployed(self, mock_get_client):
        """Should return section with exists=False when contract not deployed."""
        mock_client = MagicMock()
        mock_client._deployed = False
        mock_get_client.return_value = mock_client

        from dpp.dpp_builder import build_don_attestation_section
        section = build_don_attestation_section("BATCH-001")
        assert section["attestationExists"] is False
        assert "not deployed" in section.get("note", "").lower()

    @patch("dpp.dpp_builder._resolve_farm_id")
    @patch("chainlink.cre_client.get_cre_client")
    def test_section_with_attestation(self, mock_get_client, mock_resolve):
        """Should include full attestation data when available."""
        from chainlink.cre_client import DeforestationAttestation, ProvenanceMetrics

        mock_resolve.return_value = "FARMER-001"

        mock_client = MagicMock()
        mock_client._deployed = True
        mock_client.get_deforestation_attestation.return_value = DeforestationAttestation(
            farm_id="FARMER-001", latitude=7.0, longitude=38.0,
            risk_level=0, eudr_compliant=True,
            tree_loss_hectares=0.001, timestamp=1700000000, exists=True,
        )
        mock_client.get_provenance_metrics.return_value = ProvenanceMetrics(
            total_farmers=10, total_batches=20, verified_batches=15,
            total_quantity_kg=5000, eudr_compliant_percent=90,
            batches_anchored=12, last_updated=1700000000, exists=True,
        )
        mock_get_client.return_value = mock_client

        from dpp.dpp_builder import build_don_attestation_section
        section = build_don_attestation_section("BATCH-001")
        assert section["attestationExists"] is True
        assert section["riskLabel"] == "LOW"
        assert section["eudrCompliant"] is True
        assert "platformMetrics" in section
        assert section["platformMetrics"]["totalFarmers"] == 10

    @patch("dpp.dpp_builder._resolve_farm_id")
    @patch("chainlink.cre_client.get_cre_client")
    def test_section_no_attestation(self, mock_get_client, mock_resolve):
        """Should indicate no attestation when farm not yet attested."""
        from chainlink.cre_client import DeforestationAttestation

        mock_resolve.return_value = "FARMER-002"
        mock_client = MagicMock()
        mock_client._deployed = True
        mock_client.get_deforestation_attestation.return_value = DeforestationAttestation(
            farm_id="FARMER-002", latitude=0, longitude=0,
            risk_level=3, eudr_compliant=False,
            tree_loss_hectares=0, timestamp=0, exists=False,
        )
        mock_get_client.return_value = mock_client

        from dpp.dpp_builder import build_don_attestation_section
        section = build_don_attestation_section("BATCH-002")
        assert section["attestationExists"] is False


# ─────────────────────────────────────────────────────────────
# 6. System prompt includes CRE section
# ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    """Verify system prompt now includes Chainlink DON tools."""

    def test_system_prompt_has_cre_section(self):
        from voice.agent.executor import AGENT_SYSTEM_PROMPT
        assert "CHAINLINK DON ATTESTATION" in AGENT_SYSTEM_PROMPT
        assert "request_don_attestation" in AGENT_SYSTEM_PROMPT
        assert "check_don_attestation" in AGENT_SYSTEM_PROMPT
        assert "get_don_provenance_metrics" in AGENT_SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────
# 7. ABI file exists
# ─────────────────────────────────────────────────────────────

class TestABIFile:
    """Verify ProvenanceDataReceiver ABI is extractable."""

    def test_abi_file_exists(self):
        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "blockchain_abis", "ProvenanceDataReceiver.json",
        )
        assert os.path.exists(abi_path)

    def test_abi_has_required_functions(self):
        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "blockchain_abis", "ProvenanceDataReceiver.json",
        )
        with open(abi_path) as f:
            data = json.load(f)
        abi = data.get("abi", data)
        func_names = [
            i["name"] for i in abi
            if i.get("type") == "function"
        ]
        assert "getProvenanceMetrics" in func_names
        assert "getDeforestationAttestation" in func_names
        assert "isFarmCompliant" in func_names
        assert "onReport" in func_names
        assert "reportCount" in func_names
        assert "attestedFarmCount" in func_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
