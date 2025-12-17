-- Migration: Add verification and registration system tables
-- Date: 2025-12-17
-- Purpose: Enable third-party batch verification and role-based registration

-- ============================================================================
-- 1. CREATE ORGANIZATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('COOPERATIVE', 'EXPORTER', 'BUYER')),
    did VARCHAR(200) UNIQUE NOT NULL,
    location VARCHAR(200),
    region VARCHAR(100),
    phone_number VARCHAR(20),
    registration_number VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    metadata JSONB
);

-- Create indexes for organizations
CREATE INDEX IF NOT EXISTS idx_org_type ON organizations(type);
CREATE INDEX IF NOT EXISTS idx_org_did ON organizations(did);
CREATE INDEX IF NOT EXISTS idx_org_name ON organizations(name);

-- ============================================================================
-- 2. CREATE PENDING_REGISTRATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS pending_registrations (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(100),
    telegram_last_name VARCHAR(100),
    
    requested_role VARCHAR(50) NOT NULL CHECK (requested_role IN ('COOPERATIVE_MANAGER', 'EXPORTER', 'BUYER')),
    
    -- Registration form answers
    full_name VARCHAR(200) NOT NULL,
    organization_name VARCHAR(200) NOT NULL,
    location VARCHAR(200) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    registration_number VARCHAR(100),
    reason TEXT,
    
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    reviewed_by_admin_id INTEGER,
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for pending_registrations
CREATE INDEX IF NOT EXISTS idx_pending_reg_status ON pending_registrations(status);
CREATE INDEX IF NOT EXISTS idx_pending_reg_telegram ON pending_registrations(telegram_user_id);

-- ============================================================================
-- 3. CREATE FARMER_COOPERATIVES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS farmer_cooperatives (
    id SERIAL PRIMARY KEY,
    farmer_id INTEGER NOT NULL REFERENCES user_identities(id),
    cooperative_id INTEGER NOT NULL REFERENCES organizations(id),
    
    first_delivery_date TIMESTAMP NOT NULL,
    total_batches_verified INTEGER DEFAULT 1,
    total_quantity_verified_kg FLOAT DEFAULT 0,
    
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'TERMINATED')),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(farmer_id, cooperative_id)
);

-- Create indexes for farmer_cooperatives
CREATE INDEX IF NOT EXISTS idx_farmer_coop_farmer ON farmer_cooperatives(farmer_id);
CREATE INDEX IF NOT EXISTS idx_farmer_coop_coop ON farmer_cooperatives(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_farmer_coop_status ON farmer_cooperatives(status);

-- ============================================================================
-- 4. CREATE VERIFICATION_EVIDENCE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS verification_evidence (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES coffee_batches(id),
    evidence_type VARCHAR(50) NOT NULL CHECK (evidence_type IN ('PHOTO', 'DOCUMENT', 'GPS', 'WEIGHING_SLIP', 'OTHER')),
    content_hash VARCHAR(64) NOT NULL,
    storage_url VARCHAR(500) NOT NULL,
    captured_by_did VARCHAR(200) NOT NULL,
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for verification_evidence
CREATE INDEX IF NOT EXISTS idx_evidence_batch_id ON verification_evidence(batch_id);
CREATE INDEX IF NOT EXISTS idx_evidence_hash ON verification_evidence(content_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON verification_evidence(evidence_type);

-- ============================================================================
-- 5. MODIFY USER_IDENTITIES TABLE (Add role and organization)
-- ============================================================================
ALTER TABLE user_identities 
ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'FARMER' CHECK (role IN ('FARMER', 'COOPERATIVE_MANAGER', 'EXPORTER', 'BUYER', 'SYSTEM_ADMIN')),
ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id),
ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS approved_by_admin_id INTEGER;

-- Create indexes for new user_identities columns
CREATE INDEX IF NOT EXISTS idx_user_role ON user_identities(role);
CREATE INDEX IF NOT EXISTS idx_user_org ON user_identities(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_approved ON user_identities(is_approved);

-- ============================================================================
-- 6. MODIFY COFFEE_BATCHES TABLE (Add verification fields)
-- ============================================================================
ALTER TABLE coffee_batches 
ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'PENDING_VERIFICATION' CHECK (status IN ('PENDING_VERIFICATION', 'VERIFIED', 'REJECTED', 'EXPIRED')),
ADD COLUMN IF NOT EXISTS verification_token VARCHAR(64) UNIQUE,
ADD COLUMN IF NOT EXISTS verification_expires_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS verification_used BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verified_quantity FLOAT,
ADD COLUMN IF NOT EXISTS verified_by_did VARCHAR(200),
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS verification_notes TEXT,
ADD COLUMN IF NOT EXISTS has_photo_evidence BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verifying_organization_id INTEGER REFERENCES organizations(id);

-- Create indexes for new coffee_batches columns
CREATE INDEX IF NOT EXISTS idx_batch_status ON coffee_batches(status);
CREATE INDEX IF NOT EXISTS idx_verification_token ON coffee_batches(verification_token);
CREATE INDEX IF NOT EXISTS idx_verified_by_did ON coffee_batches(verified_by_did);
CREATE INDEX IF NOT EXISTS idx_batch_verifying_org ON coffee_batches(verifying_organization_id);
CREATE INDEX IF NOT EXISTS idx_verification_expires_at ON coffee_batches(verification_expires_at);

-- ============================================================================
-- 7. CREATE UPDATE TRIGGERS
-- ============================================================================

-- Trigger for organizations updated_at
CREATE OR REPLACE FUNCTION update_organizations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER organizations_updated_at
BEFORE UPDATE ON organizations
FOR EACH ROW
EXECUTE FUNCTION update_organizations_updated_at();

-- Trigger for farmer_cooperatives updated_at
CREATE OR REPLACE FUNCTION update_farmer_cooperatives_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER farmer_cooperatives_updated_at
BEFORE UPDATE ON farmer_cooperatives
FOR EACH ROW
EXECUTE FUNCTION update_farmer_cooperatives_updated_at();

-- ============================================================================
-- 8. BACKFILL EXISTING DATA (Set default values for existing records)
-- ============================================================================

-- Set status for existing batches that don't have a status
UPDATE coffee_batches 
SET status = 'VERIFIED' 
WHERE status IS NULL 
  AND id IS NOT NULL;

-- Set role for existing users (they're all farmers)
UPDATE user_identities 
SET role = 'FARMER',
    is_approved = TRUE,
    approved_at = created_at
WHERE role IS NULL;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Verify table creation
DO $$
BEGIN
    RAISE NOTICE 'Verification system migration completed successfully!';
    RAISE NOTICE 'New tables created: organizations, pending_registrations, farmer_cooperatives, verification_evidence';
    RAISE NOTICE 'Modified tables: user_identities (added role, organization_id), coffee_batches (added verification fields)';
END $$;
