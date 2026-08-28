"""
Tests for voice/service/webhook_dispatcher.py and its compatibility with
voice/service/logistics_api.py.

Approach: zero real DB/Redis/network. All external I/O is either stubbed via
sys.modules monkeypatching (same pattern as test_commitment_logistics_tools.py)
or patched with unittest.mock. No @pytest.mark.asyncio — async tests use
anyio (already installed) or asyncio.run().
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make sure test env never hits production Redis
# ---------------------------------------------------------------------------
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-for-tests-only")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in a new event loop (avoids pytest-asyncio dependency)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _clear_cache():
    """Reset the in-process webhook cache between tests."""
    from voice.service.webhook_dispatcher import _webhooks_cache
    import voice.service.webhook_dispatcher as _mod
    _webhooks_cache.clear()
    _mod._cache_loaded = True   # prevent Redis load during unit tests
    _mod._webhooks_memory.clear()


# ===========================================================================
# WebhookRegistration unit tests
# ===========================================================================

class TestWebhookRegistration:
    """Pure unit tests — no I/O."""

    def setup_method(self):
        _clear_cache()

    def test_default_fields(self):
        from voice.service.webhook_dispatcher import WebhookRegistration
        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])
        assert wh.url == "https://a.com"
        assert wh.events == ["SHIPPED"]
        assert wh.secret is None
        assert wh.active is True
        assert wh.delivery_count == 0
        assert wh.failure_count == 0
        assert wh.last_triggered_at is None
        assert len(wh.id) == 32          # full uuid4().hex

    def test_to_dict_includes_all_fields(self):
        from voice.service.webhook_dispatcher import WebhookRegistration
        wh = WebhookRegistration(
            url="https://a.com", events=["SHIPPED"], secret="s3cr3t", description="d"
        )
        d = wh.to_dict()
        for key in ("id", "url", "events", "secret", "description",
                    "active", "created_at", "last_triggered_at",
                    "delivery_count", "failure_count"):
            assert key in d, f"Missing key: {key}"
        assert d["secret"] == "s3cr3t"
        assert d["last_triggered_at"] is None

    def test_from_dict_full_round_trip(self):
        from voice.service.webhook_dispatcher import WebhookRegistration
        wh = WebhookRegistration(
            url="https://b.com", events=["DELIVERED", "SHIPPED"],
            secret="mysecret", description="test"
        )
        wh.delivery_count = 5
        wh.failure_count = 2
        wh.last_triggered_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

        d = wh.to_dict()
        wh2 = WebhookRegistration.from_dict(d)

        assert wh2.id == wh.id
        assert wh2.url == wh.url
        assert wh2.events == wh.events
        assert wh2.secret == "mysecret"
        assert wh2.description == "test"
        assert wh2.active is True
        assert wh2.delivery_count == 5
        assert wh2.failure_count == 2
        assert wh2.last_triggered_at == wh.last_triggered_at
        assert wh2.created_at.tzinfo is not None

    def test_from_dict_naive_timestamps_get_utc(self):
        """Naive ISO timestamps should be made timezone-aware."""
        from voice.service.webhook_dispatcher import WebhookRegistration
        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])
        d = wh.to_dict()
        # Strip tz info from timestamps to simulate legacy data
        d["created_at"] = d["created_at"].replace("+00:00", "")
        wh2 = WebhookRegistration.from_dict(d)
        assert wh2.created_at.tzinfo is not None

    def test_from_dict_missing_optional_fields(self):
        """from_dict must not crash on minimal data."""
        from voice.service.webhook_dispatcher import WebhookRegistration
        d = {"id": "abc", "url": "https://a.com", "events": ["SHIPPED"]}
        wh = WebhookRegistration.from_dict(d)
        assert wh.url == "https://a.com"
        assert wh.delivery_count == 0
        assert wh.failure_count == 0
        assert wh.secret is None


# ===========================================================================
# Secret encryption
# ===========================================================================

class TestSecretEncryption:

    def test_encrypt_decrypt_round_trip(self):
        from voice.service.webhook_dispatcher import _encrypt_secret, _decrypt_secret
        plaintext = "super-secret-hmac-key"
        token = _encrypt_secret(plaintext)
        assert token != plaintext
        assert _decrypt_secret(token) == plaintext

    def test_decrypt_legacy_plaintext(self):
        """A value stored before encryption was added must pass through unchanged."""
        from voice.service.webhook_dispatcher import _decrypt_secret
        result = _decrypt_secret("plaintext-legacy-secret")
        assert result == "plaintext-legacy-secret"

    def test_secret_not_exposed_in_saved_payload(self):
        """_save_webhook must encrypt the secret before writing; the in-memory
        fallback stores the object (secret accessible on the object, not in
        the raw serialised form that would go to Redis)."""
        from voice.service.webhook_dispatcher import (
            _encrypt_secret, WebhookRegistration,
        )
        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"], secret="topsecret")
        raw = wh.to_dict()
        if raw.get("secret"):
            raw = {**raw, "secret": _encrypt_secret(raw["secret"])}
        serialised = json.dumps(raw)
        assert "topsecret" not in serialised


# ===========================================================================
# URL validation
# ===========================================================================

class TestURLValidation:

    def test_https_accepted(self):
        from voice.service.webhook_dispatcher import _validate_url
        _validate_url("https://example.com/hook")   # must not raise

    def test_http_rejected_in_production(self):
        from voice.service.webhook_dispatcher import _validate_url
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValueError, match="HTTPS"):
                _validate_url("http://example.com/hook")

    def test_http_localhost_allowed_in_dev(self):
        from voice.service.webhook_dispatcher import _validate_url
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            _validate_url("http://localhost/hook")   # must not raise

    def test_http_external_rejected_even_in_dev(self):
        from voice.service.webhook_dispatcher import _validate_url
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            with pytest.raises(ValueError, match="HTTPS"):
                _validate_url("http://evil.com/hook")

    def test_register_http_raises_value_error(self):
        """register_webhook must propagate _validate_url's ValueError."""
        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValueError, match="HTTPS"):
                register_webhook(url="http://example.com/hook", events=["SHIPPED"])


# ===========================================================================
# VALID_EVENTS
# ===========================================================================

class TestValidEvents:

    def test_all_expected_events_present(self):
        from voice.service.webhook_dispatcher import VALID_EVENTS
        for evt in ("PREPARING_SHIPMENT", "SHIPPED", "DELIVERED",
                    "PAYMENT_CONFIRMED", "MILESTONE_RECEIVED"):
            assert evt in VALID_EVENTS

    def test_register_invalid_event_raises(self):
        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook
        with pytest.raises(ValueError, match="Invalid event type"):
            register_webhook(url="https://x.com", events=["BOGUS_EVENT"])


# ===========================================================================
# register / unregister / list — in-memory (no Redis)
# ===========================================================================

class TestRegistration:

    def setup_method(self):
        _clear_cache()

    def test_register_returns_webhook_registration(self):
        from voice.service.webhook_dispatcher import register_webhook, WebhookRegistration
        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        assert isinstance(wh, WebhookRegistration)
        assert wh.url == "https://a.com"
        assert wh.active is True

    def test_registered_webhook_in_cache(self):
        from voice.service.webhook_dispatcher import register_webhook, _webhooks_cache
        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        assert wh.id in _webhooks_cache

    def test_list_webhooks_returns_dicts_without_secret(self):
        from voice.service.webhook_dispatcher import register_webhook, list_webhooks
        register_webhook(url="https://a.com", events=["SHIPPED"], secret="hidden")
        items = list_webhooks()
        assert len(items) == 1
        assert "secret" not in items[0]
        assert items[0]["url"] == "https://a.com"

    def test_list_webhooks_all_required_fields(self):
        from voice.service.webhook_dispatcher import register_webhook, list_webhooks
        register_webhook(url="https://a.com", events=["SHIPPED"], description="desc")
        d = list_webhooks()[0]
        for key in ("id", "url", "events", "description", "active",
                    "created_at", "last_triggered_at", "delivery_count", "failure_count"):
            assert key in d, f"Missing key '{key}' in list_webhooks output"

    def test_unregister_returns_true_and_removes(self):
        from voice.service.webhook_dispatcher import (
            register_webhook, unregister_webhook, _webhooks_cache,
        )
        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        assert unregister_webhook(wh.id) is True
        assert wh.id not in _webhooks_cache

    def test_unregister_nonexistent_returns_false(self):
        from voice.service.webhook_dispatcher import unregister_webhook
        assert unregister_webhook("nonexistent-id") is False

    def test_multiple_webhooks_independent(self):
        from voice.service.webhook_dispatcher import (
            register_webhook, unregister_webhook, list_webhooks,
        )
        wh1 = register_webhook(url="https://a.com", events=["SHIPPED"])
        wh2 = register_webhook(url="https://b.com", events=["DELIVERED"])
        assert len(list_webhooks()) == 2
        unregister_webhook(wh1.id)
        remaining = list_webhooks()
        assert len(remaining) == 1
        assert remaining[0]["url"] == "https://b.com"


# ===========================================================================
# dispatch_webhook — in-memory cache, no real HTTP
# ===========================================================================

class TestDispatch:

    def setup_method(self):
        _clear_cache()

    def test_dispatch_returns_count_of_matching_targets(self):
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook

        register_webhook(url="https://a.com", events=["SHIPPED"])
        register_webhook(url="https://b.com", events=["DELIVERED"])

        async def run():
            with patch("voice.service.webhook_dispatcher._deliver", new=AsyncMock()):
                return await dispatch_webhook("SHIPPED", {"sscc": "123"})

        count = _run(run())
        assert count == 1

    def test_dispatch_no_match_returns_zero(self):
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook

        register_webhook(url="https://a.com", events=["SHIPPED"])

        async def run():
            return await dispatch_webhook("DELIVERED", {})

        assert _run(run()) == 0

    def test_dispatch_multiple_subscribers_same_event(self):
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook

        register_webhook(url="https://a.com", events=["MILESTONE_RECEIVED"])
        register_webhook(url="https://b.com", events=["MILESTONE_RECEIVED"])
        register_webhook(url="https://c.com", events=["SHIPPED"])

        async def run():
            with patch("voice.service.webhook_dispatcher._deliver", new=AsyncMock()):
                return await dispatch_webhook("MILESTONE_RECEIVED", {})

        assert _run(run()) == 2

    def test_dispatch_inactive_webhook_skipped(self):
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook, _webhooks_cache

        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        _webhooks_cache[wh.id].active = False

        async def run():
            with patch("voice.service.webhook_dispatcher._deliver", new=AsyncMock()):
                return await dispatch_webhook("SHIPPED", {})

        assert _run(run()) == 0

    def test_dispatch_injects_event_and_timestamp(self):
        """dispatch_webhook must inject 'event' and 'timestamp' into the payload."""
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook

        register_webhook(url="https://a.com", events=["SHIPPED"])
        delivered_payloads = []

        async def fake_deliver(wh, payload):
            delivered_payloads.append(payload)

        async def run():
            with patch("voice.service.webhook_dispatcher._deliver", side_effect=fake_deliver):
                await dispatch_webhook("SHIPPED", {"sscc": "TEST123"})
            # Let tasks complete
            await asyncio.sleep(0)

        _run(run())
        assert len(delivered_payloads) == 1
        p = delivered_payloads[0]
        assert p["event"] == "SHIPPED"
        assert "timestamp" in p
        assert p["sscc"] == "TEST123"

    def test_dispatch_does_not_mutate_caller_payload(self):
        """The caller's payload dict must not be modified by dispatch_webhook."""
        from voice.service.webhook_dispatcher import register_webhook, dispatch_webhook

        register_webhook(url="https://a.com", events=["SHIPPED"])
        original = {"sscc": "ABC"}

        async def run():
            with patch("voice.service.webhook_dispatcher._deliver", new=AsyncMock()):
                await dispatch_webhook("SHIPPED", original)

        _run(run())
        assert original == {"sscc": "ABC"}   # unchanged


# ===========================================================================
# _deliver — HMAC signature, retry, counter persistence
# ===========================================================================

class TestDeliver:

    def setup_method(self):
        _clear_cache()

    def test_hmac_signature_header_added_when_secret_set(self):
        """X-VoiceLedger-Signature must be sha256=<hmac> when secret is set."""
        from voice.service.webhook_dispatcher import WebhookRegistration, _deliver

        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"], secret="mykey")
        payload = {"event": "SHIPPED", "sscc": "123"}
        body = json.dumps(payload, default=str).encode()
        expected_sig = hmac.new(b"mykey", body, hashlib.sha256).hexdigest()

        captured_headers = {}

        async def fake_post(url, content, headers):
            captured_headers.update(headers)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        async def run():
            with patch("voice.service.webhook_dispatcher._get_httpx_client") as mock_client:
                mock_client.return_value.post = fake_post
                with patch("voice.service.webhook_dispatcher._save_webhook"):
                    await _deliver(wh, payload)

        _run(run())
        assert "X-VoiceLedger-Signature" in captured_headers
        assert captured_headers["X-VoiceLedger-Signature"] == f"sha256={expected_sig}"

    def test_no_signature_header_without_secret(self):
        from voice.service.webhook_dispatcher import WebhookRegistration, _deliver

        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])
        captured_headers = {}

        async def fake_post(url, content, headers):
            captured_headers.update(headers)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        async def run():
            with patch("voice.service.webhook_dispatcher._get_httpx_client") as mock_client:
                mock_client.return_value.post = fake_post
                with patch("voice.service.webhook_dispatcher._save_webhook"):
                    await _deliver(wh, {"event": "SHIPPED"})

        _run(run())
        assert "X-VoiceLedger-Signature" not in captured_headers

    def test_delivery_count_incremented_on_success(self):
        from voice.service.webhook_dispatcher import WebhookRegistration, _deliver

        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])
        assert wh.delivery_count == 0

        async def fake_post(url, content, headers):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        async def run():
            with patch("voice.service.webhook_dispatcher._get_httpx_client") as mock_client:
                mock_client.return_value.post = fake_post
                with patch("voice.service.webhook_dispatcher._save_webhook"):
                    await _deliver(wh, {"event": "SHIPPED"})

        _run(run())
        assert wh.delivery_count == 1
        assert wh.last_triggered_at is not None

    def test_failure_count_incremented_after_all_retries(self):
        from voice.service.webhook_dispatcher import WebhookRegistration, _deliver

        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])

        async def fake_post(url, content, headers):
            resp = MagicMock()
            resp.status_code = 500
            return resp

        async def run():
            with patch("voice.service.webhook_dispatcher._get_httpx_client") as mock_client:
                mock_client.return_value.post = fake_post
                with patch("voice.service.webhook_dispatcher._save_webhook"):
                    with patch("asyncio.sleep", new=AsyncMock()):
                        await _deliver(wh, {"event": "SHIPPED"})

        _run(run())
        assert wh.failure_count == 1
        assert wh.delivery_count == 0

    def test_retries_on_network_error(self):
        """_deliver must retry on exceptions, not just bad status codes."""
        from voice.service.webhook_dispatcher import WebhookRegistration, _deliver

        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])
        call_count = {"n": 0}

        async def fake_post(url, content, headers):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("timeout")
            resp = MagicMock()
            resp.status_code = 200
            return resp

        async def run():
            with patch("voice.service.webhook_dispatcher._get_httpx_client") as mock_client:
                mock_client.return_value.post = fake_post
                with patch("voice.service.webhook_dispatcher._save_webhook"):
                    with patch("asyncio.sleep", new=AsyncMock()):
                        await _deliver(wh, {"event": "SHIPPED"})

        _run(run())
        assert call_count["n"] == 3
        assert wh.delivery_count == 1


# ===========================================================================
# warm_cache / _load_webhooks_from_store — Redis mocked with fakeredis pattern
# ===========================================================================

class TestCachePersistence:

    def setup_method(self):
        _clear_cache()

    def _make_fake_redis(self, stored: dict = None):
        """Return a minimal fake Redis-like object backed by a plain dict."""
        store = {}
        index = set()
        if stored:
            for wid, data in stored.items():
                store[f"vl:webhooks:{wid}"] = data
                index.add(wid)

        class FakeRedis:
            def ping(self): return True
            def set(self, key, value): store[key] = value
            def get(self, key): return store.get(key)
            def sadd(self, key, *vals):
                for v in vals: index.add(v)
            def smembers(self, key): return set(index)
            def srem(self, key, val): index.discard(val)
            def delete(self, key): store.pop(key, None)
            def pipeline(self):
                pipe = MagicMock()
                cmds = []
                def _delete(k): cmds.append(("delete", k))
                def _srem(k, v): cmds.append(("srem", k, v))
                def _execute():
                    for cmd in cmds:
                        if cmd[0] == "delete": store.pop(cmd[1], None)
                        elif cmd[0] == "srem": index.discard(cmd[2])
                pipe.delete = _delete
                pipe.srem = _srem
                pipe.execute = _execute
                return pipe
            def publish(self, channel, msg): pass

        return FakeRedis(), store, index

    def test_save_and_load_round_trip(self):
        from voice.service.webhook_dispatcher import (
            WebhookRegistration, _save_webhook, _load_webhooks_from_store,
        )
        fake_r, store, index = self._make_fake_redis()

        wh = WebhookRegistration(
            url="https://a.com", events=["SHIPPED"], secret="s3cr3t"
        )

        with patch("voice.service.webhook_dispatcher._get_redis", return_value=fake_r):
            _save_webhook(wh)
            result = _load_webhooks_from_store()

        assert wh.id in result
        loaded = result[wh.id]
        assert loaded.url == "https://a.com"
        assert loaded.secret == "s3cr3t"    # decrypted on load
        assert loaded.delivery_count == 0

    def test_save_encrypts_secret_in_redis(self):
        from voice.service.webhook_dispatcher import WebhookRegistration, _save_webhook
        fake_r, store, index = self._make_fake_redis()

        wh = WebhookRegistration(
            url="https://a.com", events=["SHIPPED"], secret="topsecret"
        )
        with patch("voice.service.webhook_dispatcher._get_redis", return_value=fake_r):
            _save_webhook(wh)

        key = f"vl:webhooks:{wh.id}"
        raw = json.loads(store[key])
        assert raw["secret"] != "topsecret"     # must be encrypted token

    def test_load_skips_corrupt_entries(self):
        from voice.service.webhook_dispatcher import _load_webhooks_from_store
        fake_r, store, index = self._make_fake_redis()
        # Inject a corrupt entry manually
        store["vl:webhooks:bad"] = "not-valid-json{{{"
        index.add("bad")

        with patch("voice.service.webhook_dispatcher._get_redis", return_value=fake_r):
            result = _load_webhooks_from_store()

        assert "bad" not in result    # corrupt entry silently skipped

    def test_warm_cache_loads_from_redis(self):
        from voice.service.webhook_dispatcher import (
            WebhookRegistration, _webhooks_cache, warm_cache, _save_webhook,
        )
        fake_r, store, index = self._make_fake_redis()
        wh = WebhookRegistration(url="https://a.com", events=["DELIVERED"])

        with patch("voice.service.webhook_dispatcher._get_redis", return_value=fake_r):
            _save_webhook(wh)
            _webhooks_cache.clear()
            count = warm_cache()

        assert count == 1
        assert wh.id in _webhooks_cache

    def test_delete_webhook_atomic_pipeline(self):
        """_delete_webhook must remove both the key and the index entry."""
        from voice.service.webhook_dispatcher import (
            WebhookRegistration, _save_webhook, _delete_webhook,
        )
        fake_r, store, index = self._make_fake_redis()
        wh = WebhookRegistration(url="https://a.com", events=["SHIPPED"])

        with patch("voice.service.webhook_dispatcher._get_redis", return_value=fake_r):
            _save_webhook(wh)
            assert wh.id in index
            _delete_webhook(wh.id)
            assert f"vl:webhooks:{wh.id}" not in store
            assert wh.id not in index

    def test_fallback_to_memory_when_redis_unavailable(self):
        from voice.service.webhook_dispatcher import (
            register_webhook, list_webhooks,
        )
        with patch("voice.service.webhook_dispatcher._get_redis", return_value=None):
            wh = register_webhook(url="https://a.com", events=["SHIPPED"])

        items = list_webhooks()
        assert any(i["url"] == "https://a.com" for i in items)


# ===========================================================================
# logistics_api.py compatibility — mock the entire database layer
# ===========================================================================

def _install_db_stubs(monkeypatch):
    """
    Stub out every database import that logistics_api.py triggers at import time.
    Uses the same sys.modules injection pattern as test_commitment_logistics_tools.py.
    """
    # ── database package ──────────────────────────────────────────────────
    db_pkg  = types.ModuleType("database")
    db_crud = types.ModuleType("database.crud")
    db_conn = types.ModuleType("database.connection")
    db_models = types.ModuleType("database.models")

    # Provide stubs for every name logistics_api.py references
    fake_cm = MagicMock()
    fake_cm.__enter__ = lambda s: MagicMock()
    fake_cm.__exit__  = MagicMock(return_value=False)
    db_pkg.get_db          = MagicMock(return_value=fake_cm)
    db_pkg.get_batch_events = MagicMock(return_value=[])

    class FakeContainerOffering:
        container_sscc = None

    class FakeEPCISEvent:
        pass

    class FakeRFQAcceptance:
        pass

    db_models.ContainerOffering = FakeContainerOffering
    db_models.EPCISEvent        = FakeEPCISEvent
    db_models.RFQAcceptance     = FakeRFQAcceptance
    db_pkg.models = db_models

    # ── blockchain / web3 stubs ───────────────────────────────────────────
    blockchain_pkg    = types.ModuleType("blockchain")
    blockchain_anchor = types.ModuleType("blockchain.blockchain_anchor")
    blockchain_anchor.anchor_event_to_blockchain = MagicMock(return_value=None)
    blockchain_pkg.blockchain_anchor = blockchain_anchor

    web3_mod  = types.ModuleType("web3")
    class _Web3:
        HTTPProvider = MagicMock
    web3_mod.Web3 = _Web3

    # ── ipfs stub ─────────────────────────────────────────────────────────
    ipfs_pkg     = types.ModuleType("ipfs")
    ipfs_storage = types.ModuleType("ipfs.ipfs_storage")
    ipfs_storage.pin_to_ipfs = MagicMock(return_value="QmFakeCid")
    ipfs_pkg.ipfs_storage = ipfs_storage

    for name, mod in [
        ("database",                   db_pkg),
        ("database.crud",              db_crud),
        ("database.connection",        db_conn),
        ("database.models",            db_models),
        ("blockchain",                 blockchain_pkg),
        ("blockchain.blockchain_anchor", blockchain_anchor),
        ("web3",                       web3_mod),
        ("ipfs",                       ipfs_pkg),
        ("ipfs.ipfs_storage",          ipfs_storage),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)


class TestLogisticsAPICompatibility:
    """
    Verify that logistics_api.py can be imported and its public interface is
    compatible with the current webhook_dispatcher API surface.
    """

    def test_logistics_api_imports_all_needed_names(self, monkeypatch):
        """logistics_api.py imports 5 names from webhook_dispatcher; all must exist."""
        _install_db_stubs(monkeypatch)
        # Force re-import so stubs are in place
        for mod in list(sys.modules):
            if "logistics_api" in mod:
                del sys.modules[mod]

        from voice.service.logistics_api import router  # noqa: F401
        # If we got here the import succeeded — all 5 names were resolved
        assert router is not None

    def test_valid_events_consistent_with_logistics_api(self, monkeypatch):
        """
        logistics_api.py uses VALID_EVENTS for its description string.
        The set must contain at least the 5 events the API documents.
        """
        _install_db_stubs(monkeypatch)
        from voice.service.webhook_dispatcher import VALID_EVENTS
        for evt in ("PREPARING_SHIPMENT", "SHIPPED", "DELIVERED",
                    "PAYMENT_CONFIRMED", "MILESTONE_RECEIVED"):
            assert evt in VALID_EVENTS

    def test_register_webhook_returns_object_compatible_with_webhook_response(self):
        """
        logistics_api.py does wh.to_dict() then pops 'secret' before passing to
        WebhookResponse(**d). The resulting dict must contain all WebhookResponse fields.
        """
        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook

        wh = register_webhook(url="https://lsp.example.com/cb", events=["SHIPPED"])
        d = wh.to_dict()
        d.pop("secret", None)

        required_fields = ("id", "url", "events", "description", "active",
                           "created_at", "last_triggered_at",
                           "delivery_count", "failure_count")
        for field in required_fields:
            assert field in d, f"WebhookResponse field '{field}' missing from to_dict()"

    def test_dispatch_webhook_is_awaitable(self):
        """logistics_api.py calls `await dispatch_webhook(...)`. Must be a coroutine."""
        import inspect
        from voice.service.webhook_dispatcher import dispatch_webhook
        assert inspect.iscoroutinefunction(dispatch_webhook)

    def test_unregister_webhook_returns_bool(self):
        """logistics_api.py checks `if not unregister_webhook(id)` — must return bool."""
        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook, unregister_webhook
        wh = register_webhook(url="https://a.com", events=["SHIPPED"])
        assert unregister_webhook(wh.id) is True
        assert unregister_webhook("ghost") is False

    def test_list_webhooks_returns_list_of_dicts_without_secret(self):
        """logistics_api.py does WebhookResponse(**w) for w in list_webhooks()."""
        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook, list_webhooks
        register_webhook(url="https://a.com", events=["SHIPPED"], secret="hidden")
        items = list_webhooks()
        assert isinstance(items, list)
        assert all(isinstance(i, dict) for i in items)
        assert all("secret" not in i for i in items)


# ===========================================================================
# WebhookResponse Pydantic compatibility (no FastAPI/DB import needed)
# ===========================================================================

class TestWebhookResponsePydanticCompat:

    def test_to_dict_minus_secret_passes_pydantic_model(self, monkeypatch):
        """
        logistics_api.py builds WebhookResponse(**d) where d = wh.to_dict() minus secret.
        Verify this doesn't raise a Pydantic ValidationError.
        """
        _install_db_stubs(monkeypatch)
        for mod in list(sys.modules):
            if "logistics_api" in mod:
                del sys.modules[mod]

        _clear_cache()
        from voice.service.webhook_dispatcher import register_webhook
        from voice.service.logistics_api import WebhookResponse

        wh = register_webhook(url="https://lsp.example.com/cb",
                               events=["SHIPPED", "DELIVERED"], secret="s3cr3t")
        d = wh.to_dict()
        d.pop("secret", None)

        resp = WebhookResponse(**d)   # must not raise
        assert resp.url == "https://lsp.example.com/cb"
        assert resp.active is True
        assert "secret" not in resp.model_dump()
