-- Migration: Add EUDR-compliant origin fields to coffee_batches and fix relationships
-- Date: 2025-12-14
-- Purpose: Add detailed origin tracking for EUDR compliance and fix credential relationships

-- Add EUDR origin fields to coffee_batches
ALTER TABLE coffee_batches
ADD COLUMN IF NOT EXISTS origin_country VARCHAR(2),
ADD COLUMN IF NOT EXISTS origin_region VARCHAR(100),
ADD COLUMN IF NOT EXISTS farm_name VARCHAR(200),
ADD COLUMN IF NOT EXISTS process_method VARCHAR(50);

-- Add farmer_id to verifiable_credentials for proper relationship
ALTER TABLE verifiable_credentials
ADD COLUMN IF NOT EXISTS farmer_id INTEGER REFERENCES farmer_identities(id);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_batch_origin_country ON coffee_batches(origin_country);
CREATE INDEX IF NOT EXISTS idx_batch_origin_region ON coffee_batches(origin_region);
CREATE INDEX IF NOT EXISTS idx_credential_farmer ON verifiable_credentials(farmer_id);

-- Add comments
COMMENT ON COLUMN coffee_batches.origin_country IS 'ISO 3166-1 alpha-2 country code for EUDR compliance';
COMMENT ON COLUMN coffee_batches.origin_region IS 'State/province/region for supply chain transparency';
COMMENT ON COLUMN coffee_batches.farm_name IS 'Farm name for traceability';
COMMENT ON COLUMN coffee_batches.process_method IS 'Processing method (alias for DPP compatibility)';
COMMENT ON COLUMN verifiable_credentials.farmer_id IS 'Link to farmer for DPP generation';

-- Update process_method from processing_method for existing records
UPDATE coffee_batches SET process_method = processing_method WHERE process_method IS NULL;

-- Link existing credentials to farmers based on subject_did
UPDATE verifiable_credentials vc
SET farmer_id = fi.id
FROM farmer_identities fi
WHERE vc.subject_did = fi.did AND vc.farmer_id IS NULL;
