"""
Webhook Dispatcher

Manages webhook registrations and dispatches events to registered URLs.
Used by:
  - Customs brokers: subscribe to PREPARING_SHIPMENT to auto-pull DPP
  - LSPs: subscribe to PREPARING_SHIPMENT to initiate booking
  - Any external system: subscribe to delivery_status transitions

Webhook registrations are persisted in Redis so they survive Railway redeploys.
Falls back to in-memory dict when Redis is unavailable (e.g. local dev without Redis).

Created: March 2026 (LSP & Customs Clearance Integration)

Design notes
============
Storage
  Redis: r.set(key, json_str) + a set index (NOT hset with mapping=json_str).
  Full to_dict / from_dict round-trip preserves all fields including secret,
  counters, and timestamps across restarts.

Secret encryption
  Webhook HMAC secrets are encrypted with Fernet before being written to Redis,
  using the same APP_SECRET_KEY / APP_ENCRYPTION_KEY that protects DID private keys.
  This keeps secrets at rest in Redis protected even if Redis access is compromised.
  Secrets are NEVER logged.

Caching
  _webhooks_cache is an in-process dict that acts as the single source of truth
  for dispatch — no Redis round-trip per event.  It is updated synchronously on
  every register / unregister call.  warm_cache() pre-loads it at startup.

Multi-instance sync
  _publish_update() broadcasts register/unregister events on the Redis pub/sub
  channel "vl:webhooks:updates".  _start_subscriber() (call from FastAPI startup)
  listens on that channel in a daemon thread and applies changes to _webhooks_cache
  on each instance, keeping all replicas in sync without polling.

Redis client
  Module-level singleton with connection-pool reuse.  Reconnects automatically
  after connection loss.

httpx client
  Module-level AsyncClient is created once and reused for all deliveries.
  close_httpx_client() must be awaited in the FastAPI shutdown handler.

In-flight task tracking
  _delivery_tasks keeps a WeakSet of running delivery tasks.
  await_in_flight() drains them gracefully during shutdown.

URL validation
  HTTPS-only in production.  http://localhost allowed when ENVIRONMENT != production.

Atomicity
  delete + srem are issued in a Redis pipeline so the index never contains stale ids.
  Delivery / failure counters use HINCRBY for atomic increments; the canonical JSON
  blob (used for full reload) is updated after each change.
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
# Redis key constants
# ---------------------------------------------------------------------------

_REDIS_KEY_PREFIX   = "vl:webhooks:"          # <prefix><id>  →  json blob
_REDIS_INDEX_KEY    = "vl:webhooks:index"      # Redis SET of all IDs
_REDIS_COUNTS_KEY   = "vl:webhooks:counts"     # Redis HASH  id -> "delivery:failure"
_REDIS_PUBSUB_CHAN  = "vl:webhooks:updates"    # pub/sub channel

# ---------------------------------------------------------------------------
# Redis singleton
# ---------------------------------------------------------------------------

_redis_client: Optional[Any] = None   # module-level cached client


def _get_redis() -> Optional[Any]:
    """
    Return the cached Redis client, or None if Redis is unavailable.
    Reconnects automatically after a connection loss.
    """
    global _redis_client

    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None   # reset — will reconnect below

    try:
        import redis as redis_lib
        client = redis_lib.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Secret encryption (Fernet, same key used for DID private keys)
# ---------------------------------------------------------------------------

def _get_fernet():
    """
    Return a Fernet instance keyed from APP_SECRET_KEY / APP_ENCRYPTION_KEY.
    Returns None if the cryptography package is unavailable.
    """
    try:
        from cryptography.fernet import Fernet
        secret = (
            os.getenv("APP_ENCRYPTION_KEY")
            or os.getenv("APP_SECRET_KEY", "voice-ledger-default-secret-change-in-production")
        )
        key_bytes = hashlib.sha256(secret.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except ImportError:
        return None


def _encrypt_secret(plaintext: str) -> str:
    """Encrypt a webhook secret before persisting. Returns base64 Fernet token."""
    f = _get_fernet()
    if f is None:
        return plaintext   # fall back to plaintext if cryptography not installed
    return f.encrypt(plaintext.encode()).decode()


def _decrypt_secret(token: str) -> str:
    """Decrypt a persisted webhook secret token. Falls back to treating it as plaintext."""
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        # Could be a legacy plaintext value stored before encryption was added
        return token


# ---------------------------------------------------------------------------
# In-process webhook cache  (_webhooks is an alias kept for test compatibility)
# ---------------------------------------------------------------------------

_webhooks_cache: Dict[str, "WebhookRegistration"] = {}
_webhooks        = _webhooks_cache   # tests call `_webhooks.clear()` directly

_cache_loaded    = False             # populated at most once per process start
_cache_lock      = threading.Lock()  # guards initial load to avoid races


def _ensure_cache_loaded() -> None:
    """Populate _webhooks_cache from the backing store on first use."""
    global _cache_loaded
    if _cache_loaded:
        return
    with _cache_lock:
        if _cache_loaded:   # double-checked
            return
        _webhooks_cache.update(_load_webhooks_from_store())
        _cache_loaded = True


# ---------------------------------------------------------------------------
# In-memory fallback (used when Redis is unavailable)
# ---------------------------------------------------------------------------

_webhooks_memory: Dict[str, "WebhookRegistration"] = {}


# ---------------------------------------------------------------------------
# WebhookRegistration
# ---------------------------------------------------------------------------

class WebhookRegistration:
    """A single registered webhook endpoint."""

    def __init__(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.id             = uuid4().hex          # 32-char hex; negligible collision risk
        self.url            = url
        self.events         = events
        self.secret         = secret               # HMAC-SHA256 signing key (optional)
        self.description    = description
        self.created_at     = datetime.now(timezone.utc)
        self.last_triggered_at: Optional[datetime] = None
        self.delivery_count = 0
        self.failure_count  = 0
        self.active         = True

    # ── Serialisation ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Full round-trip serialisation.
        Secret is included (encrypted at rest by _save_webhook).
        Callers that expose this over HTTP must strip 'secret' themselves.
        """
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
        """Reconstruct a WebhookRegistration from a dict produced by to_dict()."""
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
# Low-level persistence  (r.set / r.get, NOT hset with mapping=json_str)
# ---------------------------------------------------------------------------

def _save_webhook(wh: "WebhookRegistration") -> None:
    """
    Persist a webhook to Redis using r.set(key, json_str) and an index set.
    The secret field is encrypted before storage.
    Falls back to in-memory if Redis is unavailable.
    """
    raw = wh.to_dict()
    if raw.get("secret"):
        raw = {**raw, "secret": _encrypt_secret(raw["secret"])}

    data = json.dumps(raw)
    r = _get_redis()
    if r:
        try:
            r.set(f"{_REDIS_KEY_PREFIX}{wh.id}", data)
            r.sadd(_REDIS_INDEX_KEY, wh.id)
            return
        except Exception as e:
            logger.warning("Redis webhook save failed, using in-memory: %s", e)
    _webhooks_memory[wh.id] = wh


def _load_webhooks_from_store() -> Dict[str, "WebhookRegistration"]:
    """
    Load all webhooks from Redis (or in-memory fallback).
    Secrets are decrypted on load.  Called once per process to seed the cache.
    """
    r = _get_redis()
    if r:
        try:
            ids = r.smembers(_REDIS_INDEX_KEY) or set()
            result: Dict[str, "WebhookRegistration"] = {}
            for wid in ids:
                raw = r.get(f"{_REDIS_KEY_PREFIX}{wid}")
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    if data.get("secret"):
                        data["secret"] = _decrypt_secret(data["secret"])
                    wh = WebhookRegistration.from_dict(data)
                    result[wh.id] = wh
                except Exception as parse_err:
                    logger.warning("Skipping corrupt webhook entry %s: %s", wid, parse_err)
            return result
        except Exception as e:
            logger.warning("Redis webhook load failed, using in-memory: %s", e)
    return dict(_webhooks_memory)


def _delete_webhook(webhook_id: str) -> None:
    """
    Remove a webhook from Redis atomically (pipeline delete + srem) so the
    index never retains stale IDs.  Also removes from in-memory fallback.
    """
    r = _get_redis()
    if r:
        try:
            pipe = r.pipeline()
            pipe.delete(f"{_REDIS_KEY_PREFIX}{webhook_id}")
            pipe.srem(_REDIS_INDEX_KEY, webhook_id)
            pipe.execute()
            return
        except Exception as e:
            logger.warning("Redis webhook delete failed, using in-memory: %s", e)
    _webhooks_memory.pop(webhook_id, None)


# ---------------------------------------------------------------------------
# Redis pub/sub for multi-instance cache sync
# ---------------------------------------------------------------------------

def _publish_update(action: str, payload: Dict[str, Any]) -> None:
    """
    Broadcast a register/unregister event so all process instances can update
    their local _webhooks_cache without polling Redis.
    Secrets are stripped from the published payload (secrets live only in Redis).
    """
    r = _get_redis()
    if not r:
        return
    try:
        pub_payload = {**payload}
        pub_payload.pop("secret", None)         # never publish secrets over pub/sub
        r.publish(_REDIS_PUBSUB_CHAN, json.dumps({"action": action, "payload": pub_payload}))
    except Exception:
        pass   # pub/sub is best-effort; cache sync is advisory


def _start_subscriber() -> None:
    """
    Start a daemon thread that subscribes to _REDIS_PUBSUB_CHAN and applies
    register/unregister messages to _webhooks_cache.

    Call this once from the FastAPI startup event (alongside warm_cache).
    No-ops if Redis is unavailable.
    """
    r = _get_redis()
    if not r:
        return

    def _run() -> None:
        try:
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(_REDIS_PUBSUB_CHAN)
            for msg in pubsub.listen():
                try:
                    data    = json.loads(msg["data"])
                    action  = data.get("action")
                    payload = data.get("payload", {})

                    if action == "register":
                        # Fetch the full record (with secret) from Redis rather than
                        # trusting the pub/sub payload (which has secret stripped).
                        wid = payload.get("id")
                        if wid:
                            raw = r.get(f"{_REDIS_KEY_PREFIX}{wid}")
                            if raw:
                                rec = json.loads(raw)
                                if rec.get("secret"):
                                    rec["secret"] = _decrypt_secret(rec["secret"])
                                wh = WebhookRegistration.from_dict(rec)
                                _webhooks_cache[wh.id] = wh

                    elif action == "unregister":
                        _webhooks_cache.pop(payload.get("id", ""), None)

                except Exception:
                    logger.exception("Error processing webhook pub/sub message")
        except Exception:
            logger.exception("Webhook pub/sub subscriber exited unexpectedly")

    thread = threading.Thread(target=_run, daemon=True, name="webhook-pubsub-subscriber")
    thread.start()
    logger.info("Webhook pub/sub subscriber started")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def _validate_url(url: str) -> None:
    """
    Enforce HTTPS-only webhook URLs.
    http://localhost is permitted when ENVIRONMENT is not 'production'.
    """
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
# Registration helpers  (keep cache in sync on every mutation)
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
    """Register a new webhook endpoint."""
    _validate_url(url)

    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        raise ValueError(
            f"Invalid event type(s): {invalid}. Valid: {sorted(VALID_EVENTS)}"
        )

    _ensure_cache_loaded()

    wh = WebhookRegistration(url=url, events=events, secret=secret, description=description)
    _save_webhook(wh)
    _webhooks_cache[wh.id] = wh

    _publish_update("register", wh.to_dict())
    logger.info("Registered webhook %s → %s events=%s", wh.id, url, events)
    return wh


def unregister_webhook(webhook_id: str) -> bool:
    """Remove a webhook registration. Returns True if it existed."""
    _ensure_cache_loaded()

    if webhook_id not in _webhooks_cache:
        return False

    _delete_webhook(webhook_id)
    _webhooks_cache.pop(webhook_id, None)

    _publish_update("unregister", {"id": webhook_id})
    logger.info("Unregistered webhook %s", webhook_id)
    return True


def list_webhooks() -> List[Dict[str, Any]]:
    """Return all registered webhooks. Secrets are never included in the output."""
    _ensure_cache_loaded()
    result = []
    for wh in _webhooks_cache.values():
        d = wh.to_dict()
        d.pop("secret", None)   # never expose secrets over HTTP
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# httpx client singleton  (reuse connection pool across all deliveries)
# ---------------------------------------------------------------------------

_httpx_client: Optional[httpx.AsyncClient] = None


def _get_httpx_client() -> httpx.AsyncClient:
    """
    Return the shared AsyncClient, creating it on first use or after it has
    been closed (e.g. after a previous asyncio.run() call tore down a loop).
    """
    global _httpx_client
    if _httpx_client is None or _httpx_client.is_closed:
        _httpx_client = httpx.AsyncClient(timeout=10.0)
    return _httpx_client


async def close_httpx_client() -> None:
    """
    Close the shared httpx client.
    Await this in the FastAPI shutdown handler to release connections cleanly.
    """
    global _httpx_client
    if _httpx_client and not _httpx_client.is_closed:
        await _httpx_client.aclose()
        _httpx_client = None


# ---------------------------------------------------------------------------
# In-flight task tracking for graceful shutdown
# ---------------------------------------------------------------------------

_delivery_tasks: "weakref.WeakSet[asyncio.Task]" = weakref.WeakSet()


async def await_in_flight(timeout: float = 30.0) -> None:
    """
    Wait for all in-flight delivery tasks to complete (or until timeout).
    Await this in the FastAPI shutdown handler before close_httpx_client().
    """
    tasks = list(_delivery_tasks)
    if not tasks:
        return
    logger.info("Waiting for %d in-flight webhook deliveries…", len(tasks))
    await asyncio.wait(tasks, timeout=timeout)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _on_delivery_done(task: "asyncio.Task") -> None:
    """Callback to log unexpected exceptions from delivery tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Webhook delivery task raised an unhandled exception: %s", exc)


async def _deliver(wh: WebhookRegistration, payload: Dict[str, Any]) -> None:
    """
    Deliver a single webhook with exponential back-off retry.

    Uses the shared httpx client for connection-pool reuse.
    Persists updated delivery_count / failure_count to Redis after each outcome.
    Secrets are NEVER logged.
    """
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
                logger.info(
                    "Webhook %s delivered to %s (HTTP %s)",
                    wh.id, wh.url, resp.status_code,
                )
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
            await asyncio.sleep(2 ** attempt)   # 1 s, 2 s before attempts 2 and 3

    # All retries exhausted
    wh.failure_count += 1
    _save_webhook(wh)
    logger.error("Webhook %s permanently failed delivery to %s", wh.id, wh.url)


async def dispatch_webhook(event_type: str, payload: Dict[str, Any]) -> int:
    """
    Dispatch an event to all active, subscribed webhooks.

    Reads from _webhooks_cache — no Redis deserialization per call.
    Delivery tasks run in the background (fire-and-forget) and are tracked in
    _delivery_tasks for graceful shutdown.

    Args:
        event_type: One of VALID_EVENTS (e.g. "MILESTONE_RECEIVED")
        payload:    Arbitrary dict; "event" and "timestamp" are injected automatically.

    Returns:
        Number of webhooks targeted (tasks launched, not delivery confirmations).
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
    """
    Synchronous wrapper for use in non-async contexts (e.g. ToolRegistry handlers).

    If an event loop is already running (FastAPI request), schedules the dispatch
    as a background task and returns -1 (count is unknowable synchronously).
    Otherwise creates a temporary event loop, dispatches, drains all delivery
    tasks, then closes the httpx client so it is not reused across loop instances.
    """
    try:
        loop = asyncio.get_running_loop()
        # Inside an async context (FastAPI) — schedule as background task
        loop.create_task(dispatch_webhook(event_type, payload))
        return -1
    except RuntimeError:
        # No running loop — create one, dispatch, drain tasks, clean up client.
        async def _run_and_drain():
            # Always use a fresh client for this isolated loop
            global _httpx_client
            _httpx_client = httpx.AsyncClient(timeout=10.0)
            try:
                count = await dispatch_webhook(event_type, payload)
                # Drain delivery tasks (fire-and-forget tasks live here)
                tasks = list(_delivery_tasks)
                if tasks:
                    await asyncio.wait(tasks, timeout=15.0)
                return count
            finally:
                # Close client before loop tears down to avoid ResourceWarning
                if _httpx_client and not _httpx_client.is_closed:
                    await _httpx_client.aclose()
                _httpx_client = None

        return asyncio.run(_run_and_drain())


# ---------------------------------------------------------------------------
# Startup / shutdown helpers  (call from FastAPI lifespan)
# ---------------------------------------------------------------------------

def warm_cache() -> int:
    """
    Pre-load webhook registrations from Redis into the in-process cache.
    Call this from the FastAPI startup event so the first dispatch has zero
    cold-start cost.  Returns the number of webhooks loaded.
    """
    global _cache_loaded
    with _cache_lock:
        _cache_loaded = False
        _webhooks_cache.clear()
        loaded = _load_webhooks_from_store()
        _webhooks_cache.update(loaded)
        _cache_loaded = True
    logger.info("Webhook cache warmed: %d registrations loaded", len(loaded))
    return len(loaded)
