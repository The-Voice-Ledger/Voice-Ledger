"""
Webhook Dispatcher

Manages webhook registrations and dispatches events to registered URLs.
Used by:
  - Customs brokers: subscribe to PREPARING_SHIPMENT to auto-pull DPP
  - LSPs: subscribe to PREPARING_SHIPMENT to initiate booking
  - Any external system: subscribe to delivery_status transitions

Storage
  Webhook registrations are persisted to the PostgreSQL database
  (webhook_registrations table) so they survive restarts and Railway redeploys.
  Falls back to in-memory dict when the DB is unavailable.

Secret encryption
  HMAC secrets are encrypted with Fernet (same key as DID private keys)
  before being written to the database.  Secrets are NEVER logged.

Caching
  _webhooks_cache is an in-process dict — single source of truth for dispatch.
  Populated once at startup via warm_cache(), updated on every mutation.

httpx client
  Module-level AsyncClient reused across all deliveries.
  close_httpx_client() must be awaited in the FastAPI shutdown handler.

In-flight task tracking
  _delivery_tasks (WeakSet) tracks running delivery tasks.
  await_in_flight() drains them gracefully on shutdown.

URL validation
  HTTPS-only in production; http://localhost allowed when ENVIRONMENT != production.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import weakref
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Secret encryption (Fernet — same key as DID private keys)
# ---------------------------------------------------------------------------

def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        secret = (
            os.getenv("APP_ENCRYPTION_KEY")
            or os.getenv("APP_SECRET_KEY", "voice-ledger-default-secret-change-in-production")
        )
        key_bytes = hashlib.sha256(secret.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key_bytes))
    except ImportError:
        return None


def _encrypt_secret(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode() if f else plaintext


def _decrypt_secret(token: str) -> str:
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        return token   # legacy plaintext value


# ---------------------------------------------------------------------------
# In-process webhook cache  (_webhooks alias kept for test compatibility)
# ---------------------------------------------------------------------------

_webhooks_cache: Dict[str, "WebhookRegistration"] = {}
_webhooks        = _webhooks_cache   # tests call `_webhooks.clear()` directly

_cache_loaded    = False
_cache_lock      = threading.Lock()


def _ensure_cache_loaded() -> None:
    global _cache_loaded
    if _cache_loaded:
        return
    with _cache_lock:
        if _cache_loaded:
            return
        _webhooks_cache.update(_load_webhooks_from_db())
        _cache_loaded = True


# ---------------------------------------------------------------------------
# In-memory fallback (used when DB is unavailable)
# ---------------------------------------------------------------------------

_webhooks_memory: Dict[str, "WebhookRegistration"] = {}


# ---------------------------------------------------------------------------
# WebhookRegistration  (in-memory representation)
# ---------------------------------------------------------------------------

class WebhookRegistration:
    """A single registered webhook endpoint (in-memory)."""

    def __init__(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.id             = uuid4().hex
        self.url            = url
        self.events         = events
        self.secret         = secret
        self.description    = description
        self.created_at     = datetime.now(timezone.utc)
        self.last_triggered_at: Optional[datetime] = None
        self.delivery_count = 0
        self.failure_count  = 0
        self.active         = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":                self.id,
            "url":               self.url,
            "events":            self.events,
            "secret":            self.secret,
            "description":       self.description,
            "active":            self.active,
            "created_at":        self.created_at.isoformat(),
            "last_triggered_at": (
                self.last_triggered_at.isoformat() if self.last_triggered_at else None
            ),
            "delivery_count":    self.delivery_count,
            "failure_count":     self.failure_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebhookRegistration":
        wh = cls(
            url=data["url"],
            events=data["events"],
            secret=data.get("secret"),
            description=data.get("description"),
        )
        wh.id     = data["id"]
        wh.active = data.get("active", True)
        for attr, key in (("created_at", "created_at"), ("last_triggered_at", "last_triggered_at")):
            raw = data.get(key)
            if raw:
                try:
                    dt = datetime.fromisoformat(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    setattr(wh, attr, dt)
                except (ValueError, TypeError):
                    pass
        wh.delivery_count = int(data.get("delivery_count", 0))
        wh.failure_count  = int(data.get("failure_count", 0))
        return wh


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db_session():
    """Return a new SQLAlchemy session, or None if DB is unavailable."""
    try:
        from database.models import SessionLocal
        return SessionLocal()
    except Exception:
        return None


def _model_to_registration(row) -> "WebhookRegistration":
    """Convert a WebhookRegistrationModel ORM row → WebhookRegistration."""
    wh = WebhookRegistration.__new__(WebhookRegistration)
    wh.id          = row.id
    wh.url         = row.url
    wh.events      = row.events or []
    wh.secret      = _decrypt_secret(row.encrypted_secret) if row.encrypted_secret else None
    wh.description = row.description
    wh.active      = row.active
    wh.delivery_count = row.delivery_count or 0
    wh.failure_count  = row.failure_count  or 0

    def _parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(val))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    wh.created_at        = _parse_dt(row.created_at) or datetime.now(timezone.utc)
    wh.last_triggered_at = _parse_dt(row.last_triggered_at)
    return wh


def _save_webhook(wh: "WebhookRegistration") -> None:
    """
    Upsert a webhook to the database.
    Falls back to in-memory if the DB is unavailable.
    """
    db = _get_db_session()
    if db:
        try:
            from database.models import WebhookRegistrationModel
            row = db.query(WebhookRegistrationModel).filter_by(id=wh.id).first()
            enc_secret = _encrypt_secret(wh.secret) if wh.secret else None
            if row:
                row.url              = wh.url
                row.events           = wh.events
                row.encrypted_secret = enc_secret
                row.description      = wh.description
                row.active           = wh.active
                row.delivery_count   = wh.delivery_count
                row.failure_count    = wh.failure_count
                row.last_triggered_at = (
                    wh.last_triggered_at.replace(tzinfo=None)
                    if wh.last_triggered_at else None
                )
            else:
                row = WebhookRegistrationModel(
                    id               = wh.id,
                    url              = wh.url,
                    events           = wh.events,
                    encrypted_secret = enc_secret,
                    description      = wh.description,
                    active           = wh.active,
                    delivery_count   = wh.delivery_count,
                    failure_count    = wh.failure_count,
                    created_at       = wh.created_at.replace(tzinfo=None),
                    last_triggered_at = (
                        wh.last_triggered_at.replace(tzinfo=None)
                        if wh.last_triggered_at else None
                    ),
                )
                db.add(row)
            db.commit()
            return
        except Exception as e:
            logger.warning("DB webhook save failed, using in-memory: %s", e)
            db.rollback()
        finally:
            db.close()
    _webhooks_memory[wh.id] = wh


def _load_webhooks_from_db() -> Dict[str, "WebhookRegistration"]:
    """
    Load all active webhooks from the database (or in-memory fallback).
    Called once per process start to seed the cache.
    """
    db = _get_db_session()
    if db:
        try:
            from database.models import WebhookRegistrationModel
            rows = db.query(WebhookRegistrationModel).filter_by(active=True).all()
            result = {}
            for row in rows:
                try:
                    wh = _model_to_registration(row)
                    result[wh.id] = wh
                except Exception as e:
                    logger.warning("Skipping corrupt webhook row %s: %s", row.id, e)
            return result
        except Exception as e:
            logger.warning("DB webhook load failed, using in-memory: %s", e)
        finally:
            db.close()
    return dict(_webhooks_memory)


def _delete_webhook(webhook_id: str) -> None:
    """Hard-delete (or deactivate) a webhook from the database."""
    db = _get_db_session()
    if db:
        try:
            from database.models import WebhookRegistrationModel
            db.query(WebhookRegistrationModel).filter_by(id=webhook_id).delete()
            db.commit()
            return
        except Exception as e:
            logger.warning("DB webhook delete failed, using in-memory: %s", e)
            db.rollback()
        finally:
            db.close()
    _webhooks_memory.pop(webhook_id, None)


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    is_dev = os.getenv("ENVIRONMENT", "production").lower() not in ("production", "prod")
    if parsed.scheme == "https":
        return
    if is_dev and parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"):
        return
    raise ValueError(
        f"Webhook URL must use HTTPS (got '{parsed.scheme}://'). "
        "Provide a valid https:// endpoint."
    )


# ---------------------------------------------------------------------------
# Registration helpers  (keep cache in sync)
# ---------------------------------------------------------------------------

VALID_EVENTS: Set[str] = {
    "PREPARING_SHIPMENT",
    "SHIPPED",
    "DELIVERED",
    "PAYMENT_CONFIRMED",
    "MILESTONE_RECEIVED",
}


def register_webhook(
    url: str,
    events: List[str],
    secret: Optional[str] = None,
    description: Optional[str] = None,
) -> "WebhookRegistration":
    """Register a new webhook endpoint and persist it to the database."""
    _validate_url(url)
    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        raise ValueError(f"Invalid event type(s): {invalid}. Valid: {sorted(VALID_EVENTS)}")

    _ensure_cache_loaded()
    wh = WebhookRegistration(url=url, events=events, secret=secret, description=description)
    _save_webhook(wh)
    _webhooks_cache[wh.id] = wh
    logger.info("Registered webhook %s → %s events=%s", wh.id, url, events)
    return wh


def unregister_webhook(webhook_id: str) -> bool:
    """Remove a webhook registration. Returns True if it existed."""
    _ensure_cache_loaded()
    if webhook_id not in _webhooks_cache:
        return False
    _delete_webhook(webhook_id)
    _webhooks_cache.pop(webhook_id, None)
    logger.info("Unregistered webhook %s", webhook_id)
    return True


def list_webhooks() -> List[Dict[str, Any]]:
    """Return all registered webhooks. Secrets are never included."""
    _ensure_cache_loaded()
    result = []
    for wh in _webhooks_cache.values():
        d = wh.to_dict()
        d.pop("secret", None)
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# httpx client singleton
# ---------------------------------------------------------------------------

_httpx_client: Optional[httpx.AsyncClient] = None


def _get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None or _httpx_client.is_closed:
        _httpx_client = httpx.AsyncClient(timeout=10.0)
    return _httpx_client


async def close_httpx_client() -> None:
    global _httpx_client
    if _httpx_client and not _httpx_client.is_closed:
        await _httpx_client.aclose()
        _httpx_client = None


# ---------------------------------------------------------------------------
# In-flight task tracking
# ---------------------------------------------------------------------------

_delivery_tasks: "weakref.WeakSet[asyncio.Task]" = weakref.WeakSet()


async def await_in_flight(timeout: float = 30.0) -> None:
    tasks = list(_delivery_tasks)
    if not tasks:
        return
    logger.info("Waiting for %d in-flight webhook deliveries…", len(tasks))
    await asyncio.wait(tasks, timeout=timeout)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _on_delivery_done(task: "asyncio.Task") -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Webhook delivery task raised an unhandled exception: %s", exc)


async def _deliver(wh: WebhookRegistration, payload: Dict[str, Any]) -> None:
    """Deliver a single webhook with exponential back-off retry."""
    body = json.dumps(payload, default=str).encode()
    headers: Dict[str, str] = {
        "Content-Type":            "application/json",
        "X-VoiceLedger-Event":     payload.get("event", "unknown"),
        "X-VoiceLedger-Delivery":  uuid4().hex,
        "X-VoiceLedger-Timestamp": str(int(time.time())),
    }
    if wh.secret:
        headers["X-VoiceLedger-Signature"] = f"sha256={_sign_payload(body, wh.secret)}"

    client = _get_httpx_client()
    max_retries = 3

    for attempt in range(max_retries):
        try:
            resp = await client.post(wh.url, content=body, headers=headers)
            if resp.status_code < 300:
                wh.delivery_count += 1
                wh.last_triggered_at = datetime.now(timezone.utc)
                _save_webhook(wh)
                logger.info("Webhook %s delivered to %s (HTTP %s)", wh.id, wh.url, resp.status_code)
                return
            logger.warning(
                "Webhook %s → %s returned HTTP %s (attempt %d/%d)",
                wh.id, wh.url, resp.status_code, attempt + 1, max_retries,
            )
        except Exception as exc:
            logger.warning(
                "Webhook %s → %s raised %s (attempt %d/%d)",
                wh.id, wh.url, exc, attempt + 1, max_retries,
            )
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    wh.failure_count += 1
    _save_webhook(wh)
    logger.error("Webhook %s permanently failed delivery to %s", wh.id, wh.url)


async def dispatch_webhook(event_type: str, payload: Dict[str, Any]) -> int:
    """
    Dispatch an event to all active subscribed webhooks.
    Reads from _webhooks_cache — zero DB round-trips per dispatch.
    """
    _ensure_cache_loaded()
    full_payload = {
        **payload,
        "event":     event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    targets = [
        wh for wh in _webhooks_cache.values()
        if wh.active and event_type in wh.events
    ]
    if not targets:
        return 0

    logger.info("Dispatching %s to %d webhook(s)", event_type, len(targets))
    for wh in targets:
        task = asyncio.create_task(_deliver(wh, full_payload))
        _delivery_tasks.add(task)
        task.add_done_callback(_on_delivery_done)
    return len(targets)


def dispatch_webhook_sync(event_type: str, payload: Dict[str, Any]) -> int:
    """Synchronous wrapper for non-async contexts (e.g. ToolRegistry handlers)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(dispatch_webhook(event_type, payload))
        return -1
    except RuntimeError:
        async def _run_and_drain():
            global _httpx_client
            _httpx_client = httpx.AsyncClient(timeout=10.0)
            try:
                count = await dispatch_webhook(event_type, payload)
                tasks = list(_delivery_tasks)
                if tasks:
                    await asyncio.wait(tasks, timeout=15.0)
                return count
            finally:
                if _httpx_client and not _httpx_client.is_closed:
                    await _httpx_client.aclose()
                _httpx_client = None

        return asyncio.run(_run_and_drain())


# ---------------------------------------------------------------------------
# Startup / shutdown helpers  (call from FastAPI lifespan)
# ---------------------------------------------------------------------------

def warm_cache() -> int:
    """
    Pre-load webhook registrations from the DB into the in-process cache.
    Call from the FastAPI startup event.
    """
    global _cache_loaded
    with _cache_lock:
        _cache_loaded = False
        _webhooks_cache.clear()
        loaded = _load_webhooks_from_db()
        _webhooks_cache.update(loaded)
        _cache_loaded = True
    logger.info("Webhook cache warmed: %d registrations loaded", len(loaded))
    return len(loaded)


def _start_subscriber() -> None:
    """
    Multi-instance sync is now handled by the shared database — all instances
    call warm_cache() at startup and write directly to the DB on mutation.
    This function is kept for API compatibility with the FastAPI lifespan handler.
    """
    logger.info("Webhook store: PostgreSQL (no pub/sub subscriber needed)")
