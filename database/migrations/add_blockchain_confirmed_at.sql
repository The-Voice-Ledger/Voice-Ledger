-- Migration: Add blockchain_confirmed_at timestamp to epcis_events
-- Date: 2025-12-14
-- Purpose: Track when blockchain anchor was actually confirmed, not just when event was created

-- Add blockchain_confirmed_at column
ALTER TABLE epcis_events
ADD COLUMN IF NOT EXISTS blockchain_confirmed_at TIMESTAMP;

-- Add comment
COMMENT ON COLUMN epcis_events.blockchain_confirmed_at IS 'Timestamp when blockchain anchor was confirmed';

-- Create index for querying confirmed events
CREATE INDEX IF NOT EXISTS idx_epcis_blockchain_confirmed_at ON epcis_events(blockchain_confirmed_at) WHERE blockchain_confirmed = true;
