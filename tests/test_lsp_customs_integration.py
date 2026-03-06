"""
Tests for LSP & Customs Clearance integration modules:
  - voice/service/dpp_api.py
  - voice/service/logistics_api.py
  - voice/service/webhook_dispatcher.py
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ── Webhook dispatcher (pure in-memory, no DB needed) ────────────────────────

from voice.service.webhook_dispatcher import (
    register_webhook,
    unregister_webhook,
    list_webhooks,
    dispatch_webhook,
    _webhooks,
    VALID_EVENTS,
)


class TestWebhookDispatcher:
    """Unit tests for the in-memory webhook dispatcher."""

    def setup_method(self):
        _webhooks.clear()

    def test_register_webhook(self):
        wh = register_webhook(
            url="https://example.com/hook",
            events=["PREPARING_SHIPMENT"],
            secret="s3cret",
            description="test hook",
        )
        assert wh.id in _webhooks
        assert wh.url == "https://example.com/hook"
        assert wh.events == ["PREPARING_SHIPMENT"]
        assert wh.secret == "s3cret"
        assert wh.active is True
        assert wh.delivery_count == 0

    def test_register_invalid_event_raises(self):
        with pytest.raises(ValueError, match="Invalid event type"):
            register_webhook(url="https://x.com", events=["BOGUS_EVENT"])

    def test_list_webhooks(self):
        register_webhook(url="https://a.com", events=["SHIPPED"])
        register_webhook(url="https://b.com", events=["DELIVERED"])
        result = list_webhooks()
        assert len(result) == 2
        urls = {w["url"] for w in result}
        assert urls == {"https://a.com", "https://b.com"}

    def test_unregister_webhook(self):
        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        assert unregister_webhook(wh.id) is True
        assert wh.id not in _webhooks

    def test_unregister_nonexistent_returns_false(self):
        assert unregister_webhook("nonexistent") is False

    def test_to_dict_fields(self):
        wh = register_webhook(url="https://a.com", events=["SHIPPED"], description="desc")
        d = wh.to_dict()
        assert d["url"] == "https://a.com"
        assert d["events"] == ["SHIPPED"]
        assert d["description"] == "desc"
        assert d["active"] is True
        assert d["delivery_count"] == 0
        assert d["failure_count"] == 0
        assert d["last_triggered_at"] is None

    def test_valid_events_constant(self):
        assert "PREPARING_SHIPMENT" in VALID_EVENTS
        assert "SHIPPED" in VALID_EVENTS
        assert "DELIVERED" in VALID_EVENTS
        assert "MILESTONE_RECEIVED" in VALID_EVENTS

    @pytest.mark.asyncio
    async def test_dispatch_to_matching_webhooks(self):
        """dispatch_webhook returns count of matching targets."""
        register_webhook(url="https://example.com/hook", events=["SHIPPED"])

        async def _fake_deliver(wh, payload):
            pass

        with patch("voice.service.webhook_dispatcher._deliver", side_effect=_fake_deliver):
            count = await dispatch_webhook("SHIPPED", {"container_sscc": "123"})
        assert count == 1

    @pytest.mark.asyncio
    async def test_dispatch_no_match_returns_zero(self):
        register_webhook(url="https://example.com/hook", events=["SHIPPED"])
        count = await dispatch_webhook("DELIVERED", {"info": "x"})
        assert count == 0


# ── Logistics & Webhook API router (endpoint-level) ─────────────────────────

from voice.service.logistics_api import router as logistics_router
from fastapi import FastAPI

_logistics_app = FastAPI()
_logistics_app.include_router(logistics_router)
logistics_client = TestClient(_logistics_app)


class TestWebhookEndpoints:
    """Test the /api/webhooks/* HTTP endpoints."""

    def setup_method(self):
        _webhooks.clear()

    def test_register_webhook_endpoint(self):
        resp = logistics_client.post("/api/webhooks/register", json={
            "url": "https://lsp.example.com/callback",
            "events": ["PREPARING_SHIPMENT", "SHIPPED"],
            "description": "LSP booking trigger",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://lsp.example.com/callback"
        assert set(data["events"]) == {"PREPARING_SHIPMENT", "SHIPPED"}
        assert data["active"] is True

    def test_register_invalid_event_returns_400(self):
        resp = logistics_client.post("/api/webhooks/register", json={
            "url": "https://x.com",
            "events": ["NOT_A_REAL_EVENT"],
        })
        assert resp.status_code == 400

    def test_list_webhooks_endpoint(self):
        logistics_client.post("/api/webhooks/register", json={
            "url": "https://a.com", "events": ["SHIPPED"],
        })
        resp = logistics_client.get("/api/webhooks")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_webhook_endpoint(self):
        create_resp = logistics_client.post("/api/webhooks/register", json={
            "url": "https://a.com", "events": ["SHIPPED"],
        })
        wh_id = create_resp.json()["id"]
        del_resp = logistics_client.delete(f"/api/webhooks/{wh_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

    def test_delete_nonexistent_returns_404(self):
        resp = logistics_client.delete("/api/webhooks/nonexistent")
        assert resp.status_code == 404


class TestMilestoneEndpoint:
    """Test the /api/logistics/milestone endpoint."""

    def test_invalid_milestone_type_returns_400(self):
        resp = logistics_client.post("/api/logistics/milestone", json={
            "container_sscc": "306141410000000001",
            "milestone_type": "BOGUS",
        })
        assert resp.status_code == 400
        assert "Invalid milestone_type" in resp.json()["detail"]

    @patch("voice.service.logistics_api.get_db")
    @patch("voice.service.logistics_api.dispatch_webhook", new_callable=lambda: lambda: asyncio.coroutine(lambda *a, **k: 0))
    def test_container_not_found_returns_404(self, mock_dispatch, mock_get_db):
        """If the container SSCC doesn't exist, return 404."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = lambda s: mock_db
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = logistics_client.post("/api/logistics/milestone", json={
            "container_sscc": "999999999999999999",
            "milestone_type": "PICKUP",
            "location_name": "Djibouti Port",
            "carrier": "Maersk",
        })
        assert resp.status_code == 404


class TestShipmentStatusEndpoint:

    @patch("voice.service.logistics_api.get_db")
    def test_container_not_found_returns_404(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = lambda s: mock_db
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = logistics_client.get("/api/logistics/shipment/999999999999999999")
        assert resp.status_code == 404


# ── DPP API router ──────────────────────────────────────────────────────────

from voice.service.dpp_api import router as dpp_router, _build_article9

_dpp_app = FastAPI()
_dpp_app.include_router(dpp_router)
dpp_client = TestClient(_dpp_app)


class TestDPPEndpoints:

    @patch("voice.service.dpp_api.load_batch_data", return_value=None)
    def test_batch_dpp_not_found(self, mock_load):
        resp = dpp_client.get("/api/dpp/batch/NONEXISTENT")
        assert resp.status_code == 404

    @patch("voice.service.dpp_api.get_db")
    def test_verify_batch_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.__enter__ = lambda s: mock_db
        mock_db.__exit__ = MagicMock(return_value=False)
        # Make get_batch_by_batch_id return None
        with patch("voice.service.dpp_api.get_batch_by_batch_id", return_value=None):
            resp = dpp_client.get("/api/dpp/batch/NONEXISTENT/verify")
        assert resp.status_code == 404

    @patch("voice.service.dpp_api.get_db")
    def test_container_dpp_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = lambda s: mock_db
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = dpp_client.get("/api/dpp/container/999999999999999999")
        assert resp.status_code == 404

    @patch("voice.service.dpp_api.get_all_batches")
    @patch("voice.service.dpp_api.get_db")
    def test_list_batches_empty(self, mock_get_db, mock_get_all):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = lambda s: mock_db
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_all.return_value = []

        resp = dpp_client.get("/api/dpp/batches")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @patch("voice.service.dpp_api.load_batch_data", return_value=None)
    def test_eudr_compliance_not_found(self, mock_load):
        resp = dpp_client.get("/api/eudr/compliance/NONEXISTENT")
        assert resp.status_code == 404

    @patch("voice.service.dpp_api.get_db")
    def test_eudr_container_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = lambda s: mock_db
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = dpp_client.get("/api/eudr/container/999999999999999999")
        assert resp.status_code == 404
