"""
DPP & EUDR Compliance API Router

Exposes Digital Product Passport and EUDR compliance data on the main API
so that customs brokers and LSPs can access it without needing the
standalone DPP resolver service.

Endpoints:
  GET /api/dpp/batch/{batch_id}               — Full / summary / QR DPP
  GET /api/dpp/batch/{batch_id}/verify         — Blockchain verification status
  GET /api/dpp/container/{container_sscc}       — Container-level DPP with child batches
  GET /api/dpp/batches                         — List all batches with DPP links
  GET /api/eudr/compliance/{batch_id}          — Flat Article 9 fields for customs filing
  GET /api/eudr/container/{container_sscc}     — Container-level EUDR compliance package

Created: March 2026 (LSP & Customs Clearance Integration)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_db, get_all_batches, get_batch_by_batch_id, get_batch_events
from dpp.dpp_builder import build_dpp, build_eudr_compliance_section, load_batch_data, validate_dpp

logger = logging.getLogger(__name__)

router = APIRouter(tags=["DPP & EUDR Compliance"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class EUDRArticle9(BaseModel):
    """Flat structure matching EUDR Article 9 due diligence statement fields."""
    batch_id: str
    commodity_description: str
    quantity_kg: float
    country_of_production: str
    region_of_production: Optional[str] = None
    geolocation_latitude: Optional[float] = None
    geolocation_longitude: Optional[float] = None
    geolocation_source: Optional[str] = None
    geolocation_verified_at: Optional[str] = None
    geolocation_proof_photo_hash: Optional[str] = None
    geolocation_proof_ipfs_cid: Optional[str] = None
    geolocation_proof_blockchain_tx: Optional[str] = None
    date_of_production: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_did: Optional[str] = None
    cooperative_name: Optional[str] = None
    deforestation_risk: Optional[str] = None
    deforestation_compliant: Optional[bool] = None
    deforestation_confidence: Optional[float] = None
    deforestation_data_source: Optional[str] = None
    compliance_status: str  # FULLY_VERIFIED | FARM_VERIFIED | SELF_REPORTED | NO_GPS
    compliance_level: str   # Gold | Silver | Bronze | Non-Compliant
    gtin: Optional[str] = None
    blockchain_event_count: int = 0
    dpp_url: Optional[str] = None


class ContainerEUDR(BaseModel):
    """Container-level EUDR compliance for all child batches."""
    container_sscc: str
    total_quantity_kg: float
    batch_count: int
    overall_compliance_level: str
    batches: List[EUDRArticle9]


# ---------------------------------------------------------------------------
# DPP endpoints
# ---------------------------------------------------------------------------

@router.get("/api/dpp/batch/{batch_id}")
async def get_batch_dpp(
    batch_id: str,
    format: str = Query("full", description="Response format: full, summary, qr"),
) -> Dict[str, Any]:
    """
    Retrieve the Digital Product Passport for a single batch.

    This endpoint wraps the DPP builder and returns the same data that the
    standalone DPP resolver serves, but on the main API for easier
    integration by customs brokers and LSPs.
    """
    batch = load_batch_data(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    try:
        dpp = build_dpp(batch_id=batch_id, deforestation_risk="none", eudr_compliant=True)
    except Exception as exc:
        logger.exception("Error building DPP for %s", batch_id)
        raise HTTPException(status_code=500, detail=f"Error building DPP: {exc}")

    is_valid, errors = validate_dpp(dpp)
    if not is_valid:
        raise HTTPException(status_code=500, detail=f"DPP validation failed: {', '.join(errors)}")

    if format == "summary":
        eudr = dpp.get("eudrCompliance", {})
        return {
            "passportId": dpp["passportId"],
            "batchId": dpp["batchId"],
            "product": dpp["productInformation"]["productName"],
            "quantity": f"{dpp['productInformation']['quantity']} {dpp['productInformation']['unit']}",
            "origin": f"{dpp['traceability']['origin']['region']}, {dpp['traceability']['origin']['country']}",
            "farmer": dpp["traceability"]["origin"]["farmer"]["name"],
            "gtin": dpp["productInformation"]["gtin"],
            "eudrCompliant": dpp["dueDiligence"]["eudrCompliant"],
            "deforestationRisk": dpp["dueDiligence"]["riskAssessment"]["deforestationRisk"],
            "eudrVerification": {
                "status": eudr.get("complianceStatus", "UNKNOWN"),
                "level": eudr.get("complianceLevel", "Unknown"),
                "gpsVerified": eudr.get("complianceStatus") in ("FULLY_VERIFIED", "FARM_VERIFIED"),
            },
            "qrUrl": dpp.get("qrCode", {}).get("url"),
        }

    if format == "qr":
        return {"batchId": dpp["batchId"], "qrCode": dpp.get("qrCode")}

    return dpp


@router.get("/api/dpp/batch/{batch_id}/verify")
async def verify_batch_dpp(batch_id: str) -> Dict[str, Any]:
    """
    Verify the blockchain anchoring and credential status for a batch.
    """
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

        events = get_batch_events(db, batch_id)
        anchored_events = [e for e in events if e.blockchain_tx_hash]

        credentials = batch.farmer.credentials
        verified_credentials = [c for c in credentials if not c.revoked]

        has_anchors = len(anchored_events) > 0
        has_credentials = len(verified_credentials) > 0
        verification_status = "verified" if (has_anchors and has_credentials) else "partial"

        return {
            "batchId": batch_id,
            "verificationStatus": verification_status,
            "blockchain": {
                "anchored": has_anchors,
                "anchoredEvents": len(anchored_events),
                "totalEvents": len(events),
            },
            "credentials": {
                "verified": has_credentials,
                "totalCredentials": len(verified_credentials),
                "types": [c.credential_type for c in verified_credentials],
            },
            "batch": {
                "gtin": batch.gtin,
                "quantity": f"{batch.quantity_kg} kg",
                "farmer": batch.farmer.name,
            },
        }


@router.get("/api/dpp/container/{container_sscc}")
async def get_container_dpp(container_sscc: str) -> Dict[str, Any]:
    """
    Retrieve an aggregated DPP for a container (identified by SSCC).

    Looks up the container offering, finds all child batches via the
    aggregation relationship, and builds a combined DPP.
    """
    from database.models import ContainerOffering, AggregationRelationship

    with get_db() as db:
        # Find the container offering by SSCC
        offering = (
            db.query(ContainerOffering)
            .filter(ContainerOffering.container_sscc == container_sscc)
            .first()
        )
        if not offering:
            raise HTTPException(status_code=404, detail=f"Container {container_sscc} not found")

        # Gather child batch IDs from aggregation relationships
        child_dpps: List[Dict[str, Any]] = []
        child_batch_ids: List[str] = []

        # Each child is a separate AggregationRelationship row sharing the same parent_sscc
        agg_rows = (
            db.query(AggregationRelationship)
            .filter(
                AggregationRelationship.parent_sscc == container_sscc,
                AggregationRelationship.is_active == True,
            )
            .all()
        )
        child_batch_ids = [row.child_identifier for row in agg_rows]

        # Build a DPP per child batch
        for bid in child_batch_ids:
            try:
                dpp = build_dpp(batch_id=bid, deforestation_risk="none", eudr_compliant=True)
                child_dpps.append(dpp)
            except Exception:
                logger.warning("Could not build DPP for child batch %s", bid)

        return {
            "containerSSCC": container_sscc,
            "totalQuantityKg": offering.total_quantity_kg,
            "variety": offering.variety,
            "processingMethod": offering.processing_method,
            "grade": offering.grade,
            "certifications": offering.certifications,
            "status": offering.status,
            "dppUrl": offering.dpp_url,
            "deliveryLocation": offering.delivery_location,
            "childBatchCount": len(child_dpps),
            "childBatches": child_dpps,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/api/dpp/batches")
async def list_batches() -> Dict[str, Any]:
    """List all batches with summary info and DPP links."""
    with get_db() as db:
        batches = get_all_batches(db)
        batch_list = []
        for batch in batches:
            batch_list.append(
                {
                    "batchId": batch.batch_id,
                    "gtin": batch.gtin,
                    "quantity": batch.quantity_kg,
                    "unit": "kg",
                    "tokenId": batch.token_id,
                    "farmer": batch.farmer.name,
                    "origin": batch.origin_region,
                    "events": len(batch.events),
                    "credentials": len(batch.farmer.credentials),
                    "dppUrl": f"/api/dpp/batch/{batch.batch_id}",
                }
            )
        return {"total": len(batch_list), "batches": batch_list}


# ---------------------------------------------------------------------------
# EUDR compliance endpoints — flat Article 9 fields for customs brokers
# ---------------------------------------------------------------------------

def _build_article9(batch_id: str) -> EUDRArticle9:
    """Build a flat Article 9 record from database data."""
    batch = load_batch_data(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    with get_db() as db:
        db_batch = get_batch_by_batch_id(db, batch_id)
        if not db_batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found in database")

        # Build the EUDR section via the existing builder
        eudr_section = build_eudr_compliance_section(db_batch, db)

        # Extract flat coordinates from the nested EUDR structure
        geo = eudr_section.get("geolocation", {}).get("farmLocation", {})
        coords = geo.get("coordinates", {})
        proof = geo.get("proof", {})

        # Risk assessment
        risk = eudr_section.get("riskAssessment", {})

        # Production date from commission event
        events = get_batch_events(db, batch_id)
        commission_events = [e for e in events if e.biz_step and "commission" in e.biz_step.lower()]
        production_date = None
        if commission_events:
            production_date = commission_events[0].event_time.isoformat() if commission_events[0].event_time else None

        return EUDRArticle9(
            batch_id=batch_id,
            commodity_description=f"{db_batch.variety or 'Coffee'} - {db_batch.process_method or 'Unknown'}",
            quantity_kg=db_batch.quantity_kg or 0,
            country_of_production=db_batch.origin_country or db_batch.farmer.country_code or "ET",
            region_of_production=db_batch.origin_region,
            geolocation_latitude=coords.get("latitude"),
            geolocation_longitude=coords.get("longitude"),
            geolocation_source=geo.get("source"),
            geolocation_verified_at=geo.get("verifiedAt"),
            geolocation_proof_photo_hash=proof.get("photoHash"),
            geolocation_proof_ipfs_cid=proof.get("ipfsCID"),
            geolocation_proof_blockchain_tx=proof.get("blockchainTx"),
            date_of_production=production_date,
            supplier_name=db_batch.farmer.name if db_batch.farmer else None,
            supplier_did=db_batch.farmer.did if db_batch.farmer else None,
            cooperative_name=db_batch.farm_name,
            deforestation_risk=risk.get("deforestationRisk"),
            deforestation_compliant=risk.get("compliant"),
            deforestation_confidence=risk.get("confidence"),
            deforestation_data_source=risk.get("dataSource"),
            compliance_status=eudr_section.get("complianceStatus", "UNKNOWN"),
            compliance_level=eudr_section.get("complianceLevel", "Unknown"),
            gtin=db_batch.gtin,
            blockchain_event_count=len([e for e in events if e.blockchain_tx_hash]),
            dpp_url=f"/api/dpp/batch/{batch_id}",
        )


@router.get("/api/eudr/compliance/{batch_id}", response_model=EUDRArticle9)
async def get_eudr_compliance(batch_id: str) -> EUDRArticle9:
    """
    Return flattened EUDR Article 9 fields for a single batch.

    Designed for customs brokers to pull directly into their due diligence
    statement templates — every field maps 1:1 to an Article 9 requirement.
    """
    return _build_article9(batch_id)


@router.get("/api/eudr/container/{container_sscc}", response_model=ContainerEUDR)
async def get_container_eudr(container_sscc: str) -> ContainerEUDR:
    """
    Return EUDR compliance data for an entire container (all child batches).

    The overall compliance level is the *lowest* level among child batches
    (weakest-link principle): if any batch is Non-Compliant, the container
    is Non-Compliant for customs purposes.
    """
    from database.models import ContainerOffering, AggregationRelationship

    with get_db() as db:
        offering = (
            db.query(ContainerOffering)
            .filter(ContainerOffering.container_sscc == container_sscc)
            .first()
        )
        if not offering:
            raise HTTPException(status_code=404, detail=f"Container {container_sscc} not found")

        # Each child is a separate AggregationRelationship row sharing the same parent_sscc
        agg_rows = (
            db.query(AggregationRelationship)
            .filter(
                AggregationRelationship.parent_sscc == container_sscc,
                AggregationRelationship.is_active == True,
            )
            .all()
        )
        child_batch_ids: List[str] = [row.child_identifier for row in agg_rows]

        # Build Article 9 for each child batch
        batch_records: List[EUDRArticle9] = []
        for bid in child_batch_ids:
            try:
                batch_records.append(_build_article9(bid))
            except HTTPException:
                logger.warning("Skipping batch %s — not found", bid)

        # Determine overall compliance level (weakest link)
        level_order = {"Non-Compliant": 0, "Bronze": 1, "Silver": 2, "Gold": 3}
        worst_level = "Gold"
        for rec in batch_records:
            if level_order.get(rec.compliance_level, 0) < level_order.get(worst_level, 3):
                worst_level = rec.compliance_level

        return ContainerEUDR(
            container_sscc=container_sscc,
            total_quantity_kg=offering.total_quantity_kg or 0,
            batch_count=len(batch_records),
            overall_compliance_level=worst_level if batch_records else "Unknown",
            batches=batch_records,
        )
