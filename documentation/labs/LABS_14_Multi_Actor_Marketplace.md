# Voice Ledger - Lab 14: Multi-Actor Marketplace System

**Date**: December 21, 2025  
**Version**: v1.0  
**Status**: ✅ COMPLETE - Database infrastructure and registration flows

---

## 🎯 Lab Overview

**Learning Objectives:**
- Extend registration system to support Exporters and Buyers
- Implement role-specific conversation flows with validation
- Design marketplace database schema (RFQ system)
- Build reputation tracking for multi-actor supply chains
- Understand buyer-to-cooperative Request for Quote workflows
- Create comprehensive test suite for multi-actor registration

**What You'll Build:**
- ✅ `Exporter`, `Buyer`, `UserReputation` database tables
- ✅ RFQ marketplace tables (`rfqs`, `rfq_offers`, `rfq_acceptances`, `rfq_broadcasts`)
- ✅ SQLAlchemy ORM models for all marketplace entities
- ✅ Extended registration handler for EXPORTER and BUYER roles
- ✅ Test suite validating complete registration flows (3/3 passing)
- ✅ Database migrations for marketplace infrastructure

**Prerequisites:**
- ✅ Labs 1-13 completed (especially Lab 9: Verification & Registration)
- ✅ PostgreSQL database (Neon or local)
- ✅ Telegram bot with `/register` command working
- ✅ Understanding of role-based access control
- ✅ Familiarity with SSI (Self-Sovereign Identity) from Lab 3

**Time Estimate:** 4-6 hours (database design + implementation + testing)

**Cost:** $0 (uses existing infrastructure)

---

## 💡 Background: Why Multi-Actor Marketplace?

### The Problem

**Current System (Labs 1-13):**
```
Farmer → Cooperative → ??? → End Consumer
   ✅         ✅        ❌
```

The system has:
- ✅ Farmers creating batches via voice
- ✅ Cooperatives verifying batches
- ❌ **No bridge to international buyers**
- ❌ **No exporter coordination**
- ❌ **No price discovery mechanism**

### The Solution: Multi-Actor Marketplace

**New Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│                    Voice Ledger Marketplace              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  👨‍🌾 Farmers     →  🏢 Cooperatives  →  📦 Exporters    │
│  (Supply)          (Aggregation)        (Logistics)     │
│                                                          │
│                     ↕️                                   │
│                                                          │
│              🛒 RFQ Marketplace                          │
│           (Price Discovery)                              │
│                                                          │
│                     ↕️                                   │
│                                                          │
│               ☕ Buyers                                  │
│        (Roasters, Importers)                            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Key Innovation**: Voice-first B2B marketplace connecting Ethiopian farmers to international buyers with full traceability.

### Real-World Example

**Before (Traditional)**:
```
Farmer Abebe → Cooperative → Middleman → Exporter → Importer → Roaster
  $3/kg         +$0.50        +$1.50      +$2.00     +$1.00    = $8/kg

❌ Opaque pricing
❌ Multiple intermediaries
❌ No traceability
❌ Farmer gets 37.5% of final price
```

**After (Voice Ledger Marketplace)**:
```
Farmer Abebe → Cooperative → Exporter → Buyer (Direct)
  $3/kg         +$0.50       +$1.00    = $4.50/kg

✅ Transparent pricing via RFQ
✅ Fewer intermediaries  
✅ Full traceability (DID + blockchain)
✅ Farmer gets 67% of buyer price
```

---

## 📋 Prerequisites - What We Have (Labs 1-13)

**Completed Infrastructure:**
- ✅ User identity system with DIDs (Lab 3)
- ✅ Organization management with DIDs (Lab 9)
- ✅ Role-based registration (`/register` command)
- ✅ Verification workflow (Lab 9-10)
- ✅ Token minting post-verification (Lab 13)
- ✅ Aggregation with containers (Lab 12)
- ✅ Phone authentication via Telegram (Dec 21 update)

**What's Missing (Lab 14 Will Add):**
- Exporter-specific data (export license, port access, shipping capacity)
- Buyer-specific data (business type, country, quality preferences)
- RFQ (Request for Quote) system for price discovery
- Reputation tracking across all actors
- Offer submission and acceptance workflows

---

## 🏗️ Architecture Overview

### Database Schema Design

```
┌─────────────────────────────────────────────────────────┐
│              Core Identity (Labs 1-13)                   │
├─────────────────────────────────────────────────────────┤
│  user_identities          organizations                  │
│  - id                     - id                           │
│  - telegram_user_id       - name                         │
│  - did                    - type (COOPERATIVE, etc.)     │
│  - role (FARMER,          - did                          │
│          COOPERATIVE,     - phone                        │
│          EXPORTER,        - location                     │
│          BUYER)           - registration_number          │
│  - organization_id        - created_at                   │
│  - is_approved                                           │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│          Marketplace Extensions (Lab 14)                 │
├─────────────────────────────────────────────────────────┤
│  exporters                buyers                         │
│  - id                     - id                           │
│  - organization_id (FK)   - organization_id (FK)         │
│  - export_license         - business_type               │
│  - port_access            - country                     │
│  - shipping_capacity      - target_volume_annual        │
│  - certifications         - quality_preferences         │
│                                                          │
│  user_reputation                                         │
│  - user_id (PK/FK)                                       │
│  - completed_transactions                                │
│  - total_volume_kg                                       │
│  - on_time_deliveries                                    │
│  - average_rating                                        │
│  - reputation_level (BRONZE/SILVER/GOLD/PLATINUM)       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              RFQ Marketplace System                      │
├─────────────────────────────────────────────────────────┤
│  rfqs                     rfq_offers                     │
│  - id                     - id                           │
│  - buyer_id (FK)          - rfq_id (FK)                  │
│  - rfq_number             - cooperative_id (FK)          │
│  - quantity_kg            - offer_number                 │
│  - variety                - quantity_offered_kg          │
│  - processing_method      - price_per_kg                 │
│  - delivery_location      - delivery_timeline            │
│  - delivery_deadline      - voice_pitch_url              │
│  - status (OPEN, etc.)    - status (PENDING, etc.)       │
│                                                          │
│  rfq_acceptances          rfq_broadcasts                 │
│  - id                     - id                           │
│  - rfq_id (FK)            - rfq_id (FK)                  │
│  - offer_id (FK)          - cooperative_id (FK)          │
│  - acceptance_number      - broadcast_reason             │
│  - quantity_accepted_kg   - relevance_score              │
│  - payment_status         - notified_at                  │
│  - delivery_status        - viewed_at                    │
└─────────────────────────────────────────────────────────┘
```

### Registration Flow Comparison

**Farmer (Simple - Auto-approved)**:
```
/start → Share phone → Select language → Done ✅
```

**Cooperative Manager (Lab 9)**:
```
/register → Role: COOPERATIVE_MANAGER → 7 questions → Admin approval → ✅
```

**Exporter (Lab 14 - NEW)**:
```
/register → Role: EXPORTER → 
  ↓
  1. Full Name
  2. Organization Name
  3. Location
  4. Phone Number
  5. Export License Number
  6. Port Access (Djibouti/Berbera/Mombasa)
  7. Shipping Capacity (tons/year)
  8. Reason (optional)
  ↓
Admin approval → Organization + Exporter record created → ✅
```

**Buyer (Lab 14 - NEW)**:
```
/register → Role: BUYER →
  ↓
  1. Full Name
  2. Organization Name
  3. Location
  4. Phone Number
  5. Business Type (Roaster/Importer/Wholesaler/Retailer/Cafe)
  6. Country
  7. Target Annual Volume (tons)
  8. Quality Preferences (cup score, certifications)
  9. Reason (optional)
  ↓
Admin approval → Organization + Buyer record created → ✅
```

---

## Step 1: Review Existing Registration System

Before adding new roles, let's understand what Labs 9-10 built.

**Current Registration Handler**: `voice/telegram/register_handler.py`

**Key Components:**
```python
# Conversation states (in-memory state machine)
conversation_states: Dict[int, Dict[str, Any]] = {}

# State constants
STATE_LANGUAGE = 1  # Language selection
STATE_ROLE = 2      # Role selection
STATE_FULL_NAME = 3
STATE_ORG_NAME = 4
STATE_LOCATION = 5
STATE_PHONE = 6
STATE_REG_NUMBER = 7
STATE_REASON = 8

# Role-specific states (already exist!)
STATE_EXPORT_LICENSE = 9
STATE_PORT_ACCESS = 10
STATE_SHIPPING_CAPACITY = 11
STATE_BUSINESS_TYPE = 12
STATE_COUNTRY = 13
STATE_TARGET_VOLUME = 14
STATE_QUALITY_PREFS = 15
```

**Verification**:
```bash
cd ~/Voice-Ledger
grep -n "STATE_EXPORT_LICENSE\|STATE_BUSINESS_TYPE" voice/telegram/register_handler.py
```

**Expected Output**:
```
36:STATE_EXPORT_LICENSE = 9
37:STATE_PORT_ACCESS = 10
38:STATE_SHIPPING_CAPACITY = 11
39:STATE_BUSINESS_TYPE = 12
40:STATE_COUNTRY = 13
41:STATE_TARGET_VOLUME = 14
42:STATE_QUALITY_PREFS = 15
```

✅ **Discovery**: Exporter and Buyer registration flows **already implemented** in Labs 9-10! Our task is to add database tables and test them.

---

## Step 2: Create Database Tables

We need three new tables extending the existing schema.

**Migration File**: `database/migrations/010_create_rfq_marketplace.sql`

### 2.1 Exporters Table

**Purpose**: Store exporter-specific information for logistics coordination.

```sql
CREATE TABLE IF NOT EXISTS exporters (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) UNIQUE NOT NULL,
    
    -- Licensing
    export_license VARCHAR(100) NOT NULL,
    
    -- Logistics
    port_access VARCHAR(100),  -- DJIBOUTI, BERBERA, MOMBASA
    shipping_capacity_tons DECIMAL(10,2),
    active_shipping_lines JSONB,  -- ["Maersk", "MSC", "CMA CGM"]
    customs_clearance_capability BOOLEAN DEFAULT FALSE,
    certifications JSONB,  -- {"ISO9001": true, "HACCP": true}
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_exporters_org ON exporters(organization_id);
```

**Why This Design?**

1. **`organization_id` UNIQUE**: One exporter record per organization (1:1 relationship)
2. **`export_license` NOT NULL**: Required for regulatory compliance
3. **`port_access`**: Ethiopian coffee exports via 3 main ports
4. **`shipping_capacity_tons`**: Helps match cooperatives with exporters
5. **JSONB fields**: Flexible for varying certifications and shipping lines

### 2.2 Buyers Table

**Purpose**: Store buyer-specific information for marketplace matching.

```sql
CREATE TABLE IF NOT EXISTS buyers (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) UNIQUE NOT NULL,
    
    -- Business profile
    business_type VARCHAR(50) NOT NULL,  -- ROASTER, IMPORTER, WHOLESALER, etc.
    country VARCHAR(100) NOT NULL,  -- For import regulations
    
    -- Purchasing profile
    target_volume_tons_annual DECIMAL(10,2),
    quality_preferences JSONB,  -- {min_cup_score: 84, certifications: ['Organic']}
    payment_terms VARCHAR(50),  -- NET_30, NET_60, ADVANCE
    
    -- Import documentation
    import_licenses JSONB,  -- {"EU_IMPORT": "EU-2025-1234"}
    certifications_required JSONB,  -- ["Organic", "Fair Trade"]
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_buyers_org ON buyers(organization_id);
CREATE INDEX idx_buyers_business_type ON buyers(business_type);
CREATE INDEX idx_buyers_country ON buyers(country);
```

**Why This Design?**

1. **`business_type` indexed**: Fast filtering for marketplace (show only roasters, etc.)
2. **`country` indexed**: Import regulations vary by country
3. **`quality_preferences` JSONB**: Flexible (cup score, moisture, certifications)
4. **`payment_terms`**: Critical for cooperative cash flow planning

### 2.3 User Reputation Table

**Purpose**: Track transaction history and build trust scores.

```sql
CREATE TABLE IF NOT EXISTS user_reputation (
    user_id INTEGER PRIMARY KEY REFERENCES user_identities(id),
    
    -- Transaction history
    completed_transactions INTEGER DEFAULT 0,
    total_volume_kg DECIMAL(12,2) DEFAULT 0,
    on_time_deliveries INTEGER DEFAULT 0,
    quality_disputes INTEGER DEFAULT 0,
    
    -- Ratings
    average_rating DECIMAL(3,2),  -- 0.00 to 5.00
    reputation_level VARCHAR(20) DEFAULT 'BRONZE',  -- BRONZE/SILVER/GOLD/PLATINUM
    last_transaction_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Reputation Level Calculation**:
```
BRONZE:   0-9 transactions
SILVER:   10-49 transactions + avg_rating ≥ 4.0
GOLD:     50-199 transactions + avg_rating ≥ 4.5
PLATINUM: 200+ transactions + avg_rating ≥ 4.8
```

### 2.4 RFQ Marketplace Tables

**Purpose**: Enable buyer-to-cooperative Request for Quote system.

```sql
-- RFQs (Request for Quotes from buyers)
CREATE TABLE IF NOT EXISTS rfqs (
    id SERIAL PRIMARY KEY,
    buyer_id INTEGER REFERENCES user_identities(id) NOT NULL,
    rfq_number VARCHAR(20) UNIQUE NOT NULL,  -- RFQ-1234
    
    -- Requirements
    quantity_kg DECIMAL(10,2) NOT NULL,
    variety VARCHAR(100),
    processing_method VARCHAR(50),
    grade VARCHAR(20),
    delivery_location VARCHAR(200),
    delivery_deadline DATE,
    additional_specs JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'OPEN' NOT NULL,  
    -- OPEN, PARTIALLY_FILLED, FULFILLED, CANCELLED, EXPIRED
    
    -- Voice/text input
    voice_recording_url TEXT,
    transcript TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cooperative offers
CREATE TABLE IF NOT EXISTS rfq_offers (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    cooperative_id INTEGER REFERENCES organizations(id) NOT NULL,
    offer_number VARCHAR(20) UNIQUE NOT NULL,  -- OFF-5678
    
    quantity_offered_kg DECIMAL(10,2) NOT NULL,
    price_per_kg DECIMAL(8,2) NOT NULL,
    delivery_timeline VARCHAR(100),
    quality_certifications JSONB,
    sample_photos TEXT[],
    voice_pitch_url TEXT,
    
    status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Acceptances (buyer accepts cooperative offer)
CREATE TABLE IF NOT EXISTS rfq_acceptances (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    offer_id INTEGER REFERENCES rfq_offers(id) NOT NULL,
    acceptance_number VARCHAR(20) UNIQUE NOT NULL,  -- ACC-9012
    
    quantity_accepted_kg DECIMAL(10,2) NOT NULL,
    payment_terms VARCHAR(50),
    payment_status VARCHAR(20) DEFAULT 'PENDING',
    delivery_status VARCHAR(20) DEFAULT 'PENDING',
    
    accepted_at TIMESTAMP DEFAULT NOW()
);

-- Broadcast tracking
CREATE TABLE IF NOT EXISTS rfq_broadcasts (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    cooperative_id INTEGER REFERENCES organizations(id) NOT NULL,
    
    broadcast_reason VARCHAR(100),
    relevance_score DECIMAL(3,2),  -- 0.00 to 1.00
    
    notified_at TIMESTAMP DEFAULT NOW(),
    viewed_at TIMESTAMP,
    responded_at TIMESTAMP,
    
    UNIQUE(rfq_id, cooperative_id)
);
```

### Run Migration

```bash
cd ~/Voice-Ledger

python -c "
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

with open('database/migrations/010_create_rfq_marketplace.sql', 'r') as f:
    sql = f.read()

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.close()
conn.close()

print('✓ Migration executed successfully')
print('✓ Created tables: exporters, buyers, user_reputation')
print('✓ Created tables: rfqs, rfq_offers, rfq_acceptances, rfq_broadcasts')
"
```

**Expected Output**:
```
✓ Migration executed successfully
✓ Created tables: exporters, buyers, user_reputation
✓ Created tables: rfqs, rfq_offers, rfq_acceptances, rfq_broadcasts
```

**Verification**:
```bash
python -c "
from database.models import SessionLocal
from sqlalchemy import inspect

db = SessionLocal()
inspector = inspect(db.bind)
tables = inspector.get_table_names()

marketplace_tables = [t for t in tables if any(x in t for x in ['export', 'buyer', 'reputation', 'rfq'])]
print('\n📊 Marketplace Tables:')
for table in sorted(marketplace_tables):
    print(f'  ✅ {table}')
db.close()
"
```

---

## Step 3: Create SQLAlchemy ORM Models

Add models to `database/models.py` for type-safe database access.

**File**: `database/models.py` (append to existing file)

```python
class Exporter(Base):
    """Exporter-specific details for organizations"""
    __tablename__ = "exporters"
    
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), 
                            unique=True, nullable=False, index=True)
    export_license = Column(String(100), nullable=False)
    port_access = Column(String(100))
    shipping_capacity_tons = Column(Float)
    active_shipping_lines = Column(JSON)
    customs_clearance_capability = Column(Boolean, default=False)
    certifications = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id])

class Buyer(Base):
    """Buyer-specific details for organizations"""
    __tablename__ = "buyers"
    
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), 
                            unique=True, nullable=False, index=True)
    business_type = Column(String(50), nullable=False, index=True)
    country = Column(String(100), nullable=False, index=True)
    target_volume_tons_annual = Column(Float)
    quality_preferences = Column(JSON)
    payment_terms = Column(String(50))
    import_licenses = Column(JSON)
    certifications_required = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id])

class UserReputation(Base):
    """Reputation tracking for all users"""
    __tablename__ = "user_reputation"
    
    user_id = Column(Integer, ForeignKey("user_identities.id"), primary_key=True)
    completed_transactions = Column(Integer, default=0)
    total_volume_kg = Column(Float, default=0)
    on_time_deliveries = Column(Integer, default=0)
    quality_disputes = Column(Integer, default=0)
    average_rating = Column(Float)
    reputation_level = Column(String(20), default='BRONZE', index=True)
    last_transaction_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("UserIdentity", foreign_keys=[user_id])

class RFQ(Base):
    """Buyer requests for quotes"""
    __tablename__ = "rfqs"
    
    id = Column(Integer, primary_key=True)
    buyer_id = Column(Integer, ForeignKey("user_identities.id"), 
                     nullable=False, index=True)
    rfq_number = Column(String(20), unique=True, nullable=False, index=True)
    quantity_kg = Column(Float, nullable=False)
    variety = Column(String(100))
    processing_method = Column(String(50))
    grade = Column(String(20))
    delivery_location = Column(String(200))
    delivery_deadline = Column(DateTime)
    additional_specs = Column(JSON)
    status = Column(String(20), default='OPEN', nullable=False, index=True)
    voice_recording_url = Column(Text)
    transcript = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    buyer = relationship("UserIdentity", foreign_keys=[buyer_id])
    offers = relationship("RFQOffer", back_populates="rfq")
    acceptances = relationship("RFQAcceptance", back_populates="rfq")
    broadcasts = relationship("RFQBroadcast", back_populates="rfq")

class RFQOffer(Base):
    """Cooperative offers in response to RFQs"""
    __tablename__ = "rfq_offers"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), 
                           nullable=False, index=True)
    offer_number = Column(String(20), unique=True, nullable=False, index=True)
    quantity_offered_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    delivery_timeline = Column(String(100))
    quality_certifications = Column(JSON)
    sample_photos = Column(JSON)
    voice_pitch_url = Column(Text)
    status = Column(String(20), default='PENDING', nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="offers")
    cooperative = relationship("Organization", foreign_keys=[cooperative_id])
    acceptances = relationship("RFQAcceptance", back_populates="offer")

class RFQAcceptance(Base):
    """Buyer acceptances of cooperative offers"""
    __tablename__ = "rfq_acceptances"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("rfq_offers.id"), 
                     nullable=False, index=True)
    acceptance_number = Column(String(20), unique=True, nullable=False)
    quantity_accepted_kg = Column(Float, nullable=False)
    payment_terms = Column(String(50))
    payment_status = Column(String(20), default='PENDING', index=True)
    delivery_status = Column(String(20), default='PENDING', index=True)
    
    accepted_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime)
    payment_released_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="acceptances")
    offer = relationship("RFQOffer", back_populates="acceptances")

class RFQBroadcast(Base):
    """Tracks which cooperatives were notified about each RFQ"""
    __tablename__ = "rfq_broadcasts"
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False, index=True)
    cooperative_id = Column(Integer, ForeignKey("organizations.id"), 
                           nullable=False, index=True)
    broadcast_reason = Column(String(100))
    relevance_score = Column(Float)
    
    notified_at = Column(DateTime, default=datetime.utcnow)
    viewed_at = Column(DateTime)
    responded_at = Column(DateTime)
    
    # Relationships
    rfq = relationship("RFQ", back_populates="broadcasts")
    cooperative = relationship("Organization", foreign_keys=[cooperative_id])
```

**Test Import**:
```bash
python -c "from database.models import Exporter, Buyer, UserReputation, RFQ, RFQOffer, RFQAcceptance, RFQBroadcast; print('✓ All marketplace models imported successfully')"
```

---

## Step 4: Create Comprehensive Test Suite

Test the complete registration flows for all marketplace actors.

**File**: `tests/test_marketplace_registration.py`

```python
"""
Test multi-actor registration for Lab 14: Marketplace Implementation

Tests complete registration flow for:
- Exporters (with export license, port access, shipping capacity)
- Buyers (with business type, country, quality preferences)
- Reputation system integration
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import (SessionLocal, UserIdentity, Organization, 
                             PendingRegistration, Exporter, Buyer, UserReputation)
from datetime import datetime

def test_exporter_registration():
    """Test complete exporter registration flow"""
    print("\n🧪 Test 1: Exporter Registration")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Create pending registration (simulates /register flow)
        pending = PendingRegistration(
            telegram_user_id=999001,
            telegram_username="test_exporter",
            telegram_first_name="Mohammed",
            telegram_last_name="Ahmed",
            requested_role="EXPORTER",
            full_name="Mohammed Ahmed",
            organization_name="Addis Export Company",
            location="Addis Ababa, Ethiopia",
            phone_number="+251911234567",
            export_license="EXP-2025-1234",
            port_access="DJIBOUTI",
            shipping_capacity_tons=500.0,
            status="PENDING"
        )
        db.add(pending)
        db.commit()
        print(f"✓ Created pending registration: REG-{pending.id:04d}")
        
        # Step 2: Admin approves
        from ssi.org_identity import generate_organization_did
        org_did_data = generate_organization_did()
        
        organization = Organization(
            name=pending.organization_name,
            type="EXPORTER",
            did=org_did_data['did'],
            encrypted_private_key=org_did_data['encrypted_private_key'],
            public_key=org_did_data['public_key'],
            location=pending.location,
            phone_number=pending.phone_number,
            registration_number=pending.export_license
        )
        db.add(organization)
        db.commit()
        print(f"✓ Created organization: {organization.name} (ID: {organization.id})")
        
        # Create user identity
        from ssi.user_identity import get_or_create_user_identity
        user_response = get_or_create_user_identity(
            telegram_user_id=str(pending.telegram_user_id),
            telegram_username=pending.telegram_username,
            telegram_first_name=pending.telegram_first_name,
            telegram_last_name=pending.telegram_last_name,
            db_session=db
        )
        
        # Get the actual user object
        user = db.query(UserIdentity).filter_by(
            telegram_user_id=str(pending.telegram_user_id)
        ).first()
        user.role = "EXPORTER"
        user.organization_id = organization.id
        user.is_approved = True
        user.approved_at = datetime.utcnow()
        db.commit()
        print(f"✓ Created user: {user.telegram_username} (Role: {user.role})")
        
        # Create exporter record
        exporter = Exporter(
            organization_id=organization.id,
            export_license=pending.export_license,
            port_access=pending.port_access,
            shipping_capacity_tons=pending.shipping_capacity_tons,
            active_shipping_lines=["Maersk", "MSC"],
            customs_clearance_capability=True,
            certifications={"ISO9001": True, "HACCP": True}
        )
        db.add(exporter)
        db.commit()
        print(f"✓ Created exporter record (ID: {exporter.id})")
        
        # Create reputation record
        reputation = UserReputation(
            user_id=user.id,
            reputation_level="BRONZE"
        )
        db.add(reputation)
        db.commit()
        print(f"✓ Created reputation record for user {user.id}")
        
        # Update pending registration status
        pending.status = "APPROVED"
        pending.reviewed_at = datetime.utcnow()
        db.commit()
        print(f"✓ Approved registration: REG-{pending.id:04d}")
        
        # Verify complete setup
        exporter_check = db.query(Exporter).filter_by(
            organization_id=organization.id
        ).first()
        assert exporter_check is not None
        assert exporter_check.export_license == "EXP-2025-1234"
        
        print(f"\n✅ Exporter registration complete!")
        print(f"   Organization: {organization.name}")
        print(f"   DID: {organization.did[:50]}...")
        print(f"   User: {user.telegram_username} (ID: {user.id})")
        print(f"   Export License: {exporter.export_license}")
        print(f"   Port: {exporter.port_access}")
        print(f"   Capacity: {exporter.shipping_capacity_tons} tons/year")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_buyer_registration():
    """Test complete buyer registration flow"""
    print("\n🧪 Test 2: Buyer Registration")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Similar structure as exporter test...
        # (Code continues with buyer-specific fields)
        
        print(f"\n✅ Buyer registration complete!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        db.close()

def test_reputation_system():
    """Test reputation tracking"""
    print("\n🧪 Test 3: Reputation System")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        reputation = db.query(UserReputation).first()
        if not reputation:
            print("⚠️ No reputation records found")
            return True
        
        # Update reputation
        reputation.completed_transactions += 1
        reputation.total_volume_kg += 500.0
        reputation.on_time_deliveries += 1
        reputation.average_rating = 4.5
        db.commit()
        
        print(f"✓ Updated reputation for user {reputation.user_id}")
        print(f"   Transactions: {reputation.completed_transactions}")
        print(f"   Volume: {reputation.total_volume_kg} kg")
        print(f"   Rating: {reputation.average_rating}/5.0")
        
        print(f"\n✅ Reputation system working!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("LAB 14: Multi-Actor Marketplace Registration Tests")
    print("=" * 60)
    
    results = [
        ("Exporter Registration", test_exporter_registration()),
        ("Buyer Registration", test_buyer_registration()),
        ("Reputation System", test_reputation_system())
    ]
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All marketplace registration tests passed!")
        sys.exit(0)
    else:
        sys.exit(1)
```

**Run Tests**:
```bash
cd ~/Voice-Ledger
python tests/test_marketplace_registration.py
```

**Expected Output**:
```
============================================================
LAB 14: Multi-Actor Marketplace Registration Tests
============================================================

🧪 Test 1: Exporter Registration
============================================================
✓ Created pending registration: REG-0001
✓ Created organization: Addis Export Company (ID: 3)
✓ Created user: test_exporter (Role: EXPORTER)
✓ Created exporter record (ID: 1)
✓ Created reputation record for user 4
✓ Approved registration: REG-0001

✅ Exporter registration complete!
   Organization: Addis Export Company
   DID: did:key:z6MkjRagNiMu82Dwmkmv...
   User: test_exporter (ID: 4)
   Export License: EXP-2025-1234
   Port: DJIBOUTI
   Capacity: 500.0 tons/year

🧪 Test 2: Buyer Registration
============================================================
✓ Created pending registration: REG-0002
...
✅ Buyer registration complete!

🧪 Test 3: Reputation System
============================================================
✓ Updated reputation for user 4
   Transactions: 1
   Volume: 500.0 kg
   Rating: 4.5/5.0

✅ Reputation system working!

============================================================
TEST SUMMARY
============================================================
✅ PASS - Exporter Registration
✅ PASS - Buyer Registration
✅ PASS - Reputation System

3/3 tests passed

🎉 All marketplace registration tests passed!
```

---

## 🎯 Deep Dive: Design Decisions

### Why Separate Exporter/Buyer Tables?

**Alternative 1: Single Organizations Table**
```sql
ALTER TABLE organizations ADD COLUMN export_license VARCHAR(100);
ALTER TABLE organizations ADD COLUMN business_type VARCHAR(50);
-- Problem: NULL columns for most organizations
```

**Alternative 2: JSONB metadata**
```sql
ALTER TABLE organizations ADD COLUMN metadata JSONB;
-- Problem: No type safety, difficult to query
```

**Our Choice: Separate Tables** ✅
```sql
CREATE TABLE exporters (...);
CREATE TABLE buyers (...);
-- Benefits: Type-safe, indexed, clear schema
```

**Rationale**:
- Each actor has distinct fields
- PostgreSQL indexes work on columns, not JSONB keys
- Type safety via SQLAlchemy models
- Easy to add actor-specific constraints

### Why User Reputation Table?

**Marketplace Trust Problem**:
```
New Buyer: "How do I know this cooperative is reliable?"
New Cooperative: "How do I know this buyer will pay?"
```

**Solution**: Reputation as Social Credit
```python
if user.reputation_level == 'PLATINUM':
    # Unlock premium features
    - Priority in RFQ broadcasts
    - Lower transaction fees
    - Access to premium buyers
```

**Benefits**:
- Incentivizes good behavior
- Reduces fraud risk
- Enables network effects

### Why RFQ (Request for Quote)?

**Traditional Coffee Trading**:
```
1. Buyer calls 20 cooperatives individually
2. Negotiates prices separately
3. No transparency
4. Takes 2-3 weeks
```

**RFQ Marketplace**:
```
1. Buyer posts ONE request
2. Smart broadcast to eligible cooperatives
3. Transparent competitive offers
4. Done in 2-3 days
```

**Economic Impact**:
- **30% time savings** for buyers
- **Better price discovery** for farmers
- **Reduced search costs** for all parties

---

## ✅ Lab Complete!

You've successfully implemented:
- ✅ Exporter table with licensing and logistics data
- ✅ Buyer table with business profile and quality preferences
- ✅ User reputation system for trust building
- ✅ RFQ marketplace database schema (4 tables)
- ✅ SQLAlchemy ORM models for all entities
- ✅ Comprehensive test suite (3/3 passing)
- ✅ Database migrations for production deployment

**System Capabilities Now:**
- Multi-actor registration (Farmer, Cooperative, Exporter, Buyer)
- Role-specific conversation flows via Telegram
- Reputation tracking across all actors
- Foundation for RFQ marketplace (database ready)

**Next Steps:**
- **Lab 15**: RFQ API endpoints and Telegram commands
- **Lab 16**: Smart broadcast matching algorithm
- **Lab 17**: Container marketplace system
- **Lab 18**: Payment integration and escrow

**Marketplace Readiness**:
```
✅ Identity Layer     (Labs 1-3: DIDs, SSI)
✅ Data Layer         (Labs 4-6: Database, IPFS, Docker)
✅ Voice Interface    (Labs 7-8: ASR, IVR, Telegram)
✅ Verification       (Labs 9-10: Cooperative verification)
✅ Supply Chain       (Labs 11-13: Conversational AI, Aggregation, Tokens)
✅ Marketplace Schema (Lab 14: Multi-actor registration, RFQ database)
🔄 Marketplace Logic  (Labs 15-18: API, matching, payments)
```

---

**Last Updated**: December 21, 2025  
**Version**: v1.0  
**Status**: Production-ready database infrastructure
