"""
DPP & EUDR Compliance API Router

Exposes Digital Product Passport and EUDR compliance data on the main API
so that customs brokers and LSPs can access it without needing the
standalone DPP resolver service.

Endpoints:
  GET /api/dpp/batch/{batch_id}               - Full / summary / QR DPP
  GET /api/dpp/batch/{batch_id}/verify         - Blockchain verification status
  GET /api/dpp/container/{container_sscc}       - Container-level DPP with child batches
  GET /api/dpp/batches                         - List all batches with DPP links
  GET /api/eudr/compliance/{batch_id}          - Flat Article 9 fields for customs filing
  GET /api/eudr/container/{container_sscc}     - Container-level EUDR compliance package

Created: March 2026 (LSP & Customs Clearance Integration)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
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
    compliance_status: str  # FULLY_VERIFIED | FARM_VERIFIED | DEVICE_GPS | SELF_REPORTED | DEFORESTATION_RISK | NO_GPS
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

    # Derive real compliance values from farmer data instead of hardcoding
    deforestation_risk = "none"
    eudr_compliant = True
    if batch.farmer:
        f = batch.farmer
        risk = (f.deforestation_risk or "UNKNOWN").lower()
        deforestation_risk = risk if risk in ("low", "medium", "high", "unknown") else "none"
        eudr_compliant = (
            f.deforestation_compliant is True
            and f.latitude is not None
            and f.longitude is not None
        )

    try:
        dpp = build_dpp(batch_id=batch_id, deforestation_risk=deforestation_risk, eudr_compliant=eudr_compliant)
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
                "gpsVerified": eudr.get("complianceStatus") in ("FULLY_VERIFIED", "FARM_VERIFIED", "DEVICE_GPS"),
            },
            "qrUrl": dpp.get("qrCode", {}).get("url"),
        }

    if format == "qr":
        return {"batchId": dpp["batchId"], "qrCode": dpp.get("qrCode")}

    return dpp


@router.get("/api/dpp/batch/{batch_id}/pdf")
async def get_batch_dpp_pdf(batch_id: str):
    """
    Download the Digital Product Passport as a branded PDF.

    Returns a PDF file with all batch, compliance, traceability, and
    blockchain data rendered in a professional layout.
    """
    try:
        from dpp.dpp_pdf import build_and_render_pdf
        pdf_bytes = build_and_render_pdf(batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    except Exception as exc:
        logger.exception("Error generating PDF for %s", batch_id)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"DPP_{batch_id}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/passport/{batch_id}", response_class=HTMLResponse)
async def public_passport_page(batch_id: str):
    """
    Public shareable HTML page for a batch's Digital Product Passport.

    Designed to be the landing page when someone scans a QR code.  It
    renders a self-contained, mobile-friendly HTML document with all
    the key DPP data and a link to download the full PDF.
    """
    batch = load_batch_data(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    # Derive real compliance values
    deforestation_risk = "none"
    eudr_compliant = True
    if batch.farmer:
        f = batch.farmer
        risk = (f.deforestation_risk or "UNKNOWN").lower()
        deforestation_risk = risk if risk in ("low", "medium", "high", "unknown") else "none"
        eudr_compliant = (
            f.deforestation_compliant is True
            and f.latitude is not None
            and f.longitude is not None
        )

    try:
        dpp = build_dpp(batch_id=batch_id, deforestation_risk=deforestation_risk, eudr_compliant=eudr_compliant)
    except Exception as exc:
        logger.exception("Error building DPP for passport page %s", batch_id)
        raise HTTPException(status_code=500, detail=f"Error building DPP: {exc}")

    html = _render_passport_html(dpp)
    return HTMLResponse(content=html)


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

        # Build a DPP per child batch (derive real compliance values)
        for bid in child_batch_ids:
            try:
                child_batch = load_batch_data(bid)
                d_risk = "none"
                d_compliant = True
                if child_batch and child_batch.farmer:
                    f = child_batch.farmer
                    risk = (f.deforestation_risk or "UNKNOWN").lower()
                    d_risk = risk if risk in ("low", "medium", "high", "unknown") else "none"
                    d_compliant = (
                        f.deforestation_compliant is True
                        and f.latitude is not None
                        and f.longitude is not None
                    )
                dpp = build_dpp(batch_id=bid, deforestation_risk=d_risk, eudr_compliant=d_compliant)
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
# EUDR compliance endpoints - flat Article 9 fields for customs brokers
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
    statement templates - every field maps 1:1 to an Article 9 requirement.
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
                logger.warning("Skipping batch %s - not found", bid)

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


# ---------------------------------------------------------------------------
# HTML passport renderer (self-contained, mobile-friendly)
# ---------------------------------------------------------------------------

import html as _html


def _esc(val) -> str:
    """HTML-escape a value, returning 'N/A' for None."""
    if val is None:
        return "N/A"
    return _html.escape(str(val))


def _render_passport_html(dpp: Dict[str, Any]) -> str:
    """Return a self-contained HTML page for a DPP."""
    prod = dpp.get("productInformation", {})
    trace = dpp.get("traceability", {})
    origin = trace.get("origin", {})
    farmer = origin.get("farmer", {})
    eudr = dpp.get("eudrCompliance", {})
    dd = dpp.get("dueDiligence", {})
    bc = dpp.get("blockchain", {})
    qr = dpp.get("qrCode", {})
    don = dpp.get("donAttestation", {})
    risk = eudr.get("riskAssessment", {})
    geo = eudr.get("geolocation", {}).get("farmLocation", {})
    coords = geo.get("coordinates", {})

    batch_id = _esc(dpp.get("batchId"))
    comp_level = _esc(eudr.get("complianceLevel", "Unknown"))
    comp_status = _esc(eudr.get("complianceStatus", "UNKNOWN"))

    level_colors = {
        "Gold": "#DAA520", "Silver": "#C0C0C0",
        "Bronze": "#CD7F32", "Non-Compliant": "#DC3545",
    }
    badge_color = level_colors.get(eudr.get("complianceLevel", ""), "#6c757d")

    events_html = ""
    for ev in trace.get("events", [])[:15]:
        ts = (_esc(ev.get("timestamp")) or "")[:19].replace("T", " ")
        events_html += (
            f'<div class="ev">'
            f'<span class="ev-time">{ts}</span>'
            f'<span class="ev-type">{_esc(ev.get("eventType"))}</span>'
            f'<span class="ev-step">{_esc(ev.get("bizStep"))}</span>'
            f'</div>'
        )

    anchors_html = ""
    for a in bc.get("anchors", [])[:10]:
        tx = _esc(a.get("transactionHash", "pending"))
        anchors_html += f'<div class="anchor">{tx}</div>'

    don_html = ""
    if don and don.get("attestationExists"):
        don_html = f"""
        <div class="section">
            <h2>Chainlink DON Attestation</h2>
            <div class="row"><span class="lbl">Farm ID</span><span>{_esc(don.get('farmId'))}</span></div>
            <div class="row"><span class="lbl">Risk Level</span><span>{_esc(don.get('riskLabel'))}</span></div>
            <div class="row"><span class="lbl">EUDR Compliant</span><span>{_esc(don.get('eudrCompliant'))}</span></div>
            <div class="row"><span class="lbl">Tree Loss</span><span>{_esc(don.get('treeLossHectares'))} ha</span></div>
        </div>"""
    else:
        don_note = _esc((don or {}).get("note", "DON attestation pending"))
        don_html = f"""
        <div class="section">
            <h2>Chainlink DON Attestation</h2>
            <div class="row"><span class="lbl">Status</span><span>{don_note}</span></div>
        </div>"""

    qr_img = qr.get("imageUrl", "")
    qr_block = ""
    if qr_img:
        qr_block = f'<div class="qr"><img src="{qr_img}" alt="QR Code" width="160" height="160"></div>'

    # Quality assessment section
    qa = dpp.get("qualityAssessment", {})
    qa_status = qa.get("status", "PENDING_VERIFICATION")
    if qa_status == "ASSESSED":
        qa_rows = ""
        if qa.get("cuppingScore") is not None:
            qa_rows += f'<div class="row"><span class="lbl">Cupping Score (SCA)</span><span>{_esc(qa.get("cuppingScore"))}</span></div>'
        if qa.get("moisturePct") is not None:
            qa_rows += f'<div class="row"><span class="lbl">Moisture</span><span>{_esc(qa.get("moisturePct"))}%</span></div>'
        if qa.get("screenSize"):
            qa_rows += f'<div class="row"><span class="lbl">Screen Size</span><span>{_esc(qa.get("screenSize"))}</span></div>'
        if qa.get("defectCount") is not None:
            cat = _esc(qa.get("defectCategory") or "")
            qa_rows += f'<div class="row"><span class="lbl">Defects</span><span>{_esc(qa.get("defectCount"))} {cat}</span></div>'
        sensory = qa.get("sensoryNotes", {})
        for attr, val in (sensory or {}).items():
            qa_rows += f'<div class="row"><span class="lbl">{_esc(attr.title())}</span><span>{_esc(val)}</span></div>'
        if qa.get("assessedAt"):
            qa_rows += f'<div class="row"><span class="lbl">Assessed</span><span>{_esc(qa["assessedAt"][:19].replace("T", " "))}</span></div>'
        qa_html = f'<div class="section"><h2>Quality Assessment</h2>{qa_rows}</div>'
    else:
        qa_html = '<div class="section"><h2>Quality Assessment</h2><div class="row"><span class="lbl">Status</span><span>Pending cooperative verification</span></div></div>'

    dd_risk = dd.get("riskAssessment", {})
    defo_check = risk.get("deforestationCheck", {})
    defo_rows = ""
    if defo_check:
        defo_rows = f"""
            <div class="row"><span class="lbl">Tree Cover Loss</span><span>{_esc(defo_check.get('treeCoverLossHectares'))} ha</span></div>
            <div class="row"><span class="lbl">Compliant</span><span>{_esc(defo_check.get('compliant'))}</span></div>
            <div class="row"><span class="lbl">Data Source</span><span>{_esc(defo_check.get('dataSource'))}</span></div>
            <div class="row"><span class="lbl">Confidence</span><span>{_esc(defo_check.get('confidence'))}</span></div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DPP - {batch_id}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f4f6f5;color:#212529;padding:16px}}
.card{{max-width:640px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08);overflow:hidden}}
.hero{{background:linear-gradient(135deg,#228B22,#2E8B57);color:#fff;padding:24px;text-align:center}}
.hero h1{{font-size:1.4rem;margin-bottom:4px}}
.hero .batch{{font-size:.95rem;opacity:.9}}
.hero .meta{{font-size:.75rem;opacity:.7;margin-top:6px}}
.badge{{display:inline-block;padding:4px 14px;border-radius:20px;color:#fff;font-weight:700;font-size:.85rem;margin-top:8px;background:{badge_color}}}
.section{{padding:16px 24px;border-bottom:1px solid #eee}}
.section h2{{font-size:1rem;color:#228B22;margin-bottom:10px}}
.row{{display:flex;justify-content:space-between;padding:4px 0;font-size:.85rem}}
.row .lbl{{color:#6c757d;flex:0 0 45%}}
.ev{{display:flex;gap:8px;font-size:.8rem;padding:3px 0;border-bottom:1px solid #f0f0f0}}
.ev-time{{color:#6c757d;flex:0 0 130px}}
.ev-type{{font-weight:600}}
.ev-step{{color:#6c757d}}
.anchor{{font-size:.75rem;color:#6c757d;word-break:break-all;padding:2px 0}}
.qr{{text-align:center;padding:20px}}
.qr img{{border-radius:8px}}
.actions{{text-align:center;padding:16px}}
.actions a{{display:inline-block;padding:10px 24px;background:#228B22;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;font-size:.9rem}}
.actions a:hover{{background:#1a6e1a}}
.footer-note{{text-align:center;padding:12px 24px;font-size:.7rem;color:#aaa}}
</style>
</head>
<body>
<div class="card">
  <div class="hero">
    <h1>Digital Product Passport</h1>
    <div class="batch">{batch_id}</div>
    <div class="meta">Passport {_esc(dpp.get('passportId'))} &middot; v{_esc(dpp.get('version'))}</div>
    <div class="badge">{comp_level}</div>
  </div>

  <div class="section">
    <h2>Product Information</h2>
    <div class="row"><span class="lbl">Product</span><span>{_esc(prod.get('productName'))}</span></div>
    <div class="row"><span class="lbl">Variety</span><span>{_esc(prod.get('variety'))}</span></div>
    <div class="row"><span class="lbl">Processing</span><span>{_esc(prod.get('processMethod'))}</span></div>
    <div class="row"><span class="lbl">Quantity</span><span>{_esc(prod.get('quantity'))} {_esc(prod.get('unit'))}</span></div>
    <div class="row"><span class="lbl">GTIN</span><span>{_esc(prod.get('gtin'))}</span></div>
  </div>

  <div class="section">
    <h2>Traceability &amp; Origin</h2>
    <div class="row"><span class="lbl">Country</span><span>{_esc(origin.get('country'))}</span></div>
    <div class="row"><span class="lbl">Region</span><span>{_esc(origin.get('region'))}</span></div>
    <div class="row"><span class="lbl">Farm</span><span>{_esc(origin.get('farmName'))}</span></div>
    <div class="row"><span class="lbl">Farmer</span><span>{_esc(farmer.get('name'))}</span></div>
    <div class="row"><span class="lbl">DID</span><span style="font-size:.75rem;word-break:break-all">{_esc(farmer.get('did'))}</span></div>
  </div>

  {qa_html}

  <div class="section">
    <h2>EUDR Compliance</h2>
    <div class="row"><span class="lbl">Status</span><span>{comp_status}</span></div>
    <div class="row"><span class="lbl">GPS Source</span><span>{_esc(geo.get('source', geo.get('status', 'N/A')))}</span></div>
    {"<div class='row'><span class='lbl'>Latitude</span><span>" + _esc(coords.get('latitude')) + "</span></div>" if coords else ""}
    {"<div class='row'><span class='lbl'>Longitude</span><span>" + _esc(coords.get('longitude')) + "</span></div>" if coords else ""}
    <div class="row"><span class="lbl">Deforestation Risk</span><span>{_esc(risk.get('deforestationRisk'))}</span></div>
    {defo_rows}
  </div>

  {don_html}

  <div class="section">
    <h2>Due Diligence</h2>
    <div class="row"><span class="lbl">EUDR Compliant</span><span>{_esc(dd.get('eudrCompliant'))}</span></div>
    <div class="row"><span class="lbl">Risk</span><span>{_esc(dd_risk.get('deforestationRisk'))}</span></div>
    <div class="row"><span class="lbl">Methodology</span><span>{_esc(dd_risk.get('methodology'))}</span></div>
  </div>

  {"<div class='section'><h2>Supply Chain Events</h2>" + events_html + "</div>" if events_html else ""}

  {"<div class='section'><h2>Blockchain Anchors</h2>" + anchors_html + "</div>" if anchors_html else ""}

  {qr_block}

  <div class="actions">
    <a href="/api/dpp/batch/{batch_id}/pdf">Download PDF</a>
  </div>

  <div class="footer-note">
    Generated by Voice Ledger &middot; Data sourced from on-chain records, GPS-verified farm locations,
    and satellite deforestation analysis (Global Forest Watch).
  </div>
</div>
</body>
</html>"""
