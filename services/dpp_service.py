"""
DPP Service — shared business logic for Digital Product Passport operations.

Called by:
  - voice/agent/registry.py (Telegram / Mini App path)
  - voice/livekit_agent.py  (LiveKit web agent path)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_batch_cooperative(batch_id: str, db: Session) -> str:
    """Look up cooperative name from the batch's verifying org or creator's org."""
    try:
        from database.models import CoffeeBatch, UserIdentity, Organization

        batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        if not batch:
            return "Unknown Cooperative"
        if batch.verifying_organization_id:
            org = db.query(Organization).filter_by(id=batch.verifying_organization_id).first()
            if org:
                return org.name
        if batch.created_by_user_id:
            creator = db.query(UserIdentity).filter_by(id=batch.created_by_user_id).first()
            if creator and creator.organization_id:
                org = db.query(Organization).filter_by(id=creator.organization_id).first()
                if org:
                    return org.name
        return "Unknown Cooperative"
    except Exception as e:
        logger.debug("Could not resolve cooperative for %s: %s", batch_id, e)
        return "Unknown Cooperative"


def get_dpp(
    db: Session,
    *,
    batch_id: str,
) -> Dict[str, Any]:
    """
    Generate or retrieve the Digital Product Passport for a batch.

    Returns a structured dict with all DPP fields, suitable for both
    voice summary formatting and action card rendering.

    Returns:
        {
            "success": bool,
            "error": str | None,
            "batch_id": str,
            "passport_id": str,
            "product": { "name", "variety", "processing", "grade", "quantity_kg", "gtin" },
            "origin": { "region", "country", "farmer_name", "cooperative" },
            "compliance": { "eudr_compliant", "deforestation_risk", "latitude", "longitude" },
            "blockchain": { "anchored", "tx_hash" },
            "don_attestation": { "attested", "risk_label", "eudr_compliant" },
            "certifications": [...],
            "lineage": [...],
            "qr": { "url", "image_url" },
        }
    """
    if not batch_id:
        return {"success": False, "error": "no_batch_id", "batch_id": ""}

    try:
        from dpp.dpp_builder import build_dpp

        dpp = build_dpp(batch_id=batch_id)
    except ValueError as e:
        return {"success": False, "error": str(e), "batch_id": batch_id}
    except Exception as e:
        logger.warning("DPP generation failed for %s: %s", batch_id, e)
        return {"success": False, "error": str(e), "batch_id": batch_id}

    # Embed DON attestation if available
    try:
        from dpp.dpp_builder import build_don_attestation_section

        don_section = build_don_attestation_section(batch_id, db)
        if don_section and don_section.get("attestationExists"):
            dpp["donAttestation"] = don_section
    except Exception as e:
        logger.debug("DON attestation section skipped: %s", e)

    # Extract structured data from raw DPP
    product = dpp.get("productInformation", {})
    trace = dpp.get("traceability", {})
    origin = trace.get("origin", {})
    dd = dpp.get("dueDiligence", {})
    bc = dpp.get("blockchain", {})
    don = dpp.get("donAttestation", {})
    eudr = dpp.get("eudrCompliance", {})
    geo_coords = (
        eudr.get("geolocation", {})
        .get("farmLocation", {})
        .get("coordinates", {})
    )

    cooperative = dpp.get("cooperative") or _get_batch_cooperative(batch_id, db)

    return {
        "success": True,
        "error": None,
        "batch_id": dpp.get("batchId", batch_id),
        "passport_id": dpp.get("passportId"),
        "product": {
            "name": product.get("name", "Coffee"),
            "variety": product.get("variety", "Unknown"),
            "processing": product.get("processMethod"),
            "grade": product.get("grade", "A"),
            "quantity_kg": product.get("quantity"),
            "gtin": product.get("gtin"),
        },
        "origin": {
            "region": origin.get("region", "?"),
            "country": origin.get("country", "?"),
            "farmer_name": origin.get("farmer", {}).get("name"),
            "cooperative": cooperative,
        },
        "compliance": {
            "eudr_compliant": dd.get("eudrCompliant"),
            "deforestation_risk": dd.get("riskAssessment", {}).get("deforestationRisk"),
            "latitude": geo_coords.get("latitude"),
            "longitude": geo_coords.get("longitude"),
        },
        "blockchain": {
            "anchored": bool(bc.get("transactionHash") or (bc.get("anchors") and len(bc.get("anchors", [])) > 0)),
            "tx_hash": bc.get("transactionHash") or (
                bc.get("anchors", [{}])[0].get("transactionHash")
                if bc.get("anchors")
                else None
            ),
        },
        "don_attestation": {
            "attested": don.get("attestationExists", False),
            "risk_label": don.get("riskLabel"),
            "eudr_compliant": don.get("eudrCompliant"),
        },
        "certifications": [
            c.get("type")
            for c in dpp.get("sustainability", {}).get("certifications", [])
        ],
        "lineage": dpp.get("traceability", {}).get("events", []),
        "qr": {
            "url": dpp.get("qrCode", {}).get("url"),
            "image_url": dpp.get("qrCode", {}).get("imageUrl"),
        },
    }
