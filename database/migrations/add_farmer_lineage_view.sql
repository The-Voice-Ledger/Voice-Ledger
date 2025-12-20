-- Migration: Add materialized view for fast farmer lineage queries
-- Purpose: Pre-compute farmer contributions across aggregation hierarchy
-- Author: Voice Ledger Team
-- Date: December 20, 2025
-- Phase: 4 - Performance Optimization (Aggregation Roadmap Section 2.1.2)

-- Drop existing view if exists (for re-running migration)
DROP MATERIALIZED VIEW IF EXISTS product_farmer_lineage CASCADE;
DROP TRIGGER IF EXISTS trigger_refresh_lineage ON aggregation_relationships;
DROP FUNCTION IF EXISTS refresh_farmer_lineage();

-- Create materialized view with recursive CTE
-- This pre-computes all farmer contributions for every product/container
-- Eliminates need for expensive recursive queries at DPP generation time
CREATE MATERIALIZED VIEW product_farmer_lineage AS
WITH RECURSIVE lineage AS (
    -- Base case: Direct farmer batches (no aggregation yet)
    SELECT 
        b.batch_id::VARCHAR(100) AS product_id,
        b.batch_id AS farmer_batch_id,
        f.id AS farmer_id,
        f.farmer_id AS farmer_identifier,
        f.name AS farmer_name,
        f.did AS farmer_did,
        b.quantity_kg,
        b.origin_region,
        b.origin_country,
        f.latitude,
        f.longitude,
        1 AS depth
    FROM coffee_batches b
    JOIN farmer_identities f ON b.farmer_id = f.id
    WHERE b.quantity_kg > 0  -- Only include batches with quantity
    
    UNION ALL
    
    -- Recursive case: Traverse aggregation hierarchy upward
    -- Each iteration follows parent-child relationships one level up
    SELECT
        ar.parent_sscc::VARCHAR(100) AS product_id,
        l.farmer_batch_id,
        l.farmer_id,
        l.farmer_identifier,
        l.farmer_name,
        l.farmer_did,
        l.quantity_kg,
        l.origin_region,
        l.origin_country,
        l.latitude,
        l.longitude,
        l.depth + 1
    FROM lineage l
    JOIN aggregation_relationships ar ON l.product_id = ar.child_identifier
    WHERE ar.is_active = TRUE  -- Only active aggregations
      AND l.depth < 10  -- Prevent infinite loops (max 10 levels)
)
SELECT 
    product_id,
    farmer_id,
    farmer_identifier,
    farmer_name,
    farmer_did,
    SUM(quantity_kg) AS total_contribution_kg,
    MAX(origin_region) AS origin_region,
    MAX(origin_country) AS origin_country,
    MAX(latitude) AS latitude,
    MAX(longitude) AS longitude,
    MAX(depth) AS max_depth
FROM lineage
GROUP BY 
    product_id, 
    farmer_id, 
    farmer_identifier,
    farmer_name, 
    farmer_did;

-- Create index for O(1) product lookups
-- This is the primary access pattern: "Given product_id, find all farmers"
CREATE INDEX idx_product_farmer_lookup 
    ON product_farmer_lineage(product_id);

-- Create index for reverse lookups: "Given farmer_id, find all products"
CREATE INDEX idx_farmer_product_lookup 
    ON product_farmer_lineage(farmer_id);

-- Create index for DID-based lookups (for blockchain verification)
CREATE INDEX idx_farmer_did_lookup 
    ON product_farmer_lineage(farmer_did);

-- Comments for documentation
COMMENT ON MATERIALIZED VIEW product_farmer_lineage IS 
    'Pre-computed farmer contributions across entire aggregation hierarchy. 
    Enables fast DPP generation for containers with 1000+ farmers.
    Refreshed automatically after each aggregation event.';

COMMENT ON COLUMN product_farmer_lineage.product_id IS 
    'Product/container identifier (batch_id or parent_sscc)';

COMMENT ON COLUMN product_farmer_lineage.total_contribution_kg IS 
    'Total kg contributed by this farmer to this product (sum if multiple batches)';

COMMENT ON COLUMN product_farmer_lineage.max_depth IS 
    'Maximum aggregation depth (1 = direct batch, 2+ = aggregated)';

-- Create function to refresh materialized view
-- This is called automatically by trigger after aggregation events
CREATE OR REPLACE FUNCTION refresh_farmer_lineage()
RETURNS TRIGGER AS $$
BEGIN
    -- Use CONCURRENTLY to avoid blocking queries during refresh
    -- Requires UNIQUE index (handled by compound key above)
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_farmer_lineage;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-refresh after aggregation changes
-- Fires after INSERT (new aggregations) or UPDATE (status changes)
CREATE TRIGGER trigger_refresh_lineage
AFTER INSERT OR UPDATE ON aggregation_relationships
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_farmer_lineage();

-- Initial population
REFRESH MATERIALIZED VIEW product_farmer_lineage;

-- Verify view was created successfully
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM product_farmer_lineage;
    RAISE NOTICE 'Materialized view created with % rows', row_count;
END $$;
