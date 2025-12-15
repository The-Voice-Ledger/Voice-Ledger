-- Migration: Add user_identities table and batch ownership tracking
-- Date: 2025-12-16
-- Purpose: Enable DID/SSI authentication and batch ownership for Telegram users

-- Create user_identities table
CREATE TABLE IF NOT EXISTS user_identities (
    id SERIAL PRIMARY KEY,
    telegram_user_id VARCHAR(50) UNIQUE NOT NULL,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(100),
    telegram_last_name VARCHAR(100),
    did VARCHAR(200) UNIQUE NOT NULL,
    encrypted_private_key TEXT NOT NULL,
    public_key VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_identities_telegram_user_id ON user_identities(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_identities_did ON user_identities(did);

-- Add batch ownership columns to coffee_batches
ALTER TABLE coffee_batches 
ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_identities(id),
ADD COLUMN IF NOT EXISTS created_by_did VARCHAR(200);

-- Create index for fast batch queries by user
CREATE INDEX IF NOT EXISTS idx_coffee_batches_created_by_user_id ON coffee_batches(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_coffee_batches_created_by_did ON coffee_batches(created_by_did);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_identities_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_identities_updated_at
BEFORE UPDATE ON user_identities
FOR EACH ROW
EXECUTE FUNCTION update_user_identities_updated_at();
