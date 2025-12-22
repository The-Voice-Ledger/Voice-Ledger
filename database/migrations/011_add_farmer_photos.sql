-- Migration: Add GPS-verified photo fields to farmer_identities for EUDR compliance
-- Date: 2025-12-22
-- Purpose: Enable photo-based GPS verification for EU Deforestation Regulation (EUDR) Article 9 compliance

-- Add photo verification columns to farmer_identities table
ALTER TABLE farmer_identities 
ADD COLUMN IF NOT EXISTS farm_photo_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS farm_photo_hash VARCHAR(64),
ADD COLUMN IF NOT EXISTS farm_photo_ipfs VARCHAR(100),
ADD COLUMN IF NOT EXISTS photo_latitude FLOAT,
ADD COLUMN IF NOT EXISTS photo_longitude FLOAT,
ADD COLUMN IF NOT EXISTS photo_timestamp TIMESTAMP,
ADD COLUMN IF NOT EXISTS gps_verified_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS photo_device_make VARCHAR(100),
ADD COLUMN IF NOT EXISTS photo_device_model VARCHAR(100),
ADD COLUMN IF NOT EXISTS blockchain_proof_hash VARCHAR(66);

-- Add comments for documentation
COMMENT ON COLUMN farmer_identities.farm_photo_url IS 'URL to farm registration photo (Telegram file or IPFS)';
COMMENT ON COLUMN farmer_identities.farm_photo_hash IS 'SHA-256 hash of farm photo for duplicate detection and blockchain anchoring';
COMMENT ON COLUMN farmer_identities.farm_photo_ipfs IS 'IPFS CID (Content Identifier) for decentralized storage';
COMMENT ON COLUMN farmer_identities.photo_latitude IS 'GPS latitude extracted from photo EXIF metadata';
COMMENT ON COLUMN farmer_identities.photo_longitude IS 'GPS longitude extracted from photo EXIF metadata';
COMMENT ON COLUMN farmer_identities.photo_timestamp IS 'Timestamp when photo was taken (from EXIF)';
COMMENT ON COLUMN farmer_identities.gps_verified_at IS 'Timestamp when GPS was verified from photo';
COMMENT ON COLUMN farmer_identities.photo_device_make IS 'Device manufacturer from EXIF (e.g., Apple, Samsung)';
COMMENT ON COLUMN farmer_identities.photo_device_model IS 'Device model from EXIF (e.g., iPhone 14 Pro)';
COMMENT ON COLUMN farmer_identities.blockchain_proof_hash IS 'Transaction hash of blockchain-anchored GPS proof';

-- Create indexes for querying
CREATE INDEX IF NOT EXISTS idx_farmer_gps_verified ON farmer_identities(gps_verified_at);
CREATE INDEX IF NOT EXISTS idx_farmer_photo_hash ON farmer_identities(farm_photo_hash);

-- Create table for batch verification photos (for ongoing compliance)
CREATE TABLE IF NOT EXISTS verification_photos (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES coffee_batches(id) ON DELETE CASCADE,
    photo_url VARCHAR(500) NOT NULL,
    photo_hash VARCHAR(64) NOT NULL,
    photo_ipfs VARCHAR(100),
    latitude FLOAT,
    longitude FLOAT,
    photo_timestamp TIMESTAMP,
    device_make VARCHAR(100),
    device_model VARCHAR(100),
    verified_at TIMESTAMP DEFAULT NOW(),
    distance_from_farm_km FLOAT,
    blockchain_proof_hash VARCHAR(66),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(photo_hash)
);

-- Add comments for verification_photos table
COMMENT ON TABLE verification_photos IS 'GPS-verified photos linked to coffee batches for EUDR compliance';
COMMENT ON COLUMN verification_photos.batch_id IS 'Coffee batch being verified';
COMMENT ON COLUMN verification_photos.distance_from_farm_km IS 'Distance between verification photo GPS and registered farm location';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_verification_photos_batch ON verification_photos(batch_id);
CREATE INDEX IF NOT EXISTS idx_verification_photos_hash ON verification_photos(photo_hash);
CREATE INDEX IF NOT EXISTS idx_verification_photos_verified_at ON verification_photos(verified_at);

-- Add EUDR compliance status view
CREATE OR REPLACE VIEW farmer_eudr_compliance AS
SELECT 
    fi.id,
    fi.farmer_id,
    fi.name,
    fi.latitude AS registered_latitude,
    fi.longitude AS registered_longitude,
    fi.photo_latitude,
    fi.photo_longitude,
    fi.gps_verified_at,
    fi.farm_photo_ipfs,
    fi.blockchain_proof_hash,
    CASE 
        WHEN fi.latitude IS NULL OR fi.longitude IS NULL THEN 'NO_GPS'
        WHEN fi.gps_verified_at IS NULL THEN 'GPS_UNVERIFIED'
        WHEN fi.blockchain_proof_hash IS NULL THEN 'NOT_ANCHORED'
        ELSE 'COMPLIANT'
    END AS compliance_status,
    COUNT(DISTINCT cb.id) AS total_batches,
    COUNT(DISTINCT vp.id) AS verified_batches
FROM farmer_identities fi
LEFT JOIN coffee_batches cb ON fi.id = cb.farmer_id
LEFT JOIN verification_photos vp ON cb.id = vp.batch_id
GROUP BY fi.id, fi.farmer_id, fi.name, fi.latitude, fi.longitude, 
         fi.photo_latitude, fi.photo_longitude, fi.gps_verified_at, 
         fi.farm_photo_ipfs, fi.blockchain_proof_hash;

COMMENT ON VIEW farmer_eudr_compliance IS 'Summary view of farmer EUDR compliance status';
