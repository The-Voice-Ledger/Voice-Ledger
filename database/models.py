"""
SQLAlchemy models for Voice Ledger with Neon Postgres
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL")

class Organization(Base):
    """Organizations (cooperatives, exporters, buyers) in the supply chain"""
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)  # COOPERATIVE, EXPORTER, BUYER
    did = Column(String(200), unique=True, nullable=False, index=True)
    encrypted_private_key = Column(Text, nullable=False)  # Organization's private key for signing
    public_key = Column(String(100), nullable=False)
    
    location = Column(String(200))
    region = Column(String(100))
    phone_number = Column(String(20))
    registration_number = Column(String(100))  # Official license/registration
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    metadata_json = Column(JSON)  # Additional fields
    
    # Relationships
    members = relationship("UserIdentity", back_populates="organization")
    verified_batches = relationship("CoffeeBatch", back_populates="verifying_organization")
    farmer_relationships = relationship("FarmerCooperative", back_populates="cooperative")

class UserIdentity(Base):
    """Telegram user identity with auto-generated DIDs for batch ownership tracking"""
    __tablename__ = "user_identities"
    
    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(String(50), unique=True, nullable=False, index=True)
    telegram_username = Column(String(100))
    telegram_first_name = Column(String(100))
    telegram_last_name = Column(String(100))
    
    # Auto-generated DID for user authentication
    did = Column(String(200), unique=True, nullable=False, index=True)
    encrypted_private_key = Column(Text, nullable=False)
    public_key = Column(String(100), nullable=False)
    
    # GS1 Global Location Number for user's location
    gln = Column(String(13), nullable=True, index=True)
    
    # Phone number for IVR authentication (E.164 format: +251912345678)
    phone_number = Column(String(20), nullable=True, unique=True, index=True)
    phone_verified_at = Column(DateTime)  # When phone was verified via Telegram contact share
    
    # Role and organization (for verification system)
    role = Column(String(50), default='FARMER', index=True)  # FARMER, COOPERATIVE_MANAGER, EXPORTER, BUYER, SYSTEM_ADMIN
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_approved = Column(Boolean, default=True, index=True)
    approved_at = Column(DateTime)
    approved_by_admin_id = Column(Integer)
    
    # Language preference for conversational AI
    preferred_language = Column(String(2), default='en', nullable=False, index=True)  # 'en' or 'am'
    language_set_at = Column(DateTime, default=datetime.utcnow)
    
    # PIN authentication for web UI (v1.7 - Phase 3: PIN Setup Integration)
    pin_hash = Column(String(255))  # Bcrypt hash of 4-digit PIN
    pin_salt = Column(String(255))  # Salt (bcrypt includes salt, kept for compatibility)
    pin_set_at = Column(DateTime)  # When PIN was last set/changed
    failed_login_attempts = Column(Integer, default=0)  # Consecutive failed PIN attempts
    locked_until = Column(DateTime)  # Account locked until this timestamp (NULL if not locked)
    last_login_at = Column(DateTime)  # Last successful PIN login
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    created_batches = relationship("CoffeeBatch", back_populates="creator", foreign_keys="CoffeeBatch.created_by_user_id")
    organization = relationship("Organization", back_populates="members")
    cooperative_relationships = relationship("FarmerCooperative", back_populates="farmer")

class PendingRegistration(Base):
    """Pending registration requests for non-farmer roles"""
    __tablename__ = "pending_registrations"
    
    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    telegram_username = Column(String(100))
    telegram_first_name = Column(String(100))
    telegram_last_name = Column(String(100))
    
    requested_role = Column(String(50), nullable=False)  # COOPERATIVE_MANAGER, EXPORTER, BUYER
    
    # Common registration form answers
    full_name = Column(String(200), nullable=False)
    organization_name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False)
    phone_number = Column(String(20), nullable=False)
    registration_number = Column(String(100))
    reason = Column(Text)
    
    # Exporter-specific fields
    export_license = Column(String(100))
    port_access = Column(String(100))
    shipping_capacity_tons = Column(Float)
    
    # Buyer-specific fields
    business_type = Column(String(50))  # ROASTER, IMPORTER, WHOLESALER, etc.
    country = Column(String(100))
    target_volume_tons_annual = Column(Float)
    quality_preferences = Column(JSON)
    
    # PIN authentication (v1.7 - Phase 3: Collected during registration, copied to UserIdentity on approval)
    pin_hash = Column(String(255))  # Bcrypt hash of 4-digit PIN
    pin_salt = Column(String(255))  # Salt for PIN
    
    status = Column(String(20), default='PENDING', index=True)  # PENDING, APPROVED, REJECTED
    reviewed_by_admin_id = Column(Integer)
    reviewed_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class FarmerCooperative(Base):
    """Many-to-many relationship between farmers and cooperatives"""
    __tablename__ = "farmer_cooperatives"
    
    id = Column(Integer, primary_key=True)
    farmer_id = Column(Integer, ForeignKey("user_identities.id"), nullable=False, index=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    first_delivery_date = Column(DateTime, nullable=False)
    total_batches_verified = Column(Integer, default=1)
    total_quantity_verified_kg = Column(Float, default=0)
    
    status = Column(String(20), default='ACTIVE', index=True)  # ACTIVE, SUSPENDED, TERMINATED
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farmer = relationship("UserIdentity", back_populates="cooperative_relationships")
    cooperative = relationship("Organization", back_populates="farmer_relationships")

class FarmerIdentity(Base):
    __tablename__ = "farmer_identities"
    
    id = Column(Integer, primary_key=True)
    farmer_id = Column(String(50), unique=True, nullable=False, index=True)
    did = Column(String(200), unique=True, nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    public_key = Column(String(100), nullable=False)
    name = Column(String(200))
    phone_number = Column(String(20))
    location = Column(String(200))
    gln = Column(String(13))  # Global Location Number
    
    # EUDR-required geolocation fields
    latitude = Column(Float)  # Required for plot-level traceability
    longitude = Column(Float)  # Required for plot-level traceability
    region = Column(String(100))  # State/province/region
    country_code = Column(String(2))  # ISO 3166-1 alpha-2 code
    farm_size_hectares = Column(Float)  # Farm size for EUDR compliance
    certification_status = Column(String(100))  # e.g., 'Organic', 'Fair Trade', 'Rainforest Alliance'
    
    # GPS-verified photo fields (EUDR Article 9 compliance)
    farm_photo_url = Column(String(500))  # Telegram file URL or IPFS gateway
    farm_photo_hash = Column(String(64))  # SHA-256 hash for blockchain anchoring
    farm_photo_ipfs = Column(String(100))  # IPFS CID for decentralized storage
    photo_latitude = Column(Float)  # GPS extracted from photo EXIF
    photo_longitude = Column(Float)  # GPS extracted from photo EXIF
    photo_timestamp = Column(DateTime)  # When photo was taken (from EXIF)
    gps_verified_at = Column(DateTime)  # When GPS was verified
    photo_device_make = Column(String(100))  # Camera/phone manufacturer
    photo_device_model = Column(String(100))  # Device model
    blockchain_proof_hash = Column(String(66))  # Transaction hash of blockchain proof
    
    # Deforestation check fields (EUDR Article 10 compliance)
    deforestation_checked_at = Column(DateTime)  # When deforestation check was performed
    deforestation_risk = Column(String(20))  # LOW, MEDIUM, HIGH, UNKNOWN
    deforestation_compliant = Column(Boolean)  # True if no deforestation detected
    tree_cover_loss_hectares = Column(Float)  # Hectares of tree cover lost after Dec 31, 2020
    deforestation_data_source = Column(String(200))  # e.g., "Global Forest Watch - UMD"
    deforestation_confidence = Column(Float)  # Confidence score (0.0 to 1.0)
    deforestation_details = Column(JSON)  # Detailed results from satellite analysis
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    batches = relationship("CoffeeBatch", back_populates="farmer")
    events = relationship("EPCISEvent", back_populates="submitter")
    credentials = relationship("VerifiableCredential", back_populates="farmer")

class CoffeeBatch(Base):
    __tablename__ = "coffee_batches"
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(50), unique=True, nullable=False, index=True)
    gtin = Column(String(14), unique=True, nullable=False, index=True)
    gln = Column(String(13), nullable=True, index=True)  # Global Location Number
    batch_number = Column(String(50), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    origin = Column(String(200))  # Generic origin field (kept for compatibility)
    
    # EUDR-compliant origin fields
    origin_country = Column(String(2))  # ISO 3166-1 alpha-2
    origin_region = Column(String(100))  # State/province
    farm_name = Column(String(200))  # Farm name
    
    variety = Column(String(100))
    harvest_date = Column(DateTime)
    processing_method = Column(String(50))
    process_method = Column(String(50))  # Alias for DPP compatibility
    quality_grade = Column(String(20))
    farmer_id = Column(Integer, ForeignKey("farmer_identities.id"))
    
    # Blockchain token tracking (v1.6 - Dec 2025)
    token_id = Column(BigInteger, nullable=True, index=True)  # ERC-1155 token ID on CoffeeBatchToken contract
    
    # User ownership tracking (for Telegram user who created the batch)
    created_by_user_id = Column(Integer, ForeignKey("user_identities.id"))
    created_by_did = Column(String(200), index=True)  # Denormalized for fast queries
    
    # Verification system fields
    status = Column(String(30), default='PENDING_VERIFICATION', index=True)  # PENDING_VERIFICATION, VERIFIED, REJECTED, EXPIRED
    verification_token = Column(String(64), unique=True, index=True)
    verification_expires_at = Column(DateTime, index=True)
    verification_used = Column(Boolean, default=False)
    verified_quantity = Column(Float)  # Actual quantity verified (may differ from claimed)
    verified_by_did = Column(String(200), index=True)
    verified_at = Column(DateTime)
    verification_notes = Column(Text)
    has_photo_evidence = Column(Boolean, default=False)
    verifying_organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    
    # Quality assessment fields (populated during cooperative verification)
    cupping_score = Column(Float, nullable=True)       # SCA protocol, 0-100
    moisture_pct = Column(Float, nullable=True)         # Moisture %, ideal 10-12
    screen_size = Column(String(20), nullable=True)     # e.g. "15+", "14-16"
    defect_count = Column(Integer, nullable=True)       # Total defects per 350g sample
    defect_category = Column(String(20), nullable=True) # SCA Category 1 / Category 2 / None
    sensory_notes = Column(JSON, nullable=True)         # {aroma, acidity, body, flavor, aftertaste, balance, ...}
    
    qr_code_base64 = Column(Text, nullable=True)  # Base64 encoded PNG of DPP QR code
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farmer = relationship("FarmerIdentity", back_populates="batches")
    creator = relationship("UserIdentity", back_populates="created_batches", foreign_keys=[created_by_user_id])
    events = relationship("EPCISEvent", back_populates="batch")
    verifying_organization = relationship("Organization", back_populates="verified_batches")
    evidence = relationship("VerificationEvidence", back_populates="batch")

class VerificationEvidence(Base):
    """Photo and document evidence for batch verification"""
    __tablename__ = "verification_evidence"
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("coffee_batches.id"), nullable=False, index=True)
    evidence_type = Column(String(50), nullable=False, index=True)  # PHOTO, DOCUMENT, GPS, WEIGHING_SLIP, OTHER
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash
    storage_url = Column(String(500), nullable=False)  # S3/Spaces URL
    captured_by_did = Column(String(200), nullable=False)
    captured_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json = Column(JSON)  # Additional data (filename, GPS, etc.)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    batch = relationship("CoffeeBatch", back_populates="evidence")

class VerificationPhoto(Base):
    """GPS-verified photos for batch verification (EUDR compliance)"""
    __tablename__ = "verification_photos"
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("coffee_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_url = Column(String(500), nullable=False)
    photo_hash = Column(String(64), nullable=False, unique=True, index=True)
    photo_ipfs = Column(String(100))  # IPFS CID
    latitude = Column(Float)
    longitude = Column(Float)
    photo_timestamp = Column(DateTime)
    device_make = Column(String(100))
    device_model = Column(String(100))
    verified_at = Column(DateTime, default=datetime.utcnow)
    distance_from_farm_km = Column(Float)  # Distance from registered farm location
    blockchain_proof_hash = Column(String(66))  # Transaction hash
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    batch = relationship("CoffeeBatch", backref="verification_photos")

class EPCISEvent(Base):
    __tablename__ = "epcis_events"
    
    id = Column(Integer, primary_key=True)
    event_hash = Column(String(64), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # ObjectEvent, TransformationEvent
    canonical_nquads = Column(Text, nullable=False)  # Full canonical form
    event_json = Column(JSON, nullable=False)        # Original EPCIS JSON-LD
    ipfs_cid = Column(String(100))                   # Link to IPFS storage
    blockchain_tx_hash = Column(String(66))          # Ethereum TX hash
    blockchain_confirmed = Column(Boolean, default=False)
    blockchain_confirmed_at = Column(DateTime)       # When blockchain anchor was confirmed
    
    # EPCIS fields for fast querying
    event_time = Column(DateTime, nullable=False, index=True)
    biz_step = Column(String(100), index=True)       # harvesting, processing, shipping
    biz_location = Column(String(100))               # GLN of farm/warehouse
    
    # Foreign keys
    batch_id = Column(Integer, ForeignKey("coffee_batches.id"))
    submitter_id = Column(Integer, ForeignKey("farmer_identities.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    batch = relationship("CoffeeBatch", back_populates="events")
    submitter = relationship("FarmerIdentity", back_populates="events")

class VerifiableCredential(Base):
    __tablename__ = "verifiable_credentials"
    
    id = Column(Integer, primary_key=True)
    credential_id = Column(String(200), unique=True, nullable=False, index=True)  # Maps to credential['id']
    credential_type = Column(String(100), nullable=False)  # Extracted from credential['type']
    subject_did = Column(String(200), nullable=False, index=True)  # From credentialSubject
    issuer_did = Column(String(200), nullable=False)  # From credential['issuer']
    issuance_date = Column(DateTime, nullable=False)  # Parsed from credential['issuanceDate']
    expiration_date = Column(DateTime)  # Parsed from credential['expirationDate'] if present
    credential_json = Column(JSON, nullable=False)  # Full W3C credential with 'id', 'type', 'issuer', etc.
    proof = Column(JSON, nullable=False)  # credential['proof']
    
    # Link credential to farmer for easier DPP generation
    farmer_id = Column(Integer, ForeignKey("farmer_identities.id"))
    
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    farmer = relationship("FarmerIdentity", back_populates="credentials")

class Exporter(Base):
    """Exporter-specific details for organizations"""
    __tablename__ = "exporters"
    
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), unique=True, nullable=False, index=True)
    export_license = Column(String(100), nullable=False)
    port_access = Column(String(100))  # Primary port (Djibouti, Berbera, Mombasa)
    shipping_capacity_tons = Column(Float)
    active_shipping_lines = Column(JSON)  # Array of shipping line names
    customs_clearance_capability = Column(Boolean, default=False)
    certifications = Column(JSON)  # Array of certifications
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id])

class Buyer(Base):
    """Buyer-specific details for organizations"""
    __tablename__ = "buyers"
    
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), unique=True, nullable=False, index=True)
    business_type = Column(String(50), nullable=False, index=True)  # ROASTER, IMPORTER, WHOLESALER, RETAILER, CAFE_CHAIN
    country = Column(String(100), nullable=False, index=True)
    target_volume_tons_annual = Column(Float)
    quality_preferences = Column(JSON)  # {min_cup_score: 85, certifications: ['organic']}
    payment_terms = Column(String(50))  # NET30, NET60, LC, PREPAY
    import_licenses = Column(JSON)  # Array of license numbers
    certifications_required = Column(JSON)  # Array of required certifications
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id])

class UserReputation(Base):
    """Reputation tracking for all users across transactions"""
    __tablename__ = "user_reputation"
    
    user_id = Column(Integer, ForeignKey("user_identities.id"), primary_key=True)
    completed_transactions = Column(Integer, default=0)
    total_volume_kg = Column(Float, default=0)
    on_time_deliveries = Column(Integer, default=0)
    quality_disputes = Column(Integer, default=0)
    average_rating = Column(Float)  # 0.00 to 5.00
    reputation_level = Column(String(20), default='BRONZE', index=True)  # BRONZE, SILVER, GOLD, PLATINUM
    last_transaction_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("UserIdentity", foreign_keys=[user_id])

class OfflineQueue(Base):
    __tablename__ = "offline_queue"
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(100), nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)  # "submit_event", "mint_batch"
    payload = Column(JSON, nullable=False)
    status = Column(String(20), default="pending", index=True)  # pending, syncing, completed, failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    synced_at = Column(DateTime)
    error_message = Column(Text)

class AggregationRelationship(Base):
    """Parent-child relationships for EPCIS AggregationEvents"""
    __tablename__ = "aggregation_relationships"
    
    id = Column(Integer, primary_key=True)
    parent_sscc = Column(String(18), nullable=False, index=True)
    child_identifier = Column(String(100), nullable=False, index=True)
    child_type = Column(String(20), nullable=False)  # 'batch', 'sscc', 'pallet'
    contribution_kg = Column(Float)  # Quantity contributed from child (for partial aggregation)
    
    aggregation_event_id = Column(Integer, ForeignKey("epcis_events.id"))
    disaggregation_event_id = Column(Integer, ForeignKey("epcis_events.id"))
    
    # Blockchain token tracking (v1.6 - Phase 2: Container minting)
    container_token_id = Column(BigInteger, nullable=True, index=True)  # ERC-1155 container token ID
    
    aggregated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    disaggregated_at = Column(DateTime)
    is_active = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    aggregation_event = relationship("EPCISEvent", foreign_keys=[aggregation_event_id])
    disaggregation_event = relationship("EPCISEvent", foreign_keys=[disaggregation_event_id])

class ProductFarmerLineage(Base):
    """Materialized view for fast farmer lineage queries across aggregations"""
    __tablename__ = "product_farmer_lineage"
    __table_args__ = {'info': {'is_view': True}}  # Mark as view, not a regular table
    
    product_id = Column(String(100), primary_key=True)
    farmer_id = Column(Integer, primary_key=True)
    farmer_identifier = Column(String(50))
    farmer_name = Column(String(200))
    farmer_did = Column(String(200))
    total_contribution_kg = Column(Float)
    origin_region = Column(String(100))
    origin_country = Column(String(2))
    latitude = Column(Float)
    longitude = Column(Float)
    max_depth = Column(Integer)

class RFQ(Base):
    """Buyer requests for quotes (Lab 14 - RFQ Marketplace)"""
    __tablename__ = "rfqs"
    
    id = Column(Integer, primary_key=True)
    buyer_id = Column(Integer, ForeignKey("user_identities.id"), nullable=False, index=True)
    rfq_number = Column(String(20), unique=True, nullable=False, index=True)
    
    # Requirements
    quantity_kg = Column(Float, nullable=False)
    variety = Column(String(100))
    processing_method = Column(String(50))
    grade = Column(String(20))
    delivery_location = Column(String(200))
    delivery_deadline = Column(DateTime)
    additional_specs = Column(JSON)
    
    # Status
    status = Column(String(20), default='OPEN', nullable=False, index=True)
    
    # Voice/text
    voice_recording_url = Column(Text)
    transcript = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    buyer = relationship("UserIdentity", foreign_keys=[buyer_id])
    offers = relationship("RFQOffer", back_populates="rfq")
    acceptances = relationship("RFQAcceptance", back_populates="rfq")
    broadcasts = relationship("RFQBroadcast", back_populates="rfq")

class RFQOffer(Base):
    """Cooperative offers in response to RFQs (Lab 14 - RFQ Marketplace)"""
    __tablename__ = "rfq_offers"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    offer_number = Column(String(20), unique=True, nullable=False, index=True)
    
    # Offer details
    quantity_offered_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    delivery_timeline = Column(String(100))
    quality_certifications = Column(JSON)
    sample_photos = Column(ARRAY(Text))  # Array of URLs
    voice_pitch_url = Column(Text)
    
    # Status
    status = Column(String(20), default='PENDING', nullable=False, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="offers")
    cooperative = relationship("Organization", foreign_keys=[cooperative_id])
    acceptances = relationship("RFQAcceptance", back_populates="offer")

class ContainerOffering(Base):
    """Container offerings for fractional sale (Phase 4.5 - Fractional Ownership)"""
    __tablename__ = "container_offerings"
    
    id = Column(Integer, primary_key=True)
    container_sscc = Column(String(18), nullable=False, index=True)
    aggregation_id = Column(Integer, ForeignKey("aggregation_relationships.id"), nullable=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Quantity tracking
    total_quantity_kg = Column(Float, nullable=False)
    available_quantity_kg = Column(Float, nullable=False)
    reserved_quantity_kg = Column(Float, default=0)
    
    # Pricing
    price_per_kg = Column(Float, nullable=False)
    currency = Column(String(3), default='USD')
    
    # Status: AVAILABLE, PARTIALLY_SOLD, FULLY_RESERVED, SOLD_OUT, EXPIRED
    status = Column(String(20), default='AVAILABLE', index=True)
    
    # Product details
    variety = Column(String(100))
    processing_method = Column(String(50))
    grade = Column(String(20))
    certifications = Column(JSON)
    
    # Delivery info
    delivery_location = Column(String(200))
    earliest_delivery_date = Column(DateTime)
    latest_delivery_date = Column(DateTime)
    
    # Marketing
    description = Column(Text)
    sample_photos = Column(JSON)  # List of photo URLs
    dpp_url = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)
    
    # Relationships
    cooperative = relationship("Organization", foreign_keys=[cooperative_id])
    purchases = relationship("RFQAcceptance", back_populates="container_offering")
    
    @property
    def sold_quantity_kg(self) -> float:
        """Quantity that has been sold (total - available - reserved)."""
        return max(0, self.total_quantity_kg - self.available_quantity_kg - self.reserved_quantity_kg)
    
    @property
    def fill_percentage(self) -> float:
        """Percentage of container that has been sold or reserved."""
        if self.total_quantity_kg == 0:
            return 0.0
        return round((1 - self.available_quantity_kg / self.total_quantity_kg) * 100, 1)
    
    @property
    def total_value_usd(self) -> float:
        """Total value of the container."""
        return round(self.total_quantity_kg * self.price_per_kg, 2)


class RFQAcceptance(Base):
    """Buyer acceptances of cooperative offers (Lab 14 - RFQ Marketplace)"""
    __tablename__ = "rfq_acceptances"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=True, index=True)
    offer_id = Column(Integer, ForeignKey("rfq_offers.id"), nullable=True, index=True)
    container_offering_id = Column(Integer, ForeignKey("container_offerings.id"), nullable=True, index=True)
    acceptance_number = Column(String(20), unique=True, nullable=False)
    
    # Acceptance details
    quantity_accepted_kg = Column(Float, nullable=False)
    payment_terms = Column(String(50))
    payment_status = Column(String(20), default='PENDING', index=True)
    delivery_status = Column(String(20), default='PENDING', index=True)
    
    # Payment coordination
    payment_method = Column(String(30), nullable=True)            # BANK_TRANSFER
    payment_receipt_url = Column(String(500), nullable=True)      # Photo of bank receipt
    payment_confirmed_by_buyer_at = Column(DateTime, nullable=True)
    payment_received_by_coop_at = Column(DateTime, nullable=True)
    payment_dispute_reason = Column(Text, nullable=True)
    payment_disputed_at = Column(DateTime, nullable=True)

    # Blockchain settlement - buyer payment leg
    settlement_tx_hash = Column(String(66), nullable=True)
    settlement_recorded_at = Column(DateTime, nullable=True)
    settlement_blockchain_confirmed = Column(Boolean, default=False)

    # Blockchain settlement - cooperative payout leg
    coop_payout_tx_hash = Column(String(66), nullable=True)
    coop_payout_at = Column(DateTime, nullable=True)
    coop_payout_confirmed = Column(Boolean, default=False)

    # Metadata
    accepted_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime)
    payment_released_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="acceptances")
    offer = relationship("RFQOffer", back_populates="acceptances")
    container_offering = relationship("ContainerOffering", back_populates="purchases")

class RFQBroadcast(Base):
    """Tracks which cooperatives were notified about each RFQ (Lab 14 - RFQ Marketplace)"""
    __tablename__ = "rfq_broadcasts"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Matching details
    broadcast_reason = Column(String(100))
    relevance_score = Column(Float)
    
    # Engagement tracking
    notified_at = Column(DateTime, default=datetime.utcnow)
    viewed_at = Column(DateTime)
    responded_at = Column(DateTime)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="broadcasts")
    cooperative = relationship("Organization", foreign_keys=[cooperative_id])


# ======================================================================
# Container Pool & Buyer Commitment  (Phase 4.6 - Shared Container Buying)
# ======================================================================

# Port-region mapping: buyer country  →  destination port  →  pool region
REGION_PORT_MAP = {
    # Benelux
    "NL": ("Rotterdam", "Benelux"),
    "BE": ("Rotterdam", "Benelux"),
    "LU": ("Rotterdam", "Benelux"),
    # DACH
    "DE": ("Hamburg", "DACH"),
    "AT": ("Hamburg", "DACH"),
    "CH": ("Hamburg", "DACH"),
    # Mediterranean
    "FR": ("Marseille", "Mediterranean"),
    "ES": ("Marseille", "Mediterranean"),
    "PT": ("Marseille", "Mediterranean"),
    "IT": ("Marseille", "Mediterranean"),
    "GR": ("Marseille", "Mediterranean"),
    # Nordic
    "DK": ("Gothenburg", "Nordic"),
    "SE": ("Gothenburg", "Nordic"),
    "NO": ("Gothenburg", "Nordic"),
    "FI": ("Gothenburg", "Nordic"),
    "IS": ("Gothenburg", "Nordic"),
    # British Isles
    "GB": ("Felixstowe", "British Isles"),
    "IE": ("Felixstowe", "British Isles"),
    # Eastern Europe
    "PL": ("Gdansk", "Eastern Europe"),
    "CZ": ("Hamburg", "DACH"),
    "RO": ("Constanta", "Eastern Europe"),
    "HU": ("Hamburg", "DACH"),
    # North America
    "US": ("New York", "North America"),
    "CA": ("Montreal", "North America"),
    # East Asia
    "JP": ("Yokohama", "East Asia"),
    "KR": ("Busan", "East Asia"),
    "CN": ("Shanghai", "East Asia"),
    # Middle East
    "AE": ("Dubai", "Middle East"),
    "SA": ("Jeddah", "Middle East"),
}

# Default fill thresholds
POOL_AUTO_CONFIRM_PCT = 80   # confirm shipment at 80%
POOL_MIN_SHIP_PCT = 60       # ship anyway at deadline if ≥ 60%


class ContainerPool(Base):
    """
    Demand-side aggregation pool for shared container buying.

    Multiple buyers from the same destination region can commit quantities
    into a pool until it reaches the fill threshold and triggers shipment.
    """
    __tablename__ = "container_pools"

    id = Column(Integer, primary_key=True)

    # Supply side
    container_offering_id = Column(
        Integer, ForeignKey("container_offerings.id"), nullable=False, index=True
    )

    # Destination
    destination_region = Column(String(50), nullable=False, index=True)   # "Benelux", "DACH", …
    destination_port = Column(String(100), nullable=False)                # "Rotterdam", "Hamburg", …

    # Quantity tracking
    fill_target_kg = Column(Float, nullable=False)          # usually = offering.total_quantity_kg
    filled_kg = Column(Float, nullable=False, default=0)    # sum of committed quantities

    # Status: FILLING → CONFIRMED → SHIPPED → DELIVERED | CANCELLED
    status = Column(String(20), default="FILLING", nullable=False, index=True)

    # Deadline -- pool ships when full OR when deadline is reached (if ≥ min %)
    deadline = Column(DateTime, nullable=True)

    # Logistics
    estimated_departure = Column(DateTime, nullable=True)
    estimated_arrival = Column(DateTime, nullable=True)
    shipping_reference = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)

    # Relationships
    container_offering = relationship("ContainerOffering", foreign_keys=[container_offering_id])
    commitments = relationship("BuyerCommitment", back_populates="pool", order_by="BuyerCommitment.created_at")

    @property
    def fill_pct(self) -> float:
        if self.fill_target_kg == 0:
            return 0.0
        return round(self.filled_kg / self.fill_target_kg * 100, 1)

    @property
    def remaining_kg(self) -> float:
        return max(0, self.fill_target_kg - self.filled_kg)

    @property
    def buyer_count(self) -> int:
        return len(self.commitments) if self.commitments else 0


class BuyerCommitment(Base):
    """
    A single buyer's fractional commitment within a container pool.
    """
    __tablename__ = "buyer_commitments"

    id = Column(Integer, primary_key=True)

    pool_id = Column(
        Integer, ForeignKey("container_pools.id"), nullable=False, index=True
    )
    buyer_id = Column(
        Integer, ForeignKey("user_identities.id"), nullable=False, index=True
    )
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )

    # Commitment details
    quantity_kg = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)          # $/kg at time of commitment
    total_amount = Column(Float, nullable=False)         # quantity * unit_price
    currency = Column(String(3), default="USD")

    # Delivery
    delivery_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    delivery_city = Column(String(200), nullable=True)
    delivery_address = Column(Text, nullable=True)

    # Status: COMMITTED → PAYMENT_PENDING → PAID → IN_TRANSIT → DELIVERED | CANCELLED
    status = Column(String(20), default="COMMITTED", nullable=False, index=True)

    # Payment tracking
    payment_reference = Column(String(100), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_method = Column(String(30), nullable=True)            # BANK_TRANSFER
    payment_receipt_url = Column(String(500), nullable=True)      # Photo of bank receipt
    payment_confirmed_by_buyer_at = Column(DateTime, nullable=True)
    payment_received_by_coop_at = Column(DateTime, nullable=True)
    payment_dispute_reason = Column(Text, nullable=True)
    payment_disputed_at = Column(DateTime, nullable=True)

    # Blockchain settlement - buyer payment leg
    settlement_tx_hash = Column(String(66), nullable=True)
    settlement_recorded_at = Column(DateTime, nullable=True)
    settlement_blockchain_confirmed = Column(Boolean, default=False)

    # Blockchain settlement - cooperative payout leg
    coop_payout_tx_hash = Column(String(66), nullable=True)
    coop_payout_at = Column(DateTime, nullable=True)
    coop_payout_confirmed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pool = relationship("ContainerPool", back_populates="commitments")
    buyer = relationship("UserIdentity", foreign_keys=[buyer_id])
    organization = relationship("Organization", foreign_keys=[organization_id])

class UATIssue(Base):
    """UAT issue reports submitted via the floating bug-reporter widget."""
    __tablename__ = "uat_issues"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_identities.id", ondelete="SET NULL"), nullable=True, index=True)
    user_name = Column(String(128), nullable=False, default="")
    user_phone = Column(String(20), nullable=False, default="")

    page = Column(String(128), nullable=False)
    # category: bug | data | feature | performance | other
    category = Column(String(32), nullable=False, default="bug")
    # severity: blocker | major | minor | cosmetic
    severity = Column(String(16), nullable=False, default="minor")

    title = Column(String(256), nullable=False, default="")
    description = Column(Text, nullable=False, default="")

    context_json = Column(JSON, nullable=False, default=dict)
    browser_info = Column(String(512), nullable=False, default="")
    console_errors = Column(JSON, nullable=False, default=list)

    # status: open | in_progress | fixed | verified | wont_fix
    status = Column(String(20), nullable=False, default="open", index=True)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Relationship
    reporter = relationship("UserIdentity", foreign_keys=[user_id])


# Database connection
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(bind=engine)

def init_database():
    """Create all tables in Neon."""
    Base.metadata.create_all(engine)
    print("✓ Database tables created in Neon")

if __name__ == "__main__":
    init_database()
