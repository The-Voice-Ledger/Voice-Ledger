"""
Container Pool API Router

Provides REST endpoints for the shared container buying model:
  - Browse pools with fill-progress
  - Commit a fractional quantity into a pool
  - View buyer's own commitments
  - Auto-create pools per region when buyers commit

Phase 4.6 - Shared Container Buying
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import SessionLocal
from database.models import (
    ContainerPool, BuyerCommitment, ContainerOffering,
    UserIdentity, Organization, Buyer, REGION_PORT_MAP,
    POOL_AUTO_CONFIRM_PCT,
)

logger = logging.getLogger(__name__)

# Database dependency for FastAPI
def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api", tags=["container-pools"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PoolSummary(BaseModel):
    id: int
    container_offering_id: int
    container_sscc: Optional[str] = None
    cooperative_name: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None
    processing_method: Optional[str] = None
    price_per_kg: float = 0
    currency: str = "USD"
    destination_region: str
    destination_port: str
    fill_target_kg: float
    filled_kg: float
    fill_pct: float = 0
    remaining_kg: float = 0
    buyer_count: int = 0
    status: str
    deadline: Optional[str] = None
    created_at: Optional[str] = None


class CommitRequest(BaseModel):
    container_offering_id: int = Field(..., description="Which container to buy from")
    quantity_kg: float = Field(..., gt=0, description="Kilograms to commit")
    delivery_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 code")
    delivery_city: Optional[str] = None
    delivery_address: Optional[str] = None


class CommitResponse(BaseModel):
    commitment_id: int
    pool_id: int
    destination_region: str
    destination_port: str
    quantity_kg: float
    unit_price: float
    total_amount: float
    pool_fill_pct: float
    pool_status: str
    message: str


class MyCommitment(BaseModel):
    id: int
    pool_id: int
    container_sscc: Optional[str] = None
    cooperative_name: Optional[str] = None
    variety: Optional[str] = None
    destination_region: str
    destination_port: str
    quantity_kg: float
    unit_price: float
    total_amount: float
    currency: str = "USD"
    status: str
    pool_fill_pct: float = 0
    pool_status: str = "FILLING"
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_region(country_code: Optional[str]):
    """Map a country code to (port, region) or fallback to generic."""
    if country_code and country_code.upper() in REGION_PORT_MAP:
        return REGION_PORT_MAP[country_code.upper()]
    # Fallback: allow buyers to be placed in a generic "International" pool
    return ("Djibouti", "International")


def _get_or_create_pool(
    db: Session,
    offering: ContainerOffering,
    region: str,
    port: str,
) -> ContainerPool:
    """Find an open FILLING pool for this offering+region, or create one."""
    pool = (
        db.query(ContainerPool)
        .filter(
            ContainerPool.container_offering_id == offering.id,
            ContainerPool.destination_region == region,
            ContainerPool.status == "FILLING",
        )
        .first()
    )
    if pool:
        return pool

    # Create a new pool with a 30-day default deadline
    pool = ContainerPool(
        container_offering_id=offering.id,
        destination_region=region,
        destination_port=port,
        fill_target_kg=offering.available_quantity_kg,
        filled_kg=0,
        status="FILLING",
        deadline=datetime.utcnow() + timedelta(days=30),
    )
    db.add(pool)
    db.flush()  # get pool.id before commit
    return pool


def _maybe_confirm_pool(pool: ContainerPool, db: Session):
    """Auto-confirm pool when it reaches the threshold."""
    if pool.status != "FILLING":
        return
    if pool.fill_pct >= POOL_AUTO_CONFIRM_PCT:
        pool.status = "CONFIRMED"
        pool.confirmed_at = datetime.utcnow()
        # Update all commitments to PAYMENT_PENDING
        for c in pool.commitments:
            if c.status == "COMMITTED":
                c.status = "PAYMENT_PENDING"
                c.updated_at = datetime.utcnow()
        logger.info(
            "Pool %s auto-confirmed at %.1f%% fill (%s, %s)",
            pool.id, pool.fill_pct, pool.destination_region, pool.destination_port,
        )


def _resolve_user_from_query(db: Session, user_id: Optional[int]):
    """
    Temporary auth helper (mirrors rfq_api pattern).
    Will be replaced by JWT middleware.
    """
    if not user_id:
        return None
    return db.query(UserIdentity).filter_by(id=user_id).first()


def _resolve_user_id_jwt_or_query(
    authorization: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve user_id from JWT Authorization header (preferred)
    or fall back to user_id query param (backward compat for Telegram/Twilio).
    """
    # Try JWT first
    if authorization and authorization.startswith("Bearer "):
        try:
            from voice.web.auth import verify_jwt_token
            payload = verify_jwt_token(authorization.replace("Bearer ", ""))
            return payload.get("user_id")
        except Exception:
            pass
    # Fallback to query param
    return user_id


def _pool_to_summary(pool: ContainerPool, db: Session) -> dict:
    """Serialize a pool to PoolSummary-compatible dict."""
    offering = pool.container_offering or db.query(ContainerOffering).get(pool.container_offering_id)
    coop = None
    if offering:
        coop = db.query(Organization).filter_by(id=offering.cooperative_id).first()

    return {
        "id": pool.id,
        "container_offering_id": pool.container_offering_id,
        "container_sscc": offering.container_sscc if offering else None,
        "cooperative_name": coop.name if coop else None,
        "variety": offering.variety if offering else None,
        "grade": offering.grade if offering else None,
        "processing_method": offering.processing_method if offering else None,
        "price_per_kg": offering.price_per_kg if offering else 0,
        "currency": offering.currency if offering else "USD",
        "destination_region": pool.destination_region,
        "destination_port": pool.destination_port,
        "fill_target_kg": pool.fill_target_kg,
        "filled_kg": pool.filled_kg,
        "fill_pct": pool.fill_pct,
        "remaining_kg": pool.remaining_kg,
        "buyer_count": pool.buyer_count,
        "status": pool.status,
        "deadline": pool.deadline.isoformat() if pool.deadline else None,
        "created_at": pool.created_at.isoformat() if pool.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/pools", response_model=List[PoolSummary])
def list_pools(
    status: Optional[str] = Query(None, description="Filter by status (FILLING, CONFIRMED, ...)"),
    region: Optional[str] = Query(None, description="Filter by destination region"),
    container_offering_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Browse container pools with fill-progress."""
    q = db.query(ContainerPool)

    if status:
        q = q.filter(ContainerPool.status == status.upper())
    else:
        # Default: show active pools
        q = q.filter(ContainerPool.status.in_(["FILLING", "CONFIRMED"]))

    if region:
        q = q.filter(ContainerPool.destination_region.ilike(f"%{region}%"))

    if container_offering_id:
        q = q.filter(ContainerPool.container_offering_id == container_offering_id)

    pools = q.order_by(ContainerPool.created_at.desc()).limit(50).all()

    return [_pool_to_summary(p, db) for p in pools]


@router.get("/pool/{pool_id}")
def get_pool_detail(pool_id: int, db: Session = Depends(get_db)):
    """Get detailed pool info including commitment breakdown."""
    pool = db.query(ContainerPool).filter_by(id=pool_id).first()
    if not pool:
        raise HTTPException(404, "Pool not found")

    summary = _pool_to_summary(pool, db)

    # Add commitment summaries (anonymised - no buyer names for public view)
    commitments_summary = []
    for c in pool.commitments:
        commitments_summary.append({
            "id": c.id,
            "quantity_kg": c.quantity_kg,
            "delivery_country": c.delivery_country,
            "delivery_city": c.delivery_city,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    summary["commitments"] = commitments_summary
    return summary


@router.post("/pool/commit", response_model=CommitResponse)
def commit_to_pool(
    body: CommitRequest,
    user_id: Optional[int] = Query(None, description="Buyer user ID (fallback for non-JWT clients)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Commit a fractional quantity to a container pool.

    Auth: JWT Authorization header (preferred) or user_id query param.
    Auto-creates a pool for the buyer's region if none exists.
    Auto-confirms the pool when fill threshold is reached.
    """
    resolved_id = _resolve_user_id_jwt_or_query(authorization, user_id)
    user = _resolve_user_from_query(db, resolved_id)
    if not user:
        raise HTTPException(401, "User not found. Please register first.")
    if user.role not in ("BUYER", "ADMIN"):
        raise HTTPException(403, f"Only buyers can commit. Your role is {user.role}.")

    # Validate offering
    offering = db.query(ContainerOffering).filter_by(id=body.container_offering_id).first()
    if not offering:
        raise HTTPException(404, "Container offering not found.")
    if offering.status not in ("AVAILABLE", "PARTIALLY_SOLD"):
        raise HTTPException(400, f"Container is not available (status: {offering.status}).")
    if body.quantity_kg > offering.available_quantity_kg:
        raise HTTPException(
            400,
            f"Insufficient quantity. Available: {offering.available_quantity_kg} kg, "
            f"requested: {body.quantity_kg} kg.",
        )

    # Resolve buyer's region
    country = body.delivery_country
    if not country:
        # Try to get from Buyer profile
        buyer_profile = db.query(Buyer).filter_by(organization_id=user.organization_id).first()
        if buyer_profile and buyer_profile.country:
            country = buyer_profile.country[:2].upper()

    port, region = _resolve_region(country)

    # Get or create pool
    pool = _get_or_create_pool(db, offering, region, port)

    # Clamp quantity to pool remaining capacity
    actual_qty = min(body.quantity_kg, pool.remaining_kg) if pool.remaining_kg > 0 else body.quantity_kg

    total_amount = round(actual_qty * offering.price_per_kg, 2)

    commitment = BuyerCommitment(
        pool_id=pool.id,
        buyer_id=user.id,
        organization_id=user.organization_id,
        quantity_kg=actual_qty,
        unit_price=offering.price_per_kg,
        total_amount=total_amount,
        currency=offering.currency or "USD",
        delivery_country=country,
        delivery_city=body.delivery_city,
        delivery_address=body.delivery_address,
        status="COMMITTED",
    )
    db.add(commitment)

    # Update pool fill
    pool.filled_kg += actual_qty
    pool.updated_at = datetime.utcnow()

    # Update offering availability
    offering.available_quantity_kg -= actual_qty
    offering.reserved_quantity_kg += actual_qty
    if offering.available_quantity_kg <= 0:
        offering.status = "FULLY_RESERVED"
    else:
        offering.status = "PARTIALLY_SOLD"
    offering.updated_at = datetime.utcnow()

    # Check auto-confirm
    _maybe_confirm_pool(pool, db)

    db.commit()
    db.refresh(commitment)
    db.refresh(pool)

    logger.info(
        "Buyer %s committed %s kg to pool %s (%s). Pool now %.1f%% full.",
        user.id, actual_qty, pool.id, pool.destination_region, pool.fill_pct,
    )

    status_msg = f"Committed {actual_qty} kg to the {region} pool (via {port})."
    if pool.status == "CONFIRMED":
        status_msg += " Pool is now confirmed for shipment! Payment instructions will follow."
    else:
        status_msg += f" Pool is {pool.fill_pct}% full ({pool.remaining_kg:.0f} kg to go)."

    return CommitResponse(
        commitment_id=commitment.id,
        pool_id=pool.id,
        destination_region=region,
        destination_port=port,
        quantity_kg=actual_qty,
        unit_price=offering.price_per_kg,
        total_amount=total_amount,
        pool_fill_pct=pool.fill_pct,
        pool_status=pool.status,
        message=status_msg,
    )


@router.get("/my/commitments", response_model=List[MyCommitment])
def list_my_commitments(
    user_id: Optional[int] = Query(None, description="Buyer user ID (fallback for non-JWT clients)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """List the authenticated buyer's commitments across all pools."""
    resolved_id = _resolve_user_id_jwt_or_query(authorization, user_id)
    if not resolved_id:
        raise HTTPException(401, "Authentication required.")
    commitments = (
        db.query(BuyerCommitment)
        .filter(BuyerCommitment.buyer_id == resolved_id)
        .order_by(BuyerCommitment.created_at.desc())
        .all()
    )

    result = []
    for c in commitments:
        pool = c.pool or db.query(ContainerPool).get(c.pool_id)
        offering = pool.container_offering if pool else None
        coop = None
        if offering:
            coop = db.query(Organization).filter_by(id=offering.cooperative_id).first()

        result.append(MyCommitment(
            id=c.id,
            pool_id=c.pool_id,
            container_sscc=offering.container_sscc if offering else None,
            cooperative_name=coop.name if coop else None,
            variety=offering.variety if offering else None,
            destination_region=pool.destination_region if pool else "",
            destination_port=pool.destination_port if pool else "",
            quantity_kg=c.quantity_kg,
            unit_price=c.unit_price,
            total_amount=c.total_amount,
            currency=c.currency,
            status=c.status,
            pool_fill_pct=pool.fill_pct if pool else 0,
            pool_status=pool.status if pool else "UNKNOWN",
            created_at=c.created_at.isoformat() if c.created_at else None,
        ))

    return result


@router.get("/my/rfqs")
def list_my_rfqs(
    user_id: Optional[int] = Query(None, description="Buyer user ID (fallback for non-JWT clients)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    List only the authenticated buyer's own RFQs.

    Unlike the public /api/rfqs endpoint, this returns private buyer data.
    """
    from database.models import RFQ, RFQOffer

    resolved_id = _resolve_user_id_jwt_or_query(authorization, user_id)
    user = _resolve_user_from_query(db, resolved_id)
    if not user:
        raise HTTPException(401, "User not found.")
    
    # Role-based access: Only BUYER role can access their RFQs
    if user.role not in ("BUYER", "ADMIN"):
        raise HTTPException(403, f"Access denied. Only buyers can view their RFQs. Your role is {user.role}.")

    rfqs = (
        db.query(RFQ)
        .filter(RFQ.buyer_id == user.id)
        .order_by(RFQ.created_at.desc())
        .limit(50)
        .all()
    )

    result = []
    for r in rfqs:
        offer_count = db.query(func.count(RFQOffer.id)).filter(RFQOffer.rfq_id == r.id).scalar()
        result.append({
            "id": r.id,
            "rfq_number": r.rfq_number,
            "quantity_kg": r.quantity_kg,
            "variety": r.variety,
            "processing_method": r.processing_method,
            "grade": r.grade,
            "delivery_location": r.delivery_location,
            "delivery_deadline": r.delivery_deadline.isoformat() if r.delivery_deadline else None,
            "status": r.status,
            "offer_count": offer_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        })

    return result


@router.get("/regions")
def list_regions():
    """Return the port-region mapping for the frontend country picker."""
    # De-duplicate into region → port + countries
    regions = {}
    for country, (port, region) in REGION_PORT_MAP.items():
        if region not in regions:
            regions[region] = {"port": port, "countries": []}
        regions[region]["countries"].append(country)

    return {
        "regions": [
            {"name": name, "port": data["port"], "countries": sorted(data["countries"])}
            for name, data in sorted(regions.items())
        ]
    }
