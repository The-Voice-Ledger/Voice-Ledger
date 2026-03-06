"""
Webhook Dispatcher

Manages webhook registrations and dispatches events to registered URLs.
Used by:
  - Customs brokers: subscribe to PREPARING_SHIPMENT to auto-pull DPP
  - LSPs: subscribe to PREPARING_SHIPMENT to initiate booking
  - Any external system: subscribe to delivery_status transitions

Webhook registrations are stored in-memory for now (suitable for a single
process deployment on Railway). Persisting to the database is a future
enhancement once partner volume justifies it.

Created: March 2026 (LSP & Customs Clearance Integration)
"""

import asyncio
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory webhook store
# ---------------------------------------------------------------------------

# {webhook_id: WebhookRegistration}
_webhooks: Dict[str, "WebhookRegistration"] = {}


class WebhookRegistration:
    """A single registered webhook endpoint."""

    def __init__(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.id = uuid4().hex[:12]
        self.url = url
        self.events = events  # e.g. ["PREPARING_SHIPMENT", "SHIPPED", "DELIVERED"]
        self.secret = secret  # HMAC-SHA256 signing key (optional)
        self.description = description
        self.created_at = datetime.now(timezone.utc)
        self.last_triggered_at: Optional[datetime] = None
        self.delivery_count = 0
        self.failure_count = 0
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "description": self.description,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "delivery_count": self.delivery_count,
            "failure_count": self.failure_count,
        }


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------

VALID_EVENTS = {
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
) -> WebhookRegistration:
    """Register a new webhook endpoint."""
    for evt in events:
        if evt not in VALID_EVENTS:
            raise ValueError(f"Invalid event type: {evt}. Valid types: {sorted(VALID_EVENTS)}")
    wh = WebhookRegistration(url=url, events=events, secret=secret, description=description)
    _webhooks[wh.id] = wh
    logger.info("Registered webhook %s → %s for %s", wh.id, url, events)
    return wh


def unregister_webhook(webhook_id: str) -> bool:
    """Remove a webhook registration. Returns True if found."""
    if webhook_id in _webhooks:
        del _webhooks[webhook_id]
        logger.info("Unregistered webhook %s", webhook_id)
        return True
    return False


def list_webhooks() -> List[Dict[str, Any]]:
    """Return all registered webhooks."""
    return [w.to_dict() for w in _webhooks.values()]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


async def _deliver(wh: WebhookRegistration, payload: Dict[str, Any]) -> None:
    """Deliver a single webhook with retry (fire-and-forget)."""
    import json

    body = json.dumps(payload, default=str).encode()

    headers = {
        "Content-Type": "application/json",
        "X-VoiceLedger-Event": payload.get("event", "unknown"),
        "X-VoiceLedger-Delivery": uuid4().hex,
        "X-VoiceLedger-Timestamp": str(int(time.time())),
    }
    if wh.secret:
        headers["X-VoiceLedger-Signature"] = f"sha256={_sign_payload(body, wh.secret)}"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(wh.url, content=body, headers=headers)
            if resp.status_code < 300:
                wh.delivery_count += 1
                wh.last_triggered_at = datetime.now(timezone.utc)
                logger.info("Webhook %s delivered to %s (status %s)", wh.id, wh.url, resp.status_code)
                return
            else:
                logger.warning(
                    "Webhook %s delivery to %s returned %s (attempt %d/%d)",
                    wh.id, wh.url, resp.status_code, attempt + 1, max_retries,
                )
        except Exception as exc:
            logger.warning(
                "Webhook %s delivery to %s failed: %s (attempt %d/%d)",
                wh.id, wh.url, exc, attempt + 1, max_retries,
            )
        # Exponential back-off: 1s, 2s, 4s
        await asyncio.sleep(2 ** attempt)

    wh.failure_count += 1
    logger.error("Webhook %s permanently failed delivery to %s", wh.id, wh.url)


async def dispatch_webhook(event_type: str, payload: Dict[str, Any]) -> int:
    """
    Dispatch a webhook event to all registered URLs that subscribe to it.

    Args:
        event_type: One of VALID_EVENTS (e.g. "PREPARING_SHIPMENT")
        payload: Arbitrary dict — will include {"event": event_type, ...}

    Returns:
        Number of webhooks that were dispatched to.
    """
    payload["event"] = event_type
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    targets = [wh for wh in _webhooks.values() if wh.active and event_type in wh.events]
    if not targets:
        return 0

    logger.info("Dispatching %s to %d webhook(s)", event_type, len(targets))

    # Fire all deliveries concurrently (non-blocking)
    tasks = [asyncio.create_task(_deliver(wh, payload)) for wh in targets]
    # Don't await — let them run in the background
    for t in tasks:
        t.add_done_callback(lambda _t: None)  # suppress unhandled exception warnings

    return len(targets)


def dispatch_webhook_sync(event_type: str, payload: Dict[str, Any]) -> int:
    """
    Synchronous wrapper around dispatch_webhook for use in non-async code.
    
    If an event loop is already running (e.g. inside FastAPI request),
    schedules the dispatch as a background task. Otherwise creates a new loop.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're inside an async context — schedule it
        loop.create_task(dispatch_webhook(event_type, payload))
        return -1  # can't know count synchronously
    except RuntimeError:
        # No running event loop — create one
        return asyncio.run(dispatch_webhook(event_type, payload))
