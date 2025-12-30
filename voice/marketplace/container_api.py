"""
Container Offerings API - Phase 4.5: Fractional Ownership

Enables multiple buyers to purchase portions of a single container.
Integrates with existing Phase 4 payment system.

Endpoints:
- POST /api/container/offer - List container for fractional sale
- GET /api/containers - Browse available containers
- POST /api/container/{id}/buy - Purchase partial quantity
- GET /api/container/{id} - Get container details
- GET /api/container/{id}/buyers - View buyers of container
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import (
    ContainerOffering, RFQAcceptance, Organization, 
    UserIdentity, AggregationRelationship, SessionLocal
)
from voice.marketplace.payment_messaging import send_payment_instructions

# Database dependency
def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api", tags=["containers"])

# ============================================================================
# Pydantic Models (Request/Response Schemas)
# ============================================================================

class ContainerOfferCreate(BaseModel):
    """Request schema for listing a container"""
    container_sscc: str = Field(..., min_length=18, max_length=18, description="18-digit SSCC")
    aggregation_id: Optional[int] = Field(None, description="Link to aggregation_relationships")
    total_quantity_kg: float = Field(..., gt=0, description="Total container quantity")
    price_per_kg: float = Field(..., gt=0, description="Price per kg in USD")
    variety: Optional[str] = Field(None, max_length=100)
    processing_method: Optional[str] = Field(None, max_length=50)
    grade: Optional[str] = Field(None, max_length=20)
    certifications: Optional[dict] = Field(None)
    delivery_location: Optional[str] = Field(None, max_length=200)
    earliest_delivery_date: Optional[datetime] = None
    latest_delivery_date: Optional[datetime] = None
    description: Optional[str] = None
    sample_photos: Optional[List[str]] = None
    dpp_url: Optional[str] = None
    expires_days: int = Field(default=90, ge=1, le=365, description="Days until offer expires")

class PartialPurchaseRequest(BaseModel):
    """Request schema for purchasing partial container quantity"""
    quantity_kg: float = Field(..., gt=0, description="Quantity to purchase in kg")
    payment_terms: Optional[str] = Field(None, max_length=50)

class ContainerOfferingResponse(BaseModel):
    """Response schema for container offering"""
    id: int
    container_sscc: str
    cooperative_id: int
    cooperative_name: str
    total_quantity_kg: float
    available_quantity_kg: float
    reserved_quantity_kg: float
    sold_quantity_kg: float
    fill_percentage: float
    price_per_kg: float
    currency: str
    status: str
    variety: Optional[str]
    processing_method: Optional[str]
    grade: Optional[str]
    certifications: Optional[dict]
    delivery_location: Optional[str]
    earliest_delivery_date: Optional[datetime]
    latest_delivery_date: Optional[datetime]
    description: Optional[str]
    sample_photos: Optional[List[str]]
    dpp_url: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    total_value_usd: float
    
    class Config:
        from_attributes = True

class PurchaseResponse(BaseModel):
    """Response schema for partial purchase"""
    acceptance_id: int
    acceptance_number: str
    container_id: int
    container_sscc: str
    quantity_purchased_kg: float
    price_per_kg: float
    total_amount_usd: float
    payment_status: str
    message: str

class ContainerBuyerInfo(BaseModel):
    """Info about buyers who purchased from container"""
    buyer_id: int
    buyer_name: str
    quantity_kg: float
    payment_status: str
    accepted_at: datetime

# ============================================================================
# Helper Functions
# ============================================================================

def get_current_user(user_id: int, db: Session) -> UserIdentity:
    """Get user by ID and verify exists"""
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def generate_acceptance_number(db: Session) -> str:
    """Generate unique acceptance number like ACC-000123"""
    last = db.query(RFQAcceptance).order_by(RFQAcceptance.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f"ACC-{next_id:06d}"

# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/container/offer", response_model=ContainerOfferingResponse, status_code=201)
def create_container_offering(
    offering: ContainerOfferCreate,
    user_id: int = Query(..., description="User ID (cooperative manager)"),
    db: Session = Depends(get_db)
):
    """
    List a container for fractional sale.
    
    **Access:** COOPERATIVE_MANAGER role
    
    Creates a container offering that multiple buyers can purchase portions of.
    Integrates with existing payment system - each buyer gets separate payment instructions.
    """
    # Get user and verify role
    user = get_current_user(user_id, db)
    
    if user.role not in ["COOPERATIVE_MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Only cooperative managers can list containers"
        )
    
    # Verify user's organization
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User not associated with organization")
    
    # Check if container already listed
    existing = db.query(ContainerOffering).filter_by(
        container_sscc=offering.container_sscc,
        status='AVAILABLE'
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Container {offering.container_sscc} already listed"
        )
    
    # Set expiration date
    expires_at = datetime.utcnow() + timedelta(days=offering.expires_days)
    
    # Create offering
    container_offering = ContainerOffering(
        container_sscc=offering.container_sscc,
        aggregation_id=offering.aggregation_id,
        cooperative_id=user.organization_id,
        total_quantity_kg=offering.total_quantity_kg,
        available_quantity_kg=offering.total_quantity_kg,  # Initially all available
        reserved_quantity_kg=0,
        price_per_kg=offering.price_per_kg,
        currency='USD',
        status='AVAILABLE',
        variety=offering.variety,
        processing_method=offering.processing_method,
        grade=offering.grade,
        certifications=offering.certifications,
        delivery_location=offering.delivery_location,
        earliest_delivery_date=offering.earliest_delivery_date,
        latest_delivery_date=offering.latest_delivery_date,
        description=offering.description,
        sample_photos=offering.sample_photos,
        dpp_url=offering.dpp_url,
        expires_at=expires_at
    )
    
    db.add(container_offering)
    db.commit()
    db.refresh(container_offering)
    
    # Get cooperative name for response
    cooperative = db.query(Organization).filter_by(id=user.organization_id).first()
    
    return ContainerOfferingResponse(
        id=container_offering.id,
        container_sscc=container_offering.container_sscc,
        cooperative_id=container_offering.cooperative_id,
        cooperative_name=cooperative.name if cooperative else "Unknown",
        total_quantity_kg=container_offering.total_quantity_kg,
        available_quantity_kg=container_offering.available_quantity_kg,
        reserved_quantity_kg=container_offering.reserved_quantity_kg,
        sold_quantity_kg=container_offering.sold_quantity_kg,
        fill_percentage=container_offering.fill_percentage,
        price_per_kg=container_offering.price_per_kg,
        currency=container_offering.currency,
        status=container_offering.status,
        variety=container_offering.variety,
        processing_method=container_offering.processing_method,
        grade=container_offering.grade,
        certifications=container_offering.certifications,
        delivery_location=container_offering.delivery_location,
        earliest_delivery_date=container_offering.earliest_delivery_date,
        latest_delivery_date=container_offering.latest_delivery_date,
        description=container_offering.description,
        sample_photos=container_offering.sample_photos,
        dpp_url=container_offering.dpp_url,
        created_at=container_offering.created_at,
        expires_at=container_offering.expires_at,
        total_value_usd=container_offering.total_value_usd
    )

@router.get("/containers", response_model=List[ContainerOfferingResponse])
def list_available_containers(
    status: Optional[str] = Query(None, description="Filter by status"),
    min_quantity_kg: Optional[float] = Query(None, ge=0, description="Minimum available quantity"),
    cooperative_id: Optional[int] = Query(None, description="Filter by cooperative"),
    db: Session = Depends(get_db)
):
    """
    Browse available containers for fractional purchase.
    
    **Access:** Any registered user
    
    Returns containers with available quantity > 0.
    Buyers can see all offerings, cooperatives can see their own.
    """
    query = db.query(ContainerOffering)
    
    # Filter by status
    if status:
        query = query.filter(ContainerOffering.status == status)
    else:
        # Default: show available and partially sold
        query = query.filter(ContainerOffering.status.in_(['AVAILABLE', 'PARTIALLY_SOLD']))
    
    # Filter by minimum available quantity
    if min_quantity_kg is not None:
        query = query.filter(ContainerOffering.available_quantity_kg >= min_quantity_kg)
    
    # Filter by cooperative
    if cooperative_id:
        query = query.filter(ContainerOffering.cooperative_id == cooperative_id)
    
    # Order by creation date (newest first)
    offerings = query.order_by(ContainerOffering.created_at.desc()).all()
    
    results = []
    for offering in offerings:
        cooperative = db.query(Organization).filter_by(id=offering.cooperative_id).first()
        
        results.append(ContainerOfferingResponse(
            id=offering.id,
            container_sscc=offering.container_sscc,
            cooperative_id=offering.cooperative_id,
            cooperative_name=cooperative.name if cooperative else "Unknown",
            total_quantity_kg=offering.total_quantity_kg,
            available_quantity_kg=offering.available_quantity_kg,
            reserved_quantity_kg=offering.reserved_quantity_kg,
            sold_quantity_kg=offering.sold_quantity_kg,
            fill_percentage=offering.fill_percentage,
            price_per_kg=offering.price_per_kg,
            currency=offering.currency,
            status=offering.status,
            variety=offering.variety,
            processing_method=offering.processing_method,
            grade=offering.grade,
            certifications=offering.certifications,
            delivery_location=offering.delivery_location,
            earliest_delivery_date=offering.earliest_delivery_date,
            latest_delivery_date=offering.latest_delivery_date,
            description=offering.description,
            sample_photos=offering.sample_photos,
            dpp_url=offering.dpp_url,
            created_at=offering.created_at,
            expires_at=offering.expires_at,
            total_value_usd=offering.total_value_usd
        ))
    
    return results

@router.post("/container/{container_id}/buy", response_model=PurchaseResponse, status_code=201)
async def purchase_partial_container(
    container_id: int,
    purchase: PartialPurchaseRequest,
    user_id: int = Query(..., description="User ID (buyer)"),
    db: Session = Depends(get_db)
):
    """
    Purchase a partial quantity from a container.
    
    **Access:** BUYER role
    
    Creates an RFQAcceptance linked to the container offering.
    Automatically sends payment instructions using Phase 4 payment system.
    Reduces available quantity and updates container status.
    """
    # Get user and verify role
    user = get_current_user(user_id, db)
    
    if user.role not in ["BUYER", "ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Only buyers can purchase containers"
        )
    
    # Get container offering
    offering = db.query(ContainerOffering).filter_by(id=container_id).first()
    
    if not offering:
        raise HTTPException(status_code=404, detail="Container offering not found")
    
    # Validate quantity available
    if purchase.quantity_kg > offering.available_quantity_kg:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient quantity. Available: {offering.available_quantity_kg}kg, Requested: {purchase.quantity_kg}kg"
        )
    
    # Validate status
    if offering.status not in ['AVAILABLE', 'PARTIALLY_SOLD']:
        raise HTTPException(
            status_code=400,
            detail=f"Container not available for purchase (status: {offering.status})"
        )
    
    # Calculate total amount
    total_amount = purchase.quantity_kg * offering.price_per_kg
    
    # Generate acceptance number
    acceptance_number = generate_acceptance_number(db)
    
    # Create RFQAcceptance (links to Phase 4 payment system)
    acceptance = RFQAcceptance(
        rfq_id=None,  # No RFQ for direct container purchase
        offer_id=None,  # No offer for direct container purchase
        container_offering_id=container_id,
        acceptance_number=acceptance_number,
        quantity_accepted_kg=purchase.quantity_kg,
        payment_terms=purchase.payment_terms or "Net 7 days",
        payment_status="PENDING",
        delivery_status="PENDING"
    )
    
    db.add(acceptance)
    
    # Update container quantities
    offering.available_quantity_kg -= purchase.quantity_kg
    offering.reserved_quantity_kg += purchase.quantity_kg
    
    # Update status
    if offering.available_quantity_kg == 0:
        offering.status = 'FULLY_RESERVED'
    else:
        offering.status = 'PARTIALLY_SOLD'
    
    offering.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(acceptance)
    db.refresh(offering)
    
    # Send payment instructions (Phase 4 integration)
    try:
        cooperative_org = db.query(Organization).filter_by(id=offering.cooperative_id).first()
        
        await send_payment_instructions(
            acceptance=acceptance,
            offer=None,  # No RFQOffer for direct purchase
            rfq=None,  # No RFQ for direct purchase
            buyer=user,
            cooperative_org=cooperative_org,
            db=db
        )
    except Exception as e:
        # Log error but don't fail the purchase
        print(f"Warning: Failed to send payment instructions: {e}")
    
    return PurchaseResponse(
        acceptance_id=acceptance.id,
        acceptance_number=acceptance.acceptance_number,
        container_id=offering.id,
        container_sscc=offering.container_sscc,
        quantity_purchased_kg=purchase.quantity_kg,
        price_per_kg=offering.price_per_kg,
        total_amount_usd=total_amount,
        payment_status=acceptance.payment_status,
        message=f"Successfully purchased {purchase.quantity_kg}kg. Payment instructions sent to your Telegram."
    )

@router.get("/container/{container_id}", response_model=ContainerOfferingResponse)
def get_container_details(
    container_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a container offering.
    
    **Access:** Any registered user
    """
    offering = db.query(ContainerOffering).filter_by(id=container_id).first()
    
    if not offering:
        raise HTTPException(status_code=404, detail="Container offering not found")
    
    cooperative = db.query(Organization).filter_by(id=offering.cooperative_id).first()
    
    return ContainerOfferingResponse(
        id=offering.id,
        container_sscc=offering.container_sscc,
        cooperative_id=offering.cooperative_id,
        cooperative_name=cooperative.name if cooperative else "Unknown",
        total_quantity_kg=offering.total_quantity_kg,
        available_quantity_kg=offering.available_quantity_kg,
        reserved_quantity_kg=offering.reserved_quantity_kg,
        sold_quantity_kg=offering.sold_quantity_kg,
        fill_percentage=offering.fill_percentage,
        price_per_kg=offering.price_per_kg,
        currency=offering.currency,
        status=offering.status,
        variety=offering.variety,
        processing_method=offering.processing_method,
        grade=offering.grade,
        certifications=offering.certifications,
        delivery_location=offering.delivery_location,
        earliest_delivery_date=offering.earliest_delivery_date,
        latest_delivery_date=offering.latest_delivery_date,
        description=offering.description,
        sample_photos=offering.sample_photos,
        dpp_url=offering.dpp_url,
        created_at=offering.created_at,
        expires_at=offering.expires_at,
        total_value_usd=offering.total_value_usd
    )

@router.get("/container/{container_id}/buyers", response_model=List[ContainerBuyerInfo])
def list_container_buyers(
    container_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    View all buyers who purchased from this container.
    
    **Access:** Container owner (cooperative) or admin
    """
    # Get user
    user = get_current_user(user_id, db)
    
    # Get offering
    offering = db.query(ContainerOffering).filter_by(id=container_id).first()
    
    if not offering:
        raise HTTPException(status_code=404, detail="Container offering not found")
    
    # Verify access (owner or admin)
    if user.role != "ADMIN" and user.organization_id != offering.cooperative_id:
        raise HTTPException(
            status_code=403,
            detail="Only container owner can view buyers"
        )
    
    # Get all acceptances for this container
    acceptances = db.query(RFQAcceptance).filter_by(
        container_offering_id=container_id
    ).all()
    
    results = []
    for acc in acceptances:
        # Get buyer info
        buyer = db.query(UserIdentity).join(RFQAcceptance, RFQAcceptance.id == acc.id).first()
        
        results.append(ContainerBuyerInfo(
            buyer_id=buyer.id if buyer else 0,
            buyer_name=f"{buyer.telegram_first_name} {buyer.telegram_last_name or ''}" if buyer else "Unknown",
            quantity_kg=acc.quantity_accepted_kg,
            payment_status=acc.payment_status,
            accepted_at=acc.accepted_at
        ))
    
    return results
