"""
Voice Ledger - Chainlink CRE Provenance API

Three endpoints that CRE DON nodes call to fetch supply-chain data.
Designed to be run from the project root:

    uvicorn chainlink.api.provenance_api:app --host 0.0.0.0 --port 8100

Endpoints:
    GET  /api/provenance              - aggregated supply chain metrics (Trigger 1)
    GET  /api/batch/{batch_id}        - single batch details (Trigger 2)
    GET  /api/deforestation/{farm_id} - deforestation check for farm (Trigger 3)

Author: Voice Ledger × Chainlink CRE
Date:   February 2026
"""

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so existing modules resolve correctly
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import SessionLocal
from database.models import FarmerIdentity, CoffeeBatch, EPCISEvent
from voice.verification.deforestation_checker import DeforestationChecker

# ---------------------------------------------------------------------------
# APIRouter (mountable into any FastAPI app - e.g. the main Railway service)
# ---------------------------------------------------------------------------
provenance_router = APIRouter(tags=["CRE Provenance"])

# ---------------------------------------------------------------------------
# Standalone FastAPI app (for local dev: uvicorn chainlink.api.provenance_api:app --port 8100)
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Voice Ledger - CRE Provenance API",
    description="Data endpoints consumed by Chainlink DON nodes for Proof of Provenance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_db():
    """Yield a database session, closing it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
# Trigger 1 - Proof of Provenance aggregate metrics
# ────────────────────────────────────────────────────────────────

@provenance_router.get("/api/provenance")
def get_provenance_metrics():
    """
    Aggregated supply chain metrics consumed by CRE CronTrigger.

    Every field is a plain number so that DON nodes can apply
    **median consensus** across independent fetches.
    """
    db = next(_get_db())
    try:
        # Farmer counts
        total_farmers = db.query(FarmerIdentity).count()
        compliant_farmers = (
            db.query(FarmerIdentity)
            .filter(FarmerIdentity.deforestation_compliant == True)  # noqa: E712
            .count()
        )

        # Batch counts
        batches = db.query(CoffeeBatch).all()
        total_batches = len(batches)
        total_quantity_kg = int(sum(b.quantity_kg or 0 for b in batches))
        verified_batches = sum(1 for b in batches if b.status == "VERIFIED")

        # Blockchain anchoring
        batches_anchored = (
            db.query(EPCISEvent)
            .filter(EPCISEvent.blockchain_confirmed == True)  # noqa: E712
            .count()
        )

        # EUDR compliance percentage (avoid division by zero)
        eudr_compliant_pct = 0
        if total_farmers > 0:
            eudr_compliant_pct = int(round(compliant_farmers / total_farmers * 100))

        return {
            "totalFarmers": total_farmers,
            "totalBatches": total_batches,
            "verifiedBatches": verified_batches,
            "totalQuantityKg": total_quantity_kg,
            "eudrCompliantPercent": eudr_compliant_pct,
            "batchesAnchored": batches_anchored,
            "lastUpdated": int(datetime.utcnow().timestamp()),
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
# Trigger 2 - Batch details (called after LogTrigger fires)
# ────────────────────────────────────────────────────────────────

@provenance_router.get("/api/batch/{batch_id}")
def get_batch_details(batch_id: str):
    """
    Return full batch details for a given batch_id.

    Called by CRE LogTrigger handler after an EventAnchored emission.
    """
    db = next(_get_db())
    try:
        batch: Optional[CoffeeBatch] = (
            db.query(CoffeeBatch)
            .filter(CoffeeBatch.batch_id == batch_id)
            .first()
        )
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

        # Hydrate farmer info if available
        farmer_info = None
        if batch.farmer_id:
            farmer = db.query(FarmerIdentity).filter(FarmerIdentity.id == batch.farmer_id).first()
            if farmer:
                farmer_info = {
                    "farmerId": farmer.farmer_id,
                    "name": farmer.name,
                    "location": farmer.location,
                    "region": farmer.region,
                    "latitude": farmer.latitude,
                    "longitude": farmer.longitude,
                    "deforestationRisk": farmer.deforestation_risk,
                    "eudrCompliant": farmer.deforestation_compliant,
                }

        # Batch events (anchored + IPFS)
        events = (
            db.query(EPCISEvent)
            .filter(EPCISEvent.batch_id == batch.id)
            .order_by(EPCISEvent.event_time)
            .all()
        )
        event_list = [
            {
                "eventHash": e.event_hash,
                "eventType": e.event_type,
                "bizStep": e.biz_step,
                "ipfsCid": e.ipfs_cid,
                "blockchainTxHash": e.blockchain_tx_hash,
                "blockchainConfirmed": e.blockchain_confirmed,
                "eventTime": e.event_time.isoformat() if e.event_time else None,
            }
            for e in events
        ]

        return {
            "batchId": batch.batch_id,
            "gtin": batch.gtin,
            "quantityKg": batch.quantity_kg,
            "origin": batch.origin,
            "originCountry": batch.origin_country,
            "originRegion": batch.origin_region,
            "variety": batch.variety,
            "qualityGrade": batch.quality_grade,
            "status": batch.status,
            # Flattened farmer fields for CRE consensus serialisation
            "farmerId": farmer_info["farmerId"] if farmer_info else "",
            "farmerName": farmer_info["name"] if farmer_info else "",
            "farmerLocation": farmer_info["location"] if farmer_info else "",
            "farmerEudrCompliant": farmer_info["eudrCompliant"] if farmer_info else False,
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
# Trigger 3 - Deforestation oracle (on-demand via HTTP trigger)
# ────────────────────────────────────────────────────────────────

@provenance_router.get("/api/deforestation/{farm_id}")
def get_deforestation_check(farm_id: str):
    """
    Run a GFW deforestation check for a registered farm.

    Looks up the farm's GPS coordinates in the database, then calls the
    existing DeforestationChecker module.  Returns a deterministic result
    so DON nodes can reach **identical consensus**.
    """
    db = next(_get_db())
    try:
        farmer = (
            db.query(FarmerIdentity)
            .filter(FarmerIdentity.farmer_id == farm_id)
            .first()
        )
        if not farmer:
            raise HTTPException(status_code=404, detail=f"Farm {farm_id} not found")

        if not farmer.latitude or not farmer.longitude:
            raise HTTPException(
                status_code=422,
                detail=f"Farm {farm_id} has no GPS coordinates registered",
            )

        # Call existing deforestation checker
        checker = DeforestationChecker()
        result = checker.check_deforestation(
            latitude=farmer.latitude,
            longitude=farmer.longitude,
            radius_meters=1000,
        )

        # Return deterministic payload (no floats that could differ across nodes)
        return {
            "farmId": farmer.farmer_id,
            "latitude": int(farmer.latitude * 1_000_000),   # scaled ×1e6
            "longitude": int(farmer.longitude * 1_000_000),  # scaled ×1e6
            "riskLevel": result.risk_level,                  # LOW | MEDIUM | HIGH
            "riskLevelCode": {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}.get(
                result.risk_level, 3
            ),
            "eudrCompliant": result.compliant,
            "treeLossHectaresScaled": int(result.tree_cover_loss_hectares * 10_000),  # ×1e4
            "confidenceScaled": int(result.confidence_score * 10_000),                # ×1e4
            "dataSource": result.data_source,
            "geostoreId": result.geostore_id or "",  # GFW geostore for DON spot-check
            "timestamp": int(datetime.utcnow().timestamp()),
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────
# Health check
# ────────────────────────────────────────────────────────────────

@provenance_router.get("/health")
def health():
    return {"status": "ok", "service": "voice-ledger-cre-api", "timestamp": int(datetime.utcnow().timestamp())}


# Mount the router into the standalone app (for local dev)
app.include_router(provenance_router)


# ────────────────────────────────────────────────────────────────
# Direct execution
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
