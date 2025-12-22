-- Migration: Add PIN authentication support for web UI access
-- Purpose: Enable secure 4-digit PIN login for farmers and other users
-- Phase: 3 (PIN Setup Integration)
-- Date: December 22, 2025

-- Add PIN fields to user_identities table
ALTER TABLE user_identities 
  ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS pin_salt VARCHAR(255),
  ADD COLUMN IF NOT EXISTS pin_set_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP,
  ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP;

-- Add PIN fields to pending_registrations table
ALTER TABLE pending_registrations
  ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS pin_salt VARCHAR(255);

-- Create index for failed login attempts (for lockout queries)
CREATE INDEX IF NOT EXISTS idx_user_identities_failed_attempts 
  ON user_identities(failed_login_attempts) 
  WHERE failed_login_attempts > 0;

-- Create index for locked accounts (for cleanup queries)
CREATE INDEX IF NOT EXISTS idx_user_identities_locked 
  ON user_identities(locked_until) 
  WHERE locked_until IS NOT NULL;

-- Add comment
COMMENT ON COLUMN user_identities.pin_hash IS 'Bcrypt hash of 4-digit PIN for web UI authentication';
COMMENT ON COLUMN user_identities.pin_salt IS 'Salt for PIN hashing (bcrypt includes salt in hash, but kept for compatibility)';
COMMENT ON COLUMN user_identities.pin_set_at IS 'When PIN was last set/changed';
COMMENT ON COLUMN user_identities.failed_login_attempts IS 'Number of consecutive failed PIN attempts';
COMMENT ON COLUMN user_identities.locked_until IS 'Account locked until this timestamp (NULL if not locked)';
COMMENT ON COLUMN user_identities.last_login_at IS 'Last successful PIN login timestamp';

-- Verification query
-- Run after migration to verify columns were added:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'user_identities' 
-- AND column_name LIKE 'pin%' OR column_name LIKE '%login%' OR column_name = 'locked_until'
-- ORDER BY column_name;
