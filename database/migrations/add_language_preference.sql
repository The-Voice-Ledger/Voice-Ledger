-- Migration: Add language preference to user_identities table
-- Date: 2025-12-20
-- Description: Add preferred_language and language_set_at columns for conversational AI routing

-- Add preferred_language column (defaults to 'en' for English)
ALTER TABLE user_identities 
ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(2) DEFAULT 'en' NOT NULL;

-- Add language_set_at timestamp
ALTER TABLE user_identities 
ADD COLUMN IF NOT EXISTS language_set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_user_identities_preferred_language 
ON user_identities(preferred_language);

-- Update existing users to have English as default
UPDATE user_identities 
SET preferred_language = 'en', 
    language_set_at = CURRENT_TIMESTAMP 
WHERE preferred_language IS NULL;

-- Verify migration
SELECT COUNT(*) as total_users,
       SUM(CASE WHEN preferred_language = 'en' THEN 1 ELSE 0 END) as english_users,
       SUM(CASE WHEN preferred_language = 'am' THEN 1 ELSE 0 END) as amharic_users
FROM user_identities;
