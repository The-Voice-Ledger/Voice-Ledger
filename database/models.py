"""
SQLAlchemy models for Voice Ledger with Neon Postgres
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL")

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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    created_batches = relationship("CoffeeBatch", back_populates="creator", foreign_keys="CoffeeBatch.created_by_user_id")

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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farmer = relationship("FarmerIdentity", back_populates="batches")
    creator = relationship("UserIdentity", back_populates="created_batches", foreign_keys=[created_by_user_id])
    events = relationship("EPCISEvent", back_populates="batch")

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
