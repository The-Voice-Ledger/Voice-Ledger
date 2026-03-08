"""
Logistics & Webhook API Router

Provides endpoints for LSP integration and webhook management:

  POST /api/webhooks/register          — Register a webhook URL + subscribed events
  GET  /api/webhooks                   — List registered webhooks
  DELETE /api/webhooks/{webhook_id}    — Remove a webhook registration
  POST /api/logistics/milestone        — Ingest a tracking milestone from an LSP
  GET  /api/logistics/shipment/{sscc}  — Current shipment status + event timeline

Created: March 2026 (LSP & Customs Clearance Integration)
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_db, get_batch_events
from voice.service.webhook_dispatcher import (
    VALID_EVENTS,
    dispatch_webhook,
    list_webhooks,
    register_webhook,
    unregister_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Logistics & Webhooks"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class WebhookRegisterRequest(BaseModel):
    """Body for webhook registration."""
    url: str = Field(..., description="HTTPS endpoint that will receive POST payloads")
    events: List[str] = Field(
        ...,
        description=f"List of event types to subscribe to. Valid: {sorted(VALID_EVENTS)}",
    )
    secret: Optional[str] = Field(
        None,
        description="Optional HMAC-SHA256 secret for payload signing (X-VoiceLedger-Signature header)",
    )
    description: Optional[str] = Field(None, description="Human-readable label for this webhook")


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: List[str]
    description: Optional[str] = None
    active: bool
    created_at: str
    last_triggered_at: Optional[str] = None
    delivery_count: int
    failure_count: int


class MilestoneRequest(BaseModel):
    """
    An inbound tracking milestone from an LSP.

    Each milestone maps to an EPCIS event type and is recorded as a
    blockchain-anchored event in the batch/container's timeline.
    """
    container_sscc: str = Field(..., description="SSCC of the container this milestone applies to")
    milestone_type: str = Field(
        ...,
        description="One of: PICKUP, PORT_ARRIVAL_ORIGIN, VESSEL_DEPARTURE, "
                    "TRANSSHIPMENT, PORT_ARRIVAL_DESTINATION, CUSTOMS_CLEARED, DELIVERED",
    )
    location_gln: Optional[str] = Field(None, description="GS1 GLN of the milestone location")
    location_name: Optional[str] = Field(None, description="Human-readable location name")
    carrier: Optional[str] = Field(None, description="Carrier / shipping line name")
    vessel_imo: Optional[str] = Field(None, description="IMO number of the vessel")
    voyage_number: Optional[str] = Field(None, description="Voyage / trip reference")
    tracking_reference: Optional[str] = Field(None, description="Carrier tracking number / booking ref")
    timestamp: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp of the milestone (defaults to server time)",
    )
    notes: Optional[str] = Field(None, description="Free-text notes")


class MilestoneResponse(BaseModel):
    status: str
    milestone_type: str
    container_sscc: str
    epcis_event_hash: Optional[str] = None
    epcis_event_type: str
    blockchain_tx_hash: Optional[str] = None
    ipfs_cid: Optional[str] = None


class ShipmentStatusResponse(BaseModel):
    container_sscc: str
    delivery_status: Optional[str] = None
    total_quantity_kg: Optional[float] = None
    variety: Optional[str] = None
    events: List[Dict[str, Any]]
    milestones: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Milestone → EPCIS mapping
# ---------------------------------------------------------------------------

MILESTONE_EPCIS_MAP = {
    "PICKUP":                   ("ObjectEvent", "shipping",   "in_transit"),
    "PORT_ARRIVAL_ORIGIN":      ("ObjectEvent", "arriving",   "in_transit"),
    "VESSEL_DEPARTURE":         ("ObjectEvent", "shipping",   "in_transit"),
    "TRANSSHIPMENT":            ("ObjectEvent", "arriving",   "in_transit"),
    "PORT_ARRIVAL_DESTINATION": ("ObjectEvent", "arriving",   "in_progress"),
    "CUSTOMS_CLEARED":          ("ObjectEvent", "inspecting", "sellable_accessible"),
    "DELIVERED":                ("ObjectEvent", "receiving",  "in_progress"),
}


# ---------------------------------------------------------------------------
# Webhook management endpoints
# ---------------------------------------------------------------------------

@router.post("/api/webhooks/register", response_model=WebhookResponse)
async def register_webhook_endpoint(body: WebhookRegisterRequest):
    """
    Register a webhook URL to receive event notifications.

    Supported events:
    - PREPARING_SHIPMENT — container ready for logistics pickup
    - SHIPPED — container has departed origin
    - DELIVERED — container received at destination
    - PAYMENT_CONFIRMED — payment received and confirmed
    - MILESTONE_RECEIVED — an LSP milestone was ingested
    """
    try:
        wh = register_webhook(
            url=body.url,
            events=body.events,
            secret=body.secret,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return WebhookResponse(**wh.to_dict())


@router.get("/api/webhooks", response_model=List[WebhookResponse])
async def list_webhooks_endpoint():
    """List all registered webhooks."""
    return [WebhookResponse(**w) for w in list_webhooks()]


@router.delete("/api/webhooks/{webhook_id}")
async def delete_webhook_endpoint(webhook_id: str):
    """Remove a webhook registration."""
    if not unregister_webhook(webhook_id):
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")
    return {"status": "deleted", "id": webhook_id}


# ---------------------------------------------------------------------------
# LSP milestone ingestion
# ---------------------------------------------------------------------------

@router.post("/api/logistics/milestone", response_model=MilestoneResponse)
async def ingest_milestone(body: MilestoneRequest):
    """
    Receive a tracking milestone from an LSP and record it as a
    blockchain-anchored EPCIS event in the container's timeline.

    This is the inbound half of the bidirectional LSP integration.
    Each milestone becomes an immutable EPCIS event (Commission →
    Aggregation → Shipment → [milestones] → Receipt).
    """
    from database.models import ContainerOffering

    if body.milestone_type not in MILESTONE_EPCIS_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid milestone_type: {body.milestone_type}. "
                   f"Valid: {sorted(MILESTONE_EPCIS_MAP.keys())}",
        )

    event_type, biz_step, disposition = MILESTONE_EPCIS_MAP[body.milestone_type]

    # Resolve the container
    with get_db() as db:
        offering = (
            db.query(ContainerOffering)
            .filter(ContainerOffering.container_sscc == body.container_sscc)
            .first()
        )
        if not offering:
            raise HTTPException(status_code=404, detail=f"Container {body.container_sscc} not found")

        # Build EPCIS 2.0 event
        event_time = body.timestamp or datetime.now(timezone.utc).isoformat()
        location_id = (
            f"urn:epc:id:sgln:{body.location_gln}.0"
            if body.location_gln
            else f"urn:voiceledger:location:{body.location_name or 'unknown'}"
        )

        epcis_event = {
            "@context": [
                "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
            ],
            "type": event_type,
            "eventTime": event_time,
            "eventTimeZoneOffset": "+00:00",
            "action": "OBSERVE",
            "bizStep": f"urn:epcglobal:cbv:bizstep:{biz_step}",
            "disposition": f"urn:epcglobal:cbv:disp:{disposition}",
            "epcList": [f"urn:epc:id:sscc:{body.container_sscc}"],
            "readPoint": {"id": location_id},
            "bizLocation": {"id": location_id},
            "extension": {
                "milestoneType": body.milestone_type,
                "carrier": body.carrier,
                "vesselIMO": body.vessel_imo,
                "voyageNumber": body.voyage_number,
                "trackingReference": body.tracking_reference,
                "notes": body.notes,
                "source": "LSP_INTEGRATION",
            },
        }

        # Remove None extensions
        epcis_event["extension"] = {
            k: v for k, v in epcis_event["extension"].items() if v is not None
        }

        # Canonicalize and hash
        canonical = json.dumps(epcis_event, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(canonical.encode()).hexdigest()

        # Store as EPCIS event in database
        from database.crud import create_event

        db_event = create_event(
            db,
            event_data={
                "event_type": event_type,
                "event_json": epcis_event,
                "event_hash": event_hash,
                "event_time": datetime.fromisoformat(
                    event_time.replace("Z", "+00:00") if event_time.endswith("Z") else event_time
                ),
                "canonical_nquads": canonical,
                "biz_step": biz_step,
                "biz_location": location_id,
                "batch_id": None,  # container-level, not batch-level
                "submitter_id": None,
            },
            pin_to_ipfs=True,
            anchor_to_blockchain=True,
        )

        # Dispatch MILESTONE_RECEIVED webhook
        await dispatch_webhook(
            "MILESTONE_RECEIVED",
            {
                "container_sscc": body.container_sscc,
                "milestone_type": body.milestone_type,
                "event_hash": event_hash,
                "location": body.location_name or body.location_gln,
                "timestamp": event_time,
            },
        )

        logger.info(
            "Milestone %s ingested for container %s (hash=%s)",
            body.milestone_type, body.container_sscc, event_hash[:12],
        )

        return MilestoneResponse(
            status="recorded",
            milestone_type=body.milestone_type,
            container_sscc=body.container_sscc,
            epcis_event_hash=event_hash,
            epcis_event_type=event_type,
            blockchain_tx_hash=db_event.blockchain_tx_hash if db_event else None,
            ipfs_cid=db_event.ipfs_cid if db_event else None,
        )


# ---------------------------------------------------------------------------
# Shipment status / timeline
# ---------------------------------------------------------------------------

@router.get("/api/logistics/shipment/{container_sscc}", response_model=ShipmentStatusResponse)
async def get_shipment_status(container_sscc: str):
    """
    Return the current shipment status and full event timeline for a container.

    Combines marketplace delivery_status with all EPCIS events (including
    LSP-ingested milestones) to give a complete logistics picture.
    """
    from database.models import ContainerOffering, EPCISEvent, RFQAcceptance

    with get_db() as db:
        offering = (
            db.query(ContainerOffering)
            .filter(ContainerOffering.container_sscc == container_sscc)
            .first()
        )
        if not offering:
            raise HTTPException(status_code=404, detail=f"Container {container_sscc} not found")

        # Get the latest delivery status from acceptances linked to this offering
        acceptance = (
            db.query(RFQAcceptance)
            .filter(RFQAcceptance.container_offering_id == offering.id)
            .order_by(RFQAcceptance.created_at.desc())
            .first()
        )
        delivery_status = acceptance.delivery_status if acceptance else "PENDING"

        # Fetch all EPCIS events that reference this SSCC
        sscc_urn = f"urn:epc:id:sscc:{container_sscc}"
        from sqlalchemy import String
        epcis_events = (
            db.query(EPCISEvent)
            .filter(EPCISEvent.event_json.cast(String).contains(container_sscc))
            .order_by(EPCISEvent.event_time.asc())
            .all()
        )

        events_list = []
        milestones_list = []
        for evt in epcis_events:
            entry = {
                "event_type": evt.event_type,
                "biz_step": evt.biz_step,
                "event_time": evt.event_time.isoformat() if evt.event_time else None,
                "blockchain_tx_hash": evt.blockchain_tx_hash,
                "ipfs_cid": evt.ipfs_cid,
                "blockchain_confirmed": evt.blockchain_confirmed,
            }

            # Separate LSP milestones from native events
            event_json = evt.event_json if isinstance(evt.event_json, dict) else {}
            ext = event_json.get("extension", {})
            if ext.get("source") == "LSP_INTEGRATION":
                milestones_list.append({
                    **entry,
                    "milestone_type": ext.get("milestoneType"),
                    "carrier": ext.get("carrier"),
                    "vessel_imo": ext.get("vesselIMO"),
                    "tracking_reference": ext.get("trackingReference"),
                })
            else:
                events_list.append(entry)

        return ShipmentStatusResponse(
            container_sscc=container_sscc,
            delivery_status=delivery_status,
            total_quantity_kg=offering.total_quantity_kg,
            variety=offering.variety,
            events=events_list,
            milestones=milestones_list,
        )
