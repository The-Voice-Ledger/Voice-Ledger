"""
Mini App API endpoints for Voice Ledger.

Provides RESTful API for Telegram Mini Apps to query batch data.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from database import get_db
from database.models import (
    CoffeeBatch, EPCISEvent, UserIdentity, VerificationEvidence,
    RFQ, RFQOffer, RFQAcceptance, Organization,
    ContainerOffering, ContainerPool,
)
from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


def get_user_batches(db, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all coffee batches for a user with COMPLETE details.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        
    Returns:
        List of batch dictionaries with ALL relevant fields from CoffeeBatch model
    """
    try:
        # Get user identity
        user_identity = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user_identity:
            logger.warning(f"User identity not found for telegram_user_id: {user_id}")
            return []
        
        # Query batches created by this user
        batches = db.query(CoffeeBatch).filter(
            CoffeeBatch.created_by_user_id == user_identity.id
        ).order_by(CoffeeBatch.created_at.desc()).all()
        
        # Convert to dictionaries with ALL relevant fields from the model
        batch_list = []
        for batch in batches:
            # Determine display status
            display_status = 'pending'
            if batch.verified_at:
                display_status = 'verified'
            elif batch.status == 'REJECTED':
                display_status = 'rejected'
            
            # Check if shipped (has shipping events)
            shipping_events = db.query(EPCISEvent).filter(
                EPCISEvent.batch_id == batch.id,
                EPCISEvent.biz_step == 'shipping'
            ).first()
            if shipping_events:
                display_status = 'shipped'
            
            batch_dict = {
                # Core identifiers
                'id': batch.id,
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'gln': batch.gln,
                'batch_number': batch.batch_number,
                
                # Quantity and origin
                'quantity_kg': float(batch.quantity_kg) if batch.quantity_kg else 0,
                'origin': batch.origin,
                'origin_country': batch.origin_country,
                'origin_region': batch.origin_region,
                'farm_name': batch.farm_name,
                
                # Coffee attributes
                'variety': batch.variety,
                'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
                'processing_method': batch.processing_method,
                'process_method': batch.process_method,
                'quality_grade': batch.quality_grade,
                
                # Blockchain
                'token_id': batch.token_id,
                
                # Verification status
                'status': batch.status,
                'display_status': display_status,
                'verification_token': batch.verification_token,
                'verification_expires_at': batch.verification_expires_at.isoformat() if batch.verification_expires_at else None,
                'verification_used': batch.verification_used,
                'verified_quantity': float(batch.verified_quantity) if batch.verified_quantity else None,
                'verified_by_did': batch.verified_by_did,
                'verified_at': batch.verified_at.isoformat() if batch.verified_at else None,
                'verification_notes': batch.verification_notes,
                'has_photo_evidence': batch.has_photo_evidence,
                'verifying_organization_id': batch.verifying_organization_id,
                
                # Timestamps
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'updated_at': batch.updated_at.isoformat() if batch.updated_at else None,
                
                # Owner info
                'created_by_user_id': batch.created_by_user_id,
                'created_by_did': batch.created_by_did,
                'farmer_id': batch.farmer_id
            }
            
            batch_list.append(batch_dict)
        
        return batch_list
        
    except Exception as e:
        logger.error(f"Error getting user batches: {e}", exc_info=True)
        return []


def get_batch_details(db, batch_identifier: str, user_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific batch with ALL fields and related data.
    
    Args:
        db: Database session
        batch_identifier: GTIN or batch_id
        user_id: Telegram user ID (for authorization)
        
    Returns:
        Dictionary with complete batch details, EPCIS events, and relationships
    """
    try:
        # Get user identity
        user_identity = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user_identity:
            raise ValueError("User not found")
        
        # Find batch by GTIN or batch_id
        batch = db.query(CoffeeBatch).filter(
            (CoffeeBatch.gtin == batch_identifier) | 
            (CoffeeBatch.batch_id == batch_identifier)
        ).first()
        
        if not batch:
            raise ValueError(f"Batch not found: {batch_identifier}")
        
        # Check authorization (user must be creator)
        if batch.created_by_user_id != user_identity.id:
            raise ValueError("Unauthorized access to batch")
        
        # Get EPCIS events for this batch
        events = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id == batch.id
        ).order_by(EPCISEvent.event_time.asc()).all()
        
        # Get verification evidence (if table exists)
        try:
            evidence_items = db.query(VerificationEvidence).filter(
                VerificationEvidence.batch_id == batch.id
            ).all()
        except Exception as e:
            logger.warning(f"Could not load verification evidence: {e}")
            evidence_items = []
        
        # Determine display status
        display_status = 'pending'
        if batch.verified_at:
            display_status = 'verified'
        elif batch.status == 'REJECTED':
            display_status = 'rejected'
        
        if any(e.biz_step == 'shipping' for e in events):
            display_status = 'shipped'
        
        # Build complete response
        result = {
            'batch': {
                # Core identifiers
                'id': batch.id,
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'gln': batch.gln,
                'batch_number': batch.batch_number,
                
                # Quantity and origin
                'quantity_kg': float(batch.quantity_kg) if batch.quantity_kg else 0,
                'origin': batch.origin,
                'origin_country': batch.origin_country,
                'origin_region': batch.origin_region,
                'farm_name': batch.farm_name,
                
                # Coffee attributes
                'variety': batch.variety,
                'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
                'processing_method': batch.processing_method,
                'process_method': batch.process_method,
                'quality_grade': batch.quality_grade,
                
                # Blockchain
                'token_id': batch.token_id,
                
                # Verification status
                'status': batch.status,
                'display_status': display_status,
                'verification_token': batch.verification_token,
                'verification_expires_at': batch.verification_expires_at.isoformat() if batch.verification_expires_at else None,
                'verification_used': batch.verification_used,
                'verified_quantity': float(batch.verified_quantity) if batch.verified_quantity else None,
                'verified_by_did': batch.verified_by_did,
                'verified_at': batch.verified_at.isoformat() if batch.verified_at else None,
                'verification_notes': batch.verification_notes,
                'has_photo_evidence': batch.has_photo_evidence,
                'verifying_organization_id': batch.verifying_organization_id,
                
                # Timestamps
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'updated_at': batch.updated_at.isoformat() if batch.updated_at else None,
                
                # Owner info
                'created_by_user_id': batch.created_by_user_id,
                'created_by_did': batch.created_by_did,
                'farmer_id': batch.farmer_id
            },
            'events': [],
            'evidence': []
        }
        
        # Add EPCIS events
        for event in events:
            result['events'].append({
                'id': event.id,
                'event_hash': event.event_hash,
                'event_type': event.event_type,
                'event_time': event.event_time.isoformat() if event.event_time else None,
                'biz_step': event.biz_step,
                'biz_location': event.biz_location,
                'ipfs_cid': event.ipfs_cid,
                'blockchain_tx_hash': event.blockchain_tx_hash,
                'blockchain_confirmed': event.blockchain_confirmed,
                'blockchain_confirmed_at': event.blockchain_confirmed_at.isoformat() if event.blockchain_confirmed_at else None,
                'created_at': event.created_at.isoformat() if event.created_at else None
            })
        
        # Add verification evidence
        for item in evidence_items:
            result['evidence'].append({
                'id': item.id,
                'evidence_type': item.evidence_type,
                'content_hash': item.content_hash,
                'storage_url': item.storage_url,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting batch details: {e}", exc_info=True)
        raise


@router.get("/batches")
async def list_batches(
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get list of all batches for a user.
    
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batches array
    """
    try:
        with get_db() as db:
            batches = get_user_batches(db, user_id)
        
        return {
            "success": True,
            "batches": batches,
            "count": len(batches)
        }
        
    except Exception as e:
        logger.error(f"Error in list_batches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_identifier}")
async def get_batch(
    batch_identifier: str,
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get detailed information for a specific batch.
    
    Path Parameters:
        batch_identifier: GTIN or batch_id
        
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batch details and events
    """
    try:
        with get_db() as db:
            details = get_batch_details(db, batch_identifier, user_id)
        
        return {
            "success": True,
            **details
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{batch_identifier}")
async def trace_batch(
    batch_identifier: str,
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get traceability information for a specific batch (alias for get_batch).
    Used by the trace mini app for supply chain visualization.
    
    Path Parameters:
        batch_identifier: GTIN or batch_id
        
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batch details, EPCIS events timeline, and blockchain info
    """
    try:
        with get_db() as db:
            details = get_batch_details(db, batch_identifier, user_id)
        
        return {
            "success": True,
            **details
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in trace_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# MARKETPLACE API (for Telegram Mini Apps)
# ═══════════════════════════════════════════════════════════════

marketplace_router = APIRouter(prefix="/api/marketplace", tags=["miniapp-marketplace"])


def _get_user_by_telegram(db, telegram_user_id) -> Optional[UserIdentity]:
    """Look up user by Telegram ID (header value)."""
    if not telegram_user_id:
        return None
    return db.query(UserIdentity).filter(
        UserIdentity.telegram_user_id == str(telegram_user_id)
    ).first()


@marketplace_router.get("/rfqs")
async def marketplace_list_rfqs(
    status: Optional[str] = Query(None),
    x_telegram_user_id: Optional[str] = Header(None),
):
    """List open RFQs for the marketplace."""
    try:
        with get_db() as db:
            query = db.query(RFQ).options(
                joinedload(RFQ.buyer).joinedload(UserIdentity.organization),
                subqueryload(RFQ.offers)
            )
            if status:
                query = query.filter(RFQ.status == status)
            else:
                query = query.filter(RFQ.status.in_(['OPEN', 'ACTIVE']))

            rfqs = query.order_by(RFQ.created_at.desc()).limit(50).all()

            results = []
            for rfq in rfqs:
                buyer_name = ""
                if rfq.buyer:
                    buyer_name = f"{rfq.buyer.telegram_first_name or ''} {rfq.buyer.telegram_last_name or ''}".strip()
                    if rfq.buyer.organization:
                        buyer_name = rfq.buyer.organization.name

                results.append({
                    "id": rfq.id,
                    "rfq_number": rfq.rfq_number,
                    "title": f"{rfq.variety or 'Coffee'} - {rfq.quantity_kg} kg",
                    "coffee_type": rfq.variety or "Arabica",
                    "buyer_name": buyer_name,
                    "buyer": buyer_name,
                    "quantity": rfq.quantity_kg,
                    "target_price": None,
                    "grade": rfq.grade,
                    "processing_method": rfq.processing_method,
                    "delivery_location": rfq.delivery_location,
                    "deadline": rfq.delivery_deadline.isoformat() if rfq.delivery_deadline else None,
                    "status": rfq.status.lower(),
                    "offer_count": len(rfq.offers) if rfq.offers else 0,
                    "notes": rfq.transcript,
                    "created_at": rfq.created_at.isoformat() if rfq.created_at else None,
                })

            return {"rfqs": results, "count": len(results)}
    except Exception as e:
        logger.error(f"marketplace_list_rfqs error: {e}", exc_info=True)
        return {"rfqs": [], "count": 0}


@marketplace_router.get("/my-offers")
async def marketplace_my_offers(
    x_telegram_user_id: Optional[str] = Header(None),
):
    """List offers made by the current user's organization."""
    try:
        with get_db() as db:
            user = _get_user_by_telegram(db, x_telegram_user_id)
            if not user or not user.organization_id:
                return {"offers": [], "count": 0}

            offers = db.query(RFQOffer).filter(
                RFQOffer.cooperative_id == user.organization_id
            ).order_by(RFQOffer.created_at.desc()).limit(50).all()

            results = []
            for o in offers:
                rfq = db.query(RFQ).filter_by(id=o.rfq_id).first()
                results.append({
                    "id": o.id,
                    "offer_number": o.offer_number,
                    "rfq_id": o.rfq_id,
                    "rfq_title": f"{rfq.variety or 'Coffee'} - {rfq.quantity_kg} kg" if rfq else f"RFQ #{o.rfq_id}",
                    "price": float(o.price_per_kg) if o.price_per_kg else None,
                    "quantity": float(o.quantity_offered_kg) if o.quantity_offered_kg else None,
                    "status": (o.status or "pending").lower(),
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                })

            return {"offers": results, "count": len(results)}
    except Exception as e:
        logger.error(f"marketplace_my_offers error: {e}", exc_info=True)
        return {"offers": [], "count": 0}


class OfferCreate(BaseModel):
    rfq_id: int
    price: float
    quantity: Optional[float] = None
    notes: Optional[str] = None


@marketplace_router.post("/offers")
async def marketplace_submit_offer(
    body: OfferCreate,
    x_telegram_user_id: Optional[str] = Header(None),
):
    """Submit an offer on an RFQ."""
    try:
        with get_db() as db:
            user = _get_user_by_telegram(db, x_telegram_user_id)
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            rfq = db.query(RFQ).filter_by(id=body.rfq_id).first()
            if not rfq:
                raise HTTPException(status_code=404, detail="RFQ not found")

            # Generate offer number
            count = db.query(RFQOffer).count()
            offer_number = f"OFF-{count + 1:04d}"

            offer = RFQOffer(
                rfq_id=body.rfq_id,
                cooperative_id=user.organization_id or user.id,
                offer_number=offer_number,
                quantity_offered_kg=body.quantity or rfq.quantity_kg,
                price_per_kg=body.price,
                delivery_timeline=body.notes,
                status="PENDING",
            )
            db.add(offer)
            db.flush()

            return {
                "success": True,
                "offer_id": offer.id,
                "offer_number": offer_number,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"marketplace_submit_offer error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@marketplace_router.get("/my-containers")
async def marketplace_my_containers(
    x_telegram_user_id: Optional[str] = Header(None),
):
    """List containers + pool fill-progress for the current user's cooperative."""
    try:
        with get_db() as db:
            user = _get_user_by_telegram(db, x_telegram_user_id)
            if not user or not user.organization_id:
                return {"containers": [], "count": 0}

            offerings = (
                db.query(ContainerOffering)
                .filter(ContainerOffering.cooperative_id == user.organization_id)
                .order_by(ContainerOffering.created_at.desc())
                .limit(50)
                .all()
            )

            results = []
            for o in offerings:
                # Get pools for this offering
                pools = (
                    db.query(ContainerPool)
                    .filter(ContainerPool.container_offering_id == o.id)
                    .all()
                )
                total_committed = sum(p.filled_kg for p in pools)
                buyer_count = sum(p.buyer_count for p in pools)
                pool_regions = list({p.destination_region for p in pools})

                results.append({
                    "id": o.id,
                    "container_sscc": o.container_sscc,
                    "variety": o.variety,
                    "grade": o.grade,
                    "processing_method": o.processing_method,
                    "total_quantity_kg": o.total_quantity_kg,
                    "available_quantity_kg": o.available_quantity_kg,
                    "sold_quantity_kg": o.sold_quantity_kg,
                    "fill_percentage": o.fill_percentage,
                    "price_per_kg": o.price_per_kg,
                    "currency": o.currency,
                    "status": o.status,
                    "buyer_count": buyer_count,
                    "pool_count": len(pools),
                    "pool_regions": pool_regions,
                    "total_committed_kg": total_committed,
                    "delivery_location": o.delivery_location,
                    "description": o.description,
                    "dpp_url": o.dpp_url,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "expires_at": o.expires_at.isoformat() if o.expires_at else None,
                })

            return {"containers": results, "count": len(results)}
    except Exception as e:
        logger.error(f"marketplace_my_containers error: {e}", exc_info=True)
        return {"containers": [], "count": 0}


# ═══════════════════════════════════════════════════════════════
# ADMIN API (for Telegram Mini Apps)
# ═══════════════════════════════════════════════════════════════

admin_miniapp_router = APIRouter(prefix="/api/admin", tags=["miniapp-admin"])

ADMIN_TELEGRAM_IDS = set()
import os
_admin_id = os.getenv("ADMIN_TELEGRAM_USER_ID")
if _admin_id:
    ADMIN_TELEGRAM_IDS.add(str(_admin_id))


def _require_admin_telegram(telegram_user_id: str):
    """Check if Telegram user is an admin."""
    if not telegram_user_id or str(telegram_user_id) not in ADMIN_TELEGRAM_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")


@admin_miniapp_router.get("/users")
async def admin_list_users(
    x_telegram_user_id: Optional[str] = Header(None),
):
    """List all users (admin only)."""
    _require_admin_telegram(x_telegram_user_id)
    try:
        with get_db() as db:
            users = db.query(UserIdentity).order_by(
                UserIdentity.is_approved.asc(),
                UserIdentity.id.desc()
            ).limit(100).all()

            return {
                "users": [
                    {
                        "id": u.id,
                        "telegram_user_id": u.telegram_user_id,
                        "name": f"{u.telegram_first_name or ''} {u.telegram_last_name or ''}".strip() or f"User {u.telegram_user_id}",
                        "full_name": f"{u.telegram_first_name or ''} {u.telegram_last_name or ''}".strip(),
                        "phone_number": u.phone_number,
                        "role": u.role or "FARMER",
                        "organization": u.organization.name if u.organization else None,
                        "is_approved": u.is_approved,
                        "preferred_language": u.preferred_language,
                    }
                    for u in users
                ],
                "total": len(users),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_list_users error: {e}", exc_info=True)
        return {"users": [], "total": 0}


@admin_miniapp_router.get("/stats")
async def admin_stats(
    x_telegram_user_id: Optional[str] = Header(None),
):
    """Get summary statistics for admin dashboard."""
    _require_admin_telegram(x_telegram_user_id)
    try:
        with get_db() as db:
            total_users = db.query(UserIdentity).count()
            total_batches = db.query(CoffeeBatch).count()
            total_rfqs = db.query(RFQ).count()
            total_events = db.query(EPCISEvent).count()

            return {
                "total_users": total_users,
                "total_batches": total_batches,
                "total_rfqs": total_rfqs,
                "total_events": total_events,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_stats error: {e}", exc_info=True)
        return {"total_users": 0, "total_batches": 0, "total_rfqs": 0, "total_events": 0}


class ApproveRequest(BaseModel):
    telegram_user_id: int


@admin_miniapp_router.post("/approve")
async def admin_approve_user(
    body: ApproveRequest,
    x_telegram_user_id: Optional[str] = Header(None),
):
    """Approve a pending user registration."""
    _require_admin_telegram(x_telegram_user_id)
    try:
        with get_db() as db:
            user = db.query(UserIdentity).filter(
                UserIdentity.telegram_user_id == str(body.telegram_user_id)
            ).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user.is_approved = True
            user.approved_at = datetime.utcnow()
            user.approved_by_admin_id = int(x_telegram_user_id) if x_telegram_user_id else None
            db.flush()

            return {
                "success": True,
                "message": f"User {user.telegram_first_name or user.telegram_user_id} approved",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_approve error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Serve mini app HTML pages (supports both /page and /page.html)
mini_app_router = APIRouter(prefix="/miniapps", tags=["miniapp-pages"])

MINIAPPS_DIR = Path(__file__).parent.parent.parent / "miniapps"

def _serve_page(filename: str):
    """Return a FileResponse for the given miniapp HTML file."""
    html_path = MINIAPPS_DIR / filename
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/index")
@mini_app_router.get("/index.html")
async def serve_index():
    return _serve_page("index.html")

@mini_app_router.get("/batch_browser")
@mini_app_router.get("/batch_browser.html")
async def serve_batch_browser():
    return _serve_page("batch_browser.html")

@mini_app_router.get("/batches")
async def serve_batches_alias():
    return _serve_page("batch_browser.html")

@mini_app_router.get("/marketplace")
@mini_app_router.get("/marketplace.html")
async def serve_marketplace():
    return _serve_page("marketplace.html")

@mini_app_router.get("/trace")
@mini_app_router.get("/trace.html")
async def serve_trace():
    return _serve_page("trace.html")

@mini_app_router.get("/admin")
@mini_app_router.get("/admin.html")
async def serve_admin():
    return _serve_page("admin.html")

@mini_app_router.get("/profile")
@mini_app_router.get("/profile.html")
async def serve_profile():
    return _serve_page("profile.html")

@mini_app_router.get("/assistant")
@mini_app_router.get("/assistant.html")
async def serve_assistant():
    return _serve_page("assistant.html")
