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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.connection import get_db
from database.models import (
    UserIdentity, Organization, CoffeeBatch,
    RFQ, RFQOffer, RFQAcceptance, PendingRegistration, UATIssue
)
from voice.web.auth import require_admin, require_admin_flexible, create_jwt_token
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
                "phone_number": user.phone_number,
                "full_name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
                "name": f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
                "role": user.role,
                "preferred_language": user.preferred_language,
                "is_approved": user.is_approved
            },
            message="Login successful"
        )


@router.get("/api/auth/me")
def get_current_user_info(user: UserIdentity = Depends(require_admin)):
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
def get_registrations(
    status: Optional[str] = Query(None, regex="^(PENDING|APPROVED|REJECTED)$"),
    role: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """
    Get list of user registrations with filtering.
    
    Query params:
    - status: PENDING, APPROVED, REJECTED
    - role: FARMER, COOPERATIVE_MANAGER, EXPORTER, BUYER
    - limit: Max results (default 50, max 200)
    - offset: Pagination offset
    """
    with get_db() as db:
        # Check if we're looking for pending registrations
        if status == 'PENDING':
            # Query PendingRegistration table for pending registrations
            query = db.query(PendingRegistration)
            
            # Filter by role if specified
            if role:
                query = query.filter_by(requested_role=role)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            pending_regs = query.order_by(PendingRegistration.id.desc()).limit(limit).offset(offset).all()
            
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "registrations": [
                    {
                        "id": reg.id,
                        "name": reg.full_name,
                        "phone_number": reg.phone_number,
                        "role": reg.requested_role,
                        "organization": reg.organization_name,
                        "organization_id": None,
                        "status": reg.status,
                        "created_at": reg.created_at.isoformat() if reg.created_at else None,
                        "telegram_username": reg.telegram_username,
                        "telegram_first_name": reg.telegram_first_name,
                        "telegram_last_name": reg.telegram_last_name,
                        "location": reg.location,
                        "registration_number": reg.registration_number,
                        "reason": reg.reason,
                        "export_license": reg.export_license,
                        "port_access": reg.port_access,
                        "shipping_capacity_tons": reg.shipping_capacity_tons,
                        "business_type": reg.business_type,
                        "country": reg.country,
                        "target_volume_tons_annual": reg.target_volume_tons_annual,
                        "quality_preferences": reg.quality_preferences,
                    }
                    for reg in pending_regs
                ]
            }
        else:
            # For APPROVED/REJECTED, query UserIdentity table
            query = db.query(UserIdentity)
            
            # Filter by approval status
            if status == 'APPROVED':
                query = query.filter_by(is_approved=True)
            elif status == 'REJECTED':
                # Rejected users might not exist in UserIdentity, check PendingRegistration
                rejected_query = db.query(PendingRegistration).filter_by(status='REJECTED')
                if role:
                    rejected_query = rejected_query.filter_by(requested_role=role)
                
                total = rejected_query.count()
                rejected_regs = rejected_query.order_by(PendingRegistration.id.desc()).limit(limit).offset(offset).all()
                
                return {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "registrations": [
                        {
                            "id": reg.id,
                            "name": reg.full_name,
                            "phone_number": reg.phone_number,
                            "role": reg.requested_role,
                            "organization": reg.organization_name,
                            "organization_id": None,
                            "status": reg.status,
                            "created_at": reg.created_at.isoformat() if reg.created_at else None,
                            "telegram_username": reg.telegram_username,
                            "telegram_first_name": reg.telegram_first_name,
                            "telegram_last_name": reg.telegram_last_name,
                            "location": reg.location,
                            "registration_number": reg.registration_number,
                            "reason": reg.reason,
                            "rejection_reason": reg.rejection_reason,
                            "reviewed_at": reg.reviewed_at.isoformat() if reg.reviewed_at else None,
                        }
                        for reg in rejected_regs
                    ]
                }
            
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
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                    for user in users
                ]
            }


@router.post("/admin/registrations/{user_id}/approve")
def approve_registration(
    user_id: int,
    request: ApprovalRequest,
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """
    Approve a pending registration.
    
    Optionally assign organization.
    Transfers PIN hash from PendingRegistration to UserIdentity for web login.
    """
    with get_db() as db:
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_approved:
            raise HTTPException(status_code=400, detail="User already approved")
        
        # Transfer PIN hash from PendingRegistration to UserIdentity
        pending = db.query(PendingRegistration).filter_by(
            telegram_user_id=int(user.telegram_user_id)
        ).first()
        
        if pending and pending.pin_hash:
            user.pin_hash = pending.pin_hash
            user.pin_set_at = datetime.utcnow()
            logger.info(f"Transferred PIN hash from pending registration to user {user_id}")
        else:
            logger.warning(f"No PIN hash found in pending registration for user {user_id}")
        
        # Update user approval status
        user.is_approved = True
        user.approved_at = datetime.utcnow()
        user.approved_by_admin_id = admin.id
        
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
            "organization_id": user.organization_id,
            "pin_transferred": bool(pending and pending.pin_hash)
        }


@router.post("/admin/registrations/{user_id}/reject")
def reject_registration(
    user_id: int,
    request: ApprovalRequest,
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """
    Reject a pending registration.
    
    Note: Currently we just mark as rejected.
    Could delete user or add rejection_reason field.
    """
    with get_db() as db:
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
def get_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    approved: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """
    Search and filter users.
    
    Query params:
    - search: Search by name or phone
    - role: Filter by role
    - approved: Filter by approval status
    """
    with get_db() as db:
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
def get_user_detail(
    user_id: int,
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get detailed user profile."""
    with get_db() as db:
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
def update_user(
    user_id: int,
    request: UserUpdateRequest,
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Update user profile."""
    with get_db() as db:
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
def get_rfqs(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get RFQs with filtering."""
    with get_db() as db:
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
def get_offers(
    rfq_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get offers with optional RFQ filtering."""
    with get_db() as db:
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
def get_settlements(
    payment_status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get acceptances (settlements) with filtering."""
    with get_db() as db:
        query = db.query(RFQAcceptance)
        
        if payment_status:
            query = query.filter_by(payment_status=payment_status)
        
        total = query.count()
        acceptances = query.order_by(RFQAcceptance.id.desc()).limit(limit).all()
        
        return {
            "total": total,
            "settlements": [
                {
                    "id": acceptance.id,
                    "rfq_id": acceptance.rfq_id,
                    "offer_id": acceptance.offer_id,
                    "acceptance_number": acceptance.acceptance_number,
                    "quantity_accepted_kg": acceptance.quantity_accepted_kg,
                    "payment_status": acceptance.payment_status,
                    "delivery_status": acceptance.delivery_status,
                    "payment_method": acceptance.payment_method,
                    "settlement_tx_hash": acceptance.settlement_tx_hash
                }
                for acceptance in acceptances
            ]
        }


# ============================================================
# ANALYTICS
# ============================================================

@router.get("/admin/analytics/summary")
def get_analytics_summary(
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get dashboard summary statistics."""
    with get_db() as db:
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
        verified_batches = db.query(CoffeeBatch).filter(CoffeeBatch.verified_at.isnot(None)).count()
        
        # Acceptance stats (payments and deliveries)
        total_acceptances = db.query(RFQAcceptance).count()
        pending_payments = db.query(RFQAcceptance).filter_by(payment_status='PENDING').count()
        pending_deliveries = db.query(RFQAcceptance).filter_by(delivery_status='PENDING').count()
        
        return {
            "pending_registrations": pending_registrations,
            "total_users": total_users,
            "active_rfqs": active_rfqs,
            "total_offers": total_offers,
            "total_batches": total_batches,
            "verified_batches": verified_batches,
            "total_acceptances": total_acceptances,
            "pending_payments": pending_payments,
            "pending_deliveries": pending_deliveries,
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
                "total": total_batches,
                "verified": verified_batches
            },
            "acceptances": {
                "total": total_acceptances,
                "pending_payments": pending_payments,
                "pending_deliveries": pending_deliveries
            }
        }


@router.get("/admin/analytics/registrations")
def get_registration_analytics(
    days: int = Query(30, le=365),
    admin: UserIdentity = Depends(require_admin_flexible)
):
    """Get registration trends over time."""
    with get_db() as db:
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


# ============================================================
# UAT ISSUE REPORTING
# ============================================================

class UATIssueCreate(BaseModel):
    page: str
    category: str = "bug"
    severity: str = "minor"
    title: str = ""
    description: str = ""
    context_json: dict = {}
    browser_info: str = ""
    console_errors: list = []


class UATIssueUpdate(BaseModel):
    status: Optional[str] = None
    resolution_notes: Optional[str] = None


@router.post("/api/v1/uat/issues")
def create_uat_issue(body: UATIssueCreate, request: Request):
    """Submit a UAT issue. No auth required — anonymous submissions allowed."""
    # Optionally attach the authenticated user if a valid token is present
    from voice.web.auth import get_optional_user
    user = get_optional_user(request)

    with get_db() as db:
        issue = UATIssue(
            user_id=user.id if user else None,
            user_name=f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip() if user else "Anonymous",
            user_phone=user.phone_number or "" if user else "",
            page=body.page,
            category=body.category,
            severity=body.severity,
            title=body.title,
            description=body.description,
            context_json=body.context_json,
            browser_info=body.browser_info,
            console_errors=body.console_errors,
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)
        return {"id": issue.id, "status": issue.status}


@router.get("/api/v1/uat/issues")
def list_uat_issues(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: Optional[str] = Query(None),
    limit: int = Query(100, le=200),
    offset: int = Query(0, ge=0),
    admin: UserIdentity = Depends(require_admin_flexible),
):
    """List UAT issues. Admins see all issues."""
    with get_db() as db:
        q = db.query(UATIssue)
        if status:
            q = q.filter(UATIssue.status == status)
        if severity:
            q = q.filter(UATIssue.severity == severity)
        if page:
            q = q.filter(UATIssue.page == page)
        total = q.count()
        rows = q.order_by(UATIssue.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "issues": [
                {
                    "id": r.id,
                    "page": r.page,
                    "category": r.category,
                    "severity": r.severity,
                    "title": r.title,
                    "description": r.description,
                    "status": r.status,
                    "user_name": r.user_name,
                    "user_phone": r.user_phone,
                    "browser_info": r.browser_info,
                    "console_errors": r.console_errors,
                    "context_json": r.context_json,
                    "resolution_notes": r.resolution_notes,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                }
                for r in rows
            ],
        }


@router.patch("/api/v1/uat/issues/{issue_id}")
def update_uat_issue(
    issue_id: int,
    body: UATIssueUpdate,
    admin: UserIdentity = Depends(require_admin_flexible),
):
    """Update UAT issue status / resolution notes. Admin only."""
    with get_db() as db:
        issue = db.query(UATIssue).filter_by(id=issue_id).first()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        if body.status:
            issue.status = body.status
            if body.status in ("fixed", "verified", "wont_fix"):
                issue.resolved_at = datetime.utcnow()
        if body.resolution_notes is not None:
            issue.resolution_notes = body.resolution_notes
        issue.updated_at = datetime.utcnow()
        db.commit()
        return {"success": True, "id": issue.id, "status": issue.status}

