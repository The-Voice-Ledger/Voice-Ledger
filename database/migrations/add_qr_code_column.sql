-- Migration: Add QR code storage to coffee_batches
-- Date: 2026-03-08
-- Purpose: Store base64 encoded QR codes directly in the database for demo performance

ALTER TABLE coffee_batches
ADD COLUMN IF NOT EXISTS qr_code_base64 TEXT;

COMMENT ON COLUMN coffee_batches.qr_code_base64 IS 'Base64 encoded PNG of the batch DPP QR code';
