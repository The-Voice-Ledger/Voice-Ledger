"""
Admin Dashboard API

Provides endpoints for:
- Registration approval/rejection
- User management
- Marketplace monitoring
- Analytics and reporting

Date: December 24, 2025
Lab 17: Admin Dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.connection import get_db
from database.models import (
    UserIdentity, Organization, CoffeeBatch, 
    RFQ, RFQOffer, RFQAcceptance
)
from voice.web.auth import require_admin, create_jwt_token, verify_pin
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# PYDANTIC MODELS
# ============================================================

class LoginRequest(BaseModel):
    phone_number: str
    pin: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[dict] = None
    message: str


class ApprovalRequest(BaseModel):
    comments: Optional[str] = None
    organization_id: Optional[int] = None


class UserUpdateRequest(BaseModel):
    preferred_language: Optional[str] = None
    organization_id: Optional[int] = None
    is_approved: Optional[bool] = None


# ============================================================
# AUTHENTICATION
# ============================================================

@router.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Authenticate user with phone number and PIN.
    
    Returns JWT token valid for 7 days.
    """
    with get_db() as db:
        user = db.query(UserIdentity).filter(UserIdentity.phone_number == request.phone_number).first()
        
        if not user or not user.pin_hash:
            return LoginResponse(
                success=False,
                message="Invalid phone number or PIN"
            )
        
        # Verify PIN using bcrypt
        import bcrypt
        if not bcrypt.checkpw(request.pin.encode('utf-8'), user.pin_hash.encode('utf-8')):
            return LoginResponse(
                success=False,
                message="Invalid phone number or PIN"
            )
        
        # Generate JWT token
        token = create_jwt_token(user.id, user.role)
        
        logger.info(f"Successful login for user {user.id} ({user.phone_number})")
        
        return LoginResponse(
            success=True,
            token=token,
            user={
                "id": user.id,
                "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
                "role": user.role,
                "preferred_language": user.preferred_language,
                "is_approved": user.is_approved
            },
            message="Login successful"
        )


@router.get("/api/auth/me")
async def get_current_user_info(user: UserIdentity = Depends(require_admin)):
    """Get current authenticated admin user's profile."""
    return {
        "id": user.id,
        "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
        "role": user.role,
        "phone_number": user.phone_number,
        "preferred_language": user.preferred_language,
        "organization": user.organization.name if user.organization else None
    }


# ============================================================
# REGISTRATION MANAGEMENT
# ============================================================

@router.get("/admin/registrations")
async def get_registrations(
    status: Optional[str] = Query(None, regex="^(PENDING|APPROVED|REJECTED)$"),
    role: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get list of user registrations with filtering.
    
    Query params:
    - status: PENDING, APPROVED, REJECTED
    - role: FARMER, COOPERATIVE_MANAGER, EXPORTER, BUYER
    - limit: Max results (default 50, max 200)
    - offset: Pagination offset
    """
    query = db.query(UserIdentity)
    
    # Filter by approval status
    if status == 'PENDING':
        query = query.filter_by(is_approved=False)
    elif status == 'APPROVED':
        query = query.filter_by(is_approved=True)
    
    # Filter by role
    if role:
        query = query.filter_by(role=role)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.order_by(UserIdentity.id.desc()).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "registrations": [
            {
                "id": user.id,
                "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
                "phone_number": user.phone_number,
                "role": user.role,
                "organization": user.organization.name if user.organization else None,
                "organization_id": user.organization_id,
                "preferred_language": user.preferred_language,
                "is_approved": user.is_approved,
                "telegram_user_id": user.telegram_user_id,
                "created_at": user.id  # Using ID as proxy for creation order
            }
            for user in users
        ]
    }


@router.post("/admin/registrations/{user_id}/approve")
async def approve_registration(
    user_id: int,
    request: ApprovalRequest,
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Approve a pending registration.
    
    Optionally assign organization.
    """
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_approved:
        raise HTTPException(status_code=400, detail="User already approved")
    
    # Update user
    user.is_approved = True
    
    if request.organization_id:
        # Verify organization exists
        org = db.query(Organization).filter_by(id=request.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        user.organization_id = request.organization_id
    
    db.commit()
    
    logger.info(
        f"Admin {admin.id} approved user {user_id} "
        f"(org: {request.organization_id}, comments: {request.comments})"
    )
    
    return {
        "success": True,
        "message": f"User {user.telegram_first_name} approved successfully",
        "user_id": user_id,
        "organization_id": user.organization_id
    }


@router.post("/admin/registrations/{user_id}/reject")
async def reject_registration(
    user_id: int,
    request: ApprovalRequest,
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reject a pending registration.
    
    Note: Currently we just mark as rejected.
    Could delete user or add rejection_reason field.
    """
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.warning(
        f"Admin {admin.id} rejected user {user_id} "
        f"(reason: {request.comments})"
    )
    
    # For now, we'll just keep them unapproved
    # Could add rejection_reason field or delete user
    
    return {
        "success": True,
        "message": f"User {user.telegram_first_name} rejected",
        "user_id": user_id,
        "comments": request.comments
    }


# ============================================================
# USER MANAGEMENT
# ============================================================

@router.get("/admin/users")
async def get_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    approved: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Search and filter users.
    
    Query params:
    - search: Search by name or phone
    - role: Filter by role
    - approved: Filter by approval status
    """
    query = db.query(UserIdentity)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (UserIdentity.telegram_first_name.ilike(search_pattern)) |
            (UserIdentity.telegram_last_name.ilike(search_pattern)) |
            (UserIdentity.phone_number.ilike(search_pattern))
        )
    
    if role:
        query = query.filter_by(role=role)
    
    if approved is not None:
        query = query.filter_by(is_approved=approved)
    
    total = query.count()
    users = query.limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "users": [
            {
                "id": user.id,
                "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
                "phone_number": user.phone_number,
                "role": user.role,
                "organization": user.organization.name if user.organization else None,
                "is_approved": user.is_approved,
                "preferred_language": user.preferred_language
            }
            for user in users
        ]
    }


@router.get("/admin/users/{user_id}")
async def get_user_detail(
    user_id: int,
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get detailed user profile."""
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's batches if farmer
    batches = []
    if user.role == 'FARMER':
        batches = db.query(CoffeeBatch).filter_by(farmer_id=user.id).all()
    
    return {
        "id": user.id,
        "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
        "phone_number": user.phone_number,
        "role": user.role,
        "organization": user.organization.name if user.organization else None,
        "organization_id": user.organization_id,
        "is_approved": user.is_approved,
        "preferred_language": user.preferred_language,
        "telegram_user_id": user.telegram_user_id,
        "did": user.did,
        "batches_count": len(batches),
        "batches": [
            {
                "id": batch.id,
                "sscc": batch.sscc,
                "weight_kg": batch.weight_kg,
                "grade": batch.grade
            }
            for batch in batches[:5]  # First 5 batches
        ]
    }


@router.patch("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user profile."""
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.preferred_language:
        if request.preferred_language not in ['en', 'am']:
            raise HTTPException(status_code=400, detail="Invalid language")
        user.preferred_language = request.preferred_language
        user.language_set_at = datetime.utcnow()
    
    if request.organization_id is not None:
        org = db.query(Organization).filter_by(id=request.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        user.organization_id = request.organization_id
    
    if request.is_approved is not None:
        user.is_approved = request.is_approved
    
    db.commit()
    
    logger.info(f"Admin {admin.id} updated user {user_id}")
    
    return {"success": True, "message": "User updated"}


# ============================================================
# MARKETPLACE MONITORING
# ============================================================

@router.get("/admin/rfqs")
async def get_rfqs(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get RFQs with filtering."""
    query = db.query(RFQ)
    
    if status:
        query = query.filter_by(status=status)
    
    total = query.count()
    rfqs = query.order_by(RFQ.id.desc()).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "rfqs": [
            {
                "id": rfq.id,
                "buyer_id": rfq.buyer_id,
                "buyer_name": rfq.buyer.telegram_first_name if rfq.buyer else None,
                "quantity_kg": rfq.quantity_kg,
                "grade": rfq.grade,
                "status": rfq.status,
                "offers_count": len(rfq.offers) if hasattr(rfq, 'offers') and rfq.offers else 0
            }
            for rfq in rfqs
        ]
    }


@router.get("/admin/offers")
async def get_offers(
    rfq_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get offers with optional RFQ filtering."""
    query = db.query(RFQOffer)
    
    if rfq_id:
        query = query.filter_by(rfq_id=rfq_id)
    
    total = query.count()
    offers = query.order_by(RFQOffer.id.desc()).limit(limit).all()
    
    return {
        "total": total,
        "offers": [
            {
                "id": offer.id,
                "rfq_id": offer.rfq_id,
                "cooperative_id": offer.cooperative_id,
                "price_per_kg": float(offer.price_per_kg),
                "status": offer.status
            }
            for offer in offers
        ]
    }


@router.get("/admin/settlements")
async def get_settlements(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get acceptances (settlements) with filtering."""
    query = db.query(RFQAcceptance)
    
    if status:
        query = query.filter_by(status=status)
    
    total = query.count()
    acceptances = query.order_by(RFQAcceptance.id.desc()).limit(limit).all()
    
    return {
        "total": total,
        "settlements": [
            {
                "id": acceptance.id,
                "rfq_id": acceptance.rfq_id,
                "offer_id": acceptance.offer_id,
                "status": acceptance.status,
                "total_value_usd": None  # Not stored in RFQAcceptance
            }
            for acceptance in acceptances
        ]
    }


# ============================================================
# ANALYTICS
# ============================================================

@router.get("/admin/analytics/summary")
async def get_analytics_summary(
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get dashboard summary statistics."""
    
    # User stats
    total_users = db.query(UserIdentity).count()
    pending_registrations = db.query(UserIdentity).filter_by(is_approved=False).count()
    
    # Role breakdown
    role_counts = db.query(
        UserIdentity.role,
        func.count(UserIdentity.id)
    ).group_by(UserIdentity.role).all()
    
    # Marketplace stats
    total_rfqs = db.query(RFQ).count()
    active_rfqs = db.query(RFQ).filter_by(status='ACTIVE').count()
    total_offers = db.query(RFQOffer).count()
    
    # Batch stats
    total_batches = db.query(CoffeeBatch).count()
    
    # Acceptance stats (instead of settlements)
    total_acceptances = db.query(RFQAcceptance).count()
    pending_acceptances = db.query(RFQAcceptance).filter_by(status='PENDING').count()
    
    return {
        "users": {
            "total": total_users,
            "pending_approval": pending_registrations,
            "by_role": {role: count for role, count in role_counts}
        },
        "marketplace": {
            "total_rfqs": total_rfqs,
            "active_rfqs": active_rfqs,
            "total_offers": total_offers
        },
        "batches": {
            "total": total_batches
        },
        "settlements": {
            "total": total_acceptances,
            "pending": pending_acceptances
        }
    }


@router.get("/admin/analytics/registrations")
async def get_registration_analytics(
    days: int = Query(30, le=365),
    admin: UserIdentity = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get registration trends over time."""
    
    # Get registrations by role over last N days
    # Note: UserIdentity doesn't have created_at, using ID as proxy
    
    role_counts = db.query(
        UserIdentity.role,
        func.count(UserIdentity.id)
    ).group_by(UserIdentity.role).all()
    
    return {
        "period_days": days,
        "by_role": {role: count for role, count in role_counts}
    }
