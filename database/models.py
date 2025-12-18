"""
SQLAlchemy models for Voice Ledger with Neon Postgres
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
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
    
    # Role and organization (for verification system)
    role = Column(String(50), default='FARMER', index=True)  # FARMER, COOPERATIVE_MANAGER, EXPORTER, BUYER, SYSTEM_ADMIN
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_approved = Column(Boolean, default=True, index=True)
    approved_at = Column(DateTime)
    approved_by_admin_id = Column(Integer)
    
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
    token_id = Column(Integer, unique=True)
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

# Database connection
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

def init_database():
    """Create all tables in Neon."""
    Base.metadata.create_all(engine)
    print("✓ Database tables created in Neon")

if __name__ == "__main__":
    init_database()
