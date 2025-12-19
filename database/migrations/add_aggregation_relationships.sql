-- Migration: Add aggregation_relationships table
-- Purpose: Track parent-child relationships for EPCIS AggregationEvents
-- Author: Voice Ledger Team
-- Date: December 19, 2025

CREATE TABLE IF NOT EXISTS aggregation_relationships (
    id SERIAL PRIMARY KEY,
    
    -- Parent container (pallet, shipping container, etc.)
    parent_sscc VARCHAR(18) NOT NULL,
    
    -- Child item (batch or another container)
    child_identifier VARCHAR(100) NOT NULL,
    child_type VARCHAR(20) NOT NULL CHECK (child_type IN ('batch', 'sscc', 'pallet')),
    
    -- Link to EPCIS events
    aggregation_event_id INTEGER REFERENCES epcis_events(id) ON DELETE SET NULL,
    disaggregation_event_id INTEGER REFERENCES epcis_events(id) ON DELETE SET NULL,
    
    -- Timestamps
    aggregated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    disaggregated_at TIMESTAMP,
    
    -- Status tracking
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_parent_active 
    ON aggregation_relationships(parent_sscc, is_active);
    
CREATE INDEX IF NOT EXISTS idx_child_active 
    ON aggregation_relationships(child_identifier, is_active);
    
CREATE INDEX IF NOT EXISTS idx_aggregation_event 
    ON aggregation_relationships(aggregation_event_id);

-- Comments for documentation
COMMENT ON TABLE aggregation_relationships IS 
    'Tracks parent-child containment relationships for logistics units';
    
COMMENT ON COLUMN aggregation_relationships.parent_sscc IS 
    '18-digit GS1 SSCC identifying the container (pallet, shipping container)';
    
COMMENT ON COLUMN aggregation_relationships.child_identifier IS 
    'Batch ID or SSCC of item inside the parent';
    
COMMENT ON COLUMN aggregation_relationships.is_active IS 
    'TRUE = currently packed, FALSE = unpacked (disaggregated)';
