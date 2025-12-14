-- Migration: Add EUDR-required geolocation and certification fields to farmer_identities
-- Date: 2025-12-14
-- Purpose: Ensure compliance with EU Deforestation Regulation (EUDR) requiring plot-level traceability

-- Add geolocation columns (required for EUDR plot-level traceability)
ALTER TABLE farmer_identities 
ADD COLUMN IF NOT EXISTS latitude FLOAT,
ADD COLUMN IF NOT EXISTS longitude FLOAT,
ADD COLUMN IF NOT EXISTS region VARCHAR(100),
ADD COLUMN IF NOT EXISTS country_code VARCHAR(2),
ADD COLUMN IF NOT EXISTS farm_size_hectares FLOAT,
ADD COLUMN IF NOT EXISTS certification_status VARCHAR(100);

-- Add comments for documentation
COMMENT ON COLUMN farmer_identities.latitude IS 'Farm latitude for EUDR geolocation compliance';
COMMENT ON COLUMN farmer_identities.longitude IS 'Farm longitude for EUDR geolocation compliance';
COMMENT ON COLUMN farmer_identities.region IS 'State/province/region for supply chain transparency';
COMMENT ON COLUMN farmer_identities.country_code IS 'ISO 3166-1 alpha-2 country code';
COMMENT ON COLUMN farmer_identities.farm_size_hectares IS 'Farm size in hectares (EUDR requirement)';
COMMENT ON COLUMN farmer_identities.certification_status IS 'Certifications held (Organic, Fair Trade, etc.)';

-- Create index on country_code for faster filtering
CREATE INDEX IF NOT EXISTS idx_farmer_country ON farmer_identities(country_code);
CREATE INDEX IF NOT EXISTS idx_farmer_region ON farmer_identities(region);

-- Update existing records with placeholder values (should be updated with real data)
-- UPDATE farmer_identities SET country_code = 'ET' WHERE country_code IS NULL AND location LIKE '%Ethiopia%';
-- UPDATE farmer_identities SET country_code = 'CO' WHERE country_code IS NULL AND location LIKE '%Colombia%';
