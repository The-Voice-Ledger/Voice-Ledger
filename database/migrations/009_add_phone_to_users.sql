-- Migration: Add phone_number to user_identities for IVR authentication
-- Created: 2025-12-21
-- Purpose: Enable phone-based authentication for IVR calls

-- Add phone_number column (E.164 format: +251912345678)
ALTER TABLE user_identities 
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) UNIQUE;

-- Add index for fast lookups during IVR calls
CREATE INDEX IF NOT EXISTS idx_users_phone_number 
ON user_identities(phone_number) 
WHERE phone_number IS NOT NULL;

-- Add phone verification timestamp
ALTER TABLE user_identities 
ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMP;

-- Add comment explaining the column
COMMENT ON COLUMN user_identities.phone_number IS 
'Phone number in E.164 format (+country_code + number). Used for IVR authentication. Unique constraint ensures one phone per user.';

COMMENT ON COLUMN user_identities.phone_verified_at IS 
'Timestamp when phone was verified via Telegram contact share or SMS verification.';
