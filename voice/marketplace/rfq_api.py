"""
RFQ (Request for Quote) Marketplace API

Lab 15: Multi-Actor Marketplace - RFQ System

Endpoints:
- POST /api/rfq - Create RFQ (buyers)
- GET /api/rfqs - List RFQs (cooperatives can browse)
- GET /api/rfq/{rfq_id} - Get RFQ details
- POST /api/rfq/{rfq_id}/offer - Submit offer (cooperatives)
- GET /api/rfq/{rfq_id}/offers - View offers (buyer)
- POST /api/rfq/{rfq_id}/accept - Accept offer (buyer)
- GET /api/offers - List my offers (cooperatives)
- GET /api/broadcasts - View RFQs I was notified about

Architecture:
- RESTful API with FastAPI
- Role-based access (BUYER, COOPERATIVE_MANAGER)
- Smart broadcast matching (relevance scoring)
- Full traceability via DIDs
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import (
    RFQ, RFQOffer, RFQAcceptance, RFQBroadcast,
    UserIdentity, Organization, Buyer, SessionLocal
)

# Database dependency for FastAPI
def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api", tags=["marketplace"])

# ============================================================================
# Pydantic Models (Request/Response Schemas)
# ============================================================================

class RFQCreate(BaseModel):
    """Request schema for creating an RFQ"""
    quantity_kg: float = Field(..., gt=0, description="Quantity in kg")
    variety: Optional[str] = Field(None, max_length=100, description="Coffee variety")
    processing_method: Optional[str] = Field(None, max_length=50, description="Washed, Natural, etc.")
    grade: Optional[str] = Field(None, max_length=20, description="Grade 1, Grade 2, etc.")
    delivery_location: Optional[str] = Field(None, max_length=200, description="Delivery location")
    delivery_deadline: Optional[datetime] = Field(None, description="Delivery deadline")
    additional_specs: Optional[dict] = Field(None, description="Additional specifications")
    voice_recording_url: Optional[str] = Field(None, description="URL to voice recording if created via voice")
    transcript: Optional[str] = Field(None, description="Transcript of voice input")

class RFQResponse(BaseModel):
    """Response schema for RFQ"""
    id: int
    rfq_number: str
    buyer_id: int
    buyer_organization: str
    quantity_kg: float
    variety: Optional[str]
    processing_method: Optional[str]
    grade: Optional[str]
    delivery_location: Optional[str]
    delivery_deadline: Optional[datetime]
    status: str
    created_at: datetime
    expires_at: Optional[datetime]
    offer_count: int = 0

    class Config:
        from_attributes = True

class OfferCreate(BaseModel):
    """Request schema for creating an offer"""
    quantity_offered_kg: float = Field(..., gt=0, description="Quantity offered in kg")
    price_per_kg: float = Field(..., gt=0, description="Price per kg in USD")
    delivery_timeline: Optional[str] = Field(None, max_length=100, description="Delivery timeline")
    quality_certifications: Optional[dict] = Field(None, description="Certifications")
    sample_photos: Optional[List[str]] = Field(None, description="Photo URLs")
    voice_pitch_url: Optional[str] = Field(None, description="Voice pitch URL")

class OfferResponse(BaseModel):
    """Response schema for offer"""
    id: int
    offer_number: str
    rfq_id: int
    cooperative_id: int
    cooperative_name: str
    quantity_offered_kg: float
    price_per_kg: float
    delivery_timeline: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class AcceptOfferRequest(BaseModel):
    """Request schema for accepting an offer"""
    offer_id: int
    quantity_accepted_kg: float = Field(..., gt=0, description="Quantity to accept")
    payment_terms: Optional[str] = Field(None, max_length=50, description="NET_30, NET_60, etc.")

class AcceptanceResponse(BaseModel):
    """Response schema for acceptance"""
    id: int
    acceptance_number: str
    rfq_id: int
    offer_id: int
    quantity_accepted_kg: float
    payment_status: str
    delivery_status: str
    accepted_at: datetime

    class Config:
        from_attributes = True

# ============================================================================
# Helper Functions
# ============================================================================

def get_current_user(user_id: int, db: Session) -> UserIdentity:
    """Get current user from database (in production, use JWT auth)"""
    user = db.query(UserIdentity).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def generate_rfq_number(db: Session) -> str:
    """Generate unique RFQ number"""
    count = db.query(RFQ).count() + 1
    return f"RFQ-{count:06d}"

def generate_offer_number(db: Session) -> str:
    """Generate unique offer number"""
    count = db.query(RFQOffer).count() + 1
    return f"OFF-{count:06d}"

def generate_acceptance_number(db: Session) -> str:
    """Generate unique acceptance number"""
    count = db.query(RFQAcceptance).count() + 1
    return f"ACC-{count:06d}"

def calculate_relevance_score(rfq: RFQ, cooperative: Organization, db: Session) -> float:
    """
    Calculate relevance score for broadcasting RFQ to cooperative
    
    Factors:
    - Variety match (30%)
    - Processing method match (20%)
    - Geographic proximity (20%)
    - Available inventory (15%)
    - Past performance (15%)
    """
    score = 0.0
    
    # TODO: Implement smart matching algorithm
    # For now, return base score
    score = 0.75
    
    return score

def broadcast_rfq_to_cooperatives(rfq: RFQ, db: Session):
    """
    Smart broadcast: notify relevant cooperatives about new RFQ
    
    Broadcast reasons:
    - VARIETY_MATCH: Cooperative has this variety
    - REGION_MATCH: Geographic proximity
    - QUALITY_MATCH: Quality profile matches
    - TOP_PERFORMER: High reputation cooperative
    - INVENTORY_MATCH: Has available inventory
    """
    # Get all cooperatives
    cooperatives = db.query(Organization).filter_by(type="COOPERATIVE").all()
    
    for coop in cooperatives:
        relevance_score = calculate_relevance_score(rfq, coop, db)
        
        # Only broadcast if relevance > 0.5
        if relevance_score >= 0.5:
            broadcast = RFQBroadcast(
                rfq_id=rfq.id,
                cooperative_id=coop.id,
                broadcast_reason="SMART_MATCH",
                relevance_score=relevance_score,
                notified_at=datetime.utcnow()
            )
            db.add(broadcast)
    
    db.commit()

# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/rfq", response_model=RFQResponse, status_code=201)
def create_rfq(
    rfq_data: RFQCreate,
    user_id: int = Query(..., description="User ID (temp, will use JWT)"),
    db: Session = Depends(get_db)
):
    """
    Create new RFQ (Request for Quote)
    
    **Access:** BUYER role only
    
    **Workflow:**
    1. Validate user is BUYER
    2. Create RFQ record
    3. Smart broadcast to relevant cooperatives
    4. Return RFQ details
    
    **Example:**
    ```json
    {
      "quantity_kg": 5000,
      "variety": "Yirgacheffe",
      "processing_method": "Washed",
      "grade": "Grade 1",
      "delivery_location": "Rotterdam Port",
      "delivery_deadline": "2025-03-01T00:00:00"
    }
    ```
    """
    # Get user
    user = get_current_user(user_id, db)
    
    # Verify user is BUYER
    if user.role != "BUYER":
        raise HTTPException(
            status_code=403,
            detail="Only buyers can create RFQs"
        )
    
    # Generate RFQ number
    rfq_number = generate_rfq_number(db)
    
    # Set expiration (30 days default)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    # Create RFQ
    rfq = RFQ(
        buyer_id=user.id,
        rfq_number=rfq_number,
        quantity_kg=rfq_data.quantity_kg,
        variety=rfq_data.variety,
        processing_method=rfq_data.processing_method,
        grade=rfq_data.grade,
        delivery_location=rfq_data.delivery_location,
        delivery_deadline=rfq_data.delivery_deadline,
        additional_specs=rfq_data.additional_specs,
        voice_recording_url=rfq_data.voice_recording_url,
        transcript=rfq_data.transcript,
        status="OPEN",
        expires_at=expires_at
    )
    db.add(rfq)
    db.commit()
    db.refresh(rfq)
    
    # Smart broadcast to cooperatives
    broadcast_rfq_to_cooperatives(rfq, db)
    
    # Get buyer organization
    buyer_org = db.query(Organization).filter_by(id=user.organization_id).first()
    
    return RFQResponse(
        id=rfq.id,
        rfq_number=rfq.rfq_number,
        buyer_id=rfq.buyer_id,
        buyer_organization=buyer_org.name if buyer_org else "Unknown",
        quantity_kg=rfq.quantity_kg,
        variety=rfq.variety,
        processing_method=rfq.processing_method,
        grade=rfq.grade,
        delivery_location=rfq.delivery_location,
        delivery_deadline=rfq.delivery_deadline,
        status=rfq.status,
        created_at=rfq.created_at,
        expires_at=rfq.expires_at,
        offer_count=0
    )

@router.get("/rfqs", response_model=List[RFQResponse])
def list_rfqs(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, FULFILLED, etc.)"),
    variety: Optional[str] = Query(None, description="Filter by variety"),
    user_id: Optional[int] = Query(None, description="Filter by buyer (user_id)"),
    limit: int = Query(50, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    List RFQs (public marketplace view for cooperatives)
    
    **Access:** Any authenticated user
    
    **Filters:**
    - status: OPEN, PARTIALLY_FILLED, FULFILLED, CANCELLED
    - variety: Coffee variety
    - user_id: Buyer's user ID
    """
    query = db.query(RFQ)
    
    if status:
        query = query.filter(RFQ.status == status)
    if variety:
        query = query.filter(RFQ.variety == variety)
    if user_id:
        query = query.filter(RFQ.buyer_id == user_id)
    
    rfqs = query.order_by(RFQ.created_at.desc()).limit(limit).all()
    
    results = []
    for rfq in rfqs:
        buyer_org = db.query(Organization).filter_by(
            id=db.query(UserIdentity).filter_by(id=rfq.buyer_id).first().organization_id
        ).first()
        
        offer_count = db.query(RFQOffer).filter_by(rfq_id=rfq.id).count()
        
        results.append(RFQResponse(
            id=rfq.id,
            rfq_number=rfq.rfq_number,
            buyer_id=rfq.buyer_id,
            buyer_organization=buyer_org.name if buyer_org else "Unknown",
            quantity_kg=rfq.quantity_kg,
            variety=rfq.variety,
            processing_method=rfq.processing_method,
            grade=rfq.grade,
            delivery_location=rfq.delivery_location,
            delivery_deadline=rfq.delivery_deadline,
            status=rfq.status,
            created_at=rfq.created_at,
            expires_at=rfq.expires_at,
            offer_count=offer_count
        ))
    
    return results

@router.post("/rfq/{rfq_id}/offer", response_model=OfferResponse, status_code=201)
def create_offer(
    rfq_id: int,
    offer_data: OfferCreate,
    user_id: int = Query(..., description="User ID (cooperative manager)"),
    db: Session = Depends(get_db)
):
    """
    Submit offer for an RFQ
    
    **Access:** COOPERATIVE_MANAGER role only
    
    **Workflow:**
    1. Validate user is COOPERATIVE_MANAGER
    2. Verify RFQ exists and is OPEN
    3. Create offer
    4. Update broadcast record (responded_at)
    5. Return offer details
    """
    # Get user
    user = get_current_user(user_id, db)
    
    # Verify user is COOPERATIVE_MANAGER
    if user.role != "COOPERATIVE_MANAGER":
        raise HTTPException(
            status_code=403,
            detail="Only cooperative managers can submit offers"
        )
    
    # Get RFQ
    rfq = db.query(RFQ).filter_by(id=rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    if rfq.status != "OPEN":
        raise HTTPException(status_code=400, detail="RFQ is not open for offers")
    
    # Generate offer number
    offer_number = generate_offer_number(db)
    
    # Create offer
    offer = RFQOffer(
        rfq_id=rfq.id,
        cooperative_id=user.organization_id,
        offer_number=offer_number,
        quantity_offered_kg=offer_data.quantity_offered_kg,
        price_per_kg=offer_data.price_per_kg,
        delivery_timeline=offer_data.delivery_timeline,
        quality_certifications=offer_data.quality_certifications,
        sample_photos=offer_data.sample_photos,
        voice_pitch_url=offer_data.voice_pitch_url,
        status="PENDING"
    )
    db.add(offer)
    
    # Update broadcast record
    broadcast = db.query(RFQBroadcast).filter_by(
        rfq_id=rfq.id,
        cooperative_id=user.organization_id
    ).first()
    if broadcast:
        broadcast.responded_at = datetime.utcnow()
    
    db.commit()
    db.refresh(offer)
    
    # Get cooperative name
    coop_org = db.query(Organization).filter_by(id=user.organization_id).first()
    
    return OfferResponse(
        id=offer.id,
        offer_number=offer.offer_number,
        rfq_id=offer.rfq_id,
        cooperative_id=offer.cooperative_id,
        cooperative_name=coop_org.name if coop_org else "Unknown",
        quantity_offered_kg=offer.quantity_offered_kg,
        price_per_kg=offer.price_per_kg,
        delivery_timeline=offer.delivery_timeline,
        status=offer.status,
        created_at=offer.created_at
    )

@router.get("/rfq/{rfq_id}/offers", response_model=List[OfferResponse])
def get_rfq_offers(
    rfq_id: int,
    user_id: int = Query(..., description="User ID (buyer to view their RFQ offers)"),
    db: Session = Depends(get_db)
):
    """
    View offers for an RFQ
    
    **Access:** Buyer who created the RFQ
    """
    # Get user
    user = get_current_user(user_id, db)
    
    # Get RFQ
    rfq = db.query(RFQ).filter_by(id=rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Verify user owns this RFQ
    if rfq.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view these offers")
    
    # Get offers
    offers = db.query(RFQOffer).filter_by(rfq_id=rfq_id).order_by(RFQOffer.created_at.desc()).all()
    
    results = []
    for offer in offers:
        coop_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
        results.append(OfferResponse(
            id=offer.id,
            offer_number=offer.offer_number,
            rfq_id=offer.rfq_id,
            cooperative_id=offer.cooperative_id,
            cooperative_name=coop_org.name if coop_org else "Unknown",
            quantity_offered_kg=offer.quantity_offered_kg,
            price_per_kg=offer.price_per_kg,
            delivery_timeline=offer.delivery_timeline,
            status=offer.status,
            created_at=offer.created_at
        ))
    
    return results

@router.post("/rfq/{rfq_id}/accept", response_model=AcceptanceResponse, status_code=201)
def accept_offer(
    rfq_id: int,
    acceptance: AcceptOfferRequest,
    user_id: int = Query(..., description="User ID (buyer)"),
    db: Session = Depends(get_db)
):
    """
    Accept an offer for an RFQ
    
    **Access:** Buyer who created the RFQ
    
    **Workflow:**
    1. Validate buyer owns RFQ
    2. Validate offer exists and is PENDING
    3. Create acceptance record
    4. Update offer status to ACCEPTED
    5. Update RFQ status (PARTIALLY_FILLED or FULFILLED)
    6. Return acceptance details
    """
    # Get user
    user = get_current_user(user_id, db)
    
    # Get RFQ
    rfq = db.query(RFQ).filter_by(id=rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Verify user owns this RFQ
    if rfq.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to accept offers for this RFQ")
    
    # Get offer
    offer = db.query(RFQOffer).filter_by(id=acceptance.offer_id, rfq_id=rfq_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    if offer.status != "PENDING":
        raise HTTPException(status_code=400, detail="Offer is not available for acceptance")
    
    # Validate quantity
    if acceptance.quantity_accepted_kg > offer.quantity_offered_kg:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept more than offered quantity ({offer.quantity_offered_kg} kg)"
        )
    
    # Generate acceptance number
    acceptance_number = generate_acceptance_number(db)
    
    # Create acceptance
    acceptance_record = RFQAcceptance(
        rfq_id=rfq.id,
        offer_id=offer.id,
        acceptance_number=acceptance_number,
        quantity_accepted_kg=acceptance.quantity_accepted_kg,
        payment_terms=acceptance.payment_terms,
        payment_status="PENDING",
        delivery_status="PENDING",
        accepted_at=datetime.utcnow()
    )
    db.add(acceptance_record)
    
    # Update offer status
    offer.status = "ACCEPTED"
    
    # Update RFQ status
    total_accepted = db.query(RFQAcceptance).filter_by(rfq_id=rfq.id).count()
    if acceptance.quantity_accepted_kg >= rfq.quantity_kg:
        rfq.status = "FULFILLED"
    else:
        rfq.status = "PARTIALLY_FILLED"
    
    db.commit()
    db.refresh(acceptance_record)
    
    return AcceptanceResponse(
        id=acceptance_record.id,
        acceptance_number=acceptance_record.acceptance_number,
        rfq_id=acceptance_record.rfq_id,
        offer_id=acceptance_record.offer_id,
        quantity_accepted_kg=acceptance_record.quantity_accepted_kg,
        payment_status=acceptance_record.payment_status,
        delivery_status=acceptance_record.delivery_status,
        accepted_at=acceptance_record.accepted_at
    )

@router.get("/offers", response_model=List[OfferResponse])
def list_my_offers(
    user_id: int = Query(..., description="User ID (cooperative manager)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    List my offers (cooperative manager view)
    
    **Access:** COOPERATIVE_MANAGER role
    """
    # Get user
    user = get_current_user(user_id, db)
    
    if user.role != "COOPERATIVE_MANAGER":
        raise HTTPException(status_code=403, detail="Only cooperative managers can view offers")
    
    query = db.query(RFQOffer).filter_by(cooperative_id=user.organization_id)
    
    if status:
        query = query.filter(RFQOffer.status == status)
    
    offers = query.order_by(RFQOffer.created_at.desc()).all()
    
    results = []
    for offer in offers:
        coop_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
        results.append(OfferResponse(
            id=offer.id,
            offer_number=offer.offer_number,
            rfq_id=offer.rfq_id,
            cooperative_id=offer.cooperative_id,
            cooperative_name=coop_org.name if coop_org else "Unknown",
            quantity_offered_kg=offer.quantity_offered_kg,
            price_per_kg=offer.price_per_kg,
            delivery_timeline=offer.delivery_timeline,
            status=offer.status,
            created_at=offer.created_at
        ))
    
    return results

@router.get("/health")
def marketplace_health():
    """Health check for marketplace API"""
    return {
        "status": "healthy",
        "service": "marketplace-rfq-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }
