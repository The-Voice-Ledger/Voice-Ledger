-- Migration: Create RFQ Marketplace tables
-- Purpose: Enable buyer-to-cooperative Request for Quote system
-- Author: Voice Ledger Team
-- Date: December 21, 2025

-- RFQs (Request for Quotes)
CREATE TABLE IF NOT EXISTS rfqs (
    id SERIAL PRIMARY KEY,
    buyer_id INTEGER REFERENCES user_identities(id) NOT NULL,
    rfq_number VARCHAR(20) UNIQUE NOT NULL,  -- RFQ-1234
    
    -- Requirements
    quantity_kg DECIMAL(10,2) NOT NULL,
    variety VARCHAR(100),
    processing_method VARCHAR(50),  -- WASHED, NATURAL, HONEY
    grade VARCHAR(20),  -- G1, G2, G3
    delivery_location VARCHAR(200),
    delivery_deadline DATE,
    additional_specs JSONB,  -- {min_cup_score: 85, certifications: ['Organic']}
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'OPEN' NOT NULL,  -- OPEN, PARTIALLY_FILLED, FULFILLED, CANCELLED, EXPIRED
    
    -- Voice/text input
    voice_recording_url TEXT,
    transcript TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rfqs_buyer ON rfqs(buyer_id);
CREATE INDEX IF NOT EXISTS idx_rfqs_status ON rfqs(status);
CREATE INDEX IF NOT EXISTS idx_rfqs_deadline ON rfqs(delivery_deadline);
CREATE INDEX IF NOT EXISTS idx_rfqs_number ON rfqs(rfq_number);

-- Cooperative offers
CREATE TABLE IF NOT EXISTS rfq_offers (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    cooperative_id INTEGER REFERENCES organizations(id) NOT NULL,
    offer_number VARCHAR(20) UNIQUE NOT NULL,  -- OFF-5678
    
    -- Offer details
    quantity_offered_kg DECIMAL(10,2) NOT NULL,
    price_per_kg DECIMAL(8,2) NOT NULL,
    delivery_timeline VARCHAR(100),  -- "Ready by Feb 10" or "2 weeks"
    quality_certifications JSONB,  -- ['Organic', 'Fair Trade']
    sample_photos TEXT[],  -- Array of URLs
    voice_pitch_url TEXT,  -- Voice message from cooperative
    
    -- Status
    status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,  -- PENDING, ACCEPTED, REJECTED, WITHDRAWN, EXPIRED
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rfq_offers_rfq ON rfq_offers(rfq_id);
CREATE INDEX IF NOT EXISTS idx_rfq_offers_coop ON rfq_offers(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_rfq_offers_status ON rfq_offers(status);
CREATE INDEX IF NOT EXISTS idx_rfq_offers_number ON rfq_offers(offer_number);

-- RFQ offer acceptances (buyer accepts cooperative offer)
CREATE TABLE IF NOT EXISTS rfq_acceptances (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    offer_id INTEGER REFERENCES rfq_offers(id) NOT NULL,
    acceptance_number VARCHAR(20) UNIQUE NOT NULL,  -- ACC-9012
    
    -- Acceptance details
    quantity_accepted_kg DECIMAL(10,2) NOT NULL,  -- May be partial
    payment_terms VARCHAR(50),  -- NET_30, NET_60, ADVANCE, ESCROW
    payment_status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, ESCROWED, RELEASED, COMPLETED
    delivery_status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, IN_TRANSIT, DELIVERED, CONFIRMED
    
    -- Metadata
    accepted_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    payment_released_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rfq_acceptances_rfq ON rfq_acceptances(rfq_id);
CREATE INDEX IF NOT EXISTS idx_rfq_acceptances_offer ON rfq_acceptances(offer_id);
CREATE INDEX IF NOT EXISTS idx_rfq_acceptances_payment ON rfq_acceptances(payment_status);
CREATE INDEX IF NOT EXISTS idx_rfq_acceptances_delivery ON rfq_acceptances(delivery_status);

-- Broadcast tracking (which cooperatives were notified)
CREATE TABLE IF NOT EXISTS rfq_broadcasts (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER REFERENCES rfqs(id) NOT NULL,
    cooperative_id INTEGER REFERENCES organizations(id) NOT NULL,
    
    -- Why this cooperative was selected
    broadcast_reason VARCHAR(100),  -- "Region match", "Variety match", etc.
    relevance_score DECIMAL(3,2),  -- 0.00 to 1.00
    
    -- Engagement tracking
    notified_at TIMESTAMP DEFAULT NOW(),
    viewed_at TIMESTAMP,
    responded_at TIMESTAMP,
    
    UNIQUE(rfq_id, cooperative_id)
);

CREATE INDEX IF NOT EXISTS idx_rfq_broadcasts_rfq ON rfq_broadcasts(rfq_id);
CREATE INDEX IF NOT EXISTS idx_rfq_broadcasts_coop ON rfq_broadcasts(cooperative_id);

-- Comments for documentation
COMMENT ON TABLE rfqs IS 'Buyer requests for quotes from cooperatives';
COMMENT ON TABLE rfq_offers IS 'Cooperative offers in response to RFQs';
COMMENT ON TABLE rfq_acceptances IS 'Buyer acceptances of cooperative offers';
COMMENT ON TABLE rfq_broadcasts IS 'Tracks which cooperatives were notified about each RFQ';

COMMENT ON COLUMN rfqs.additional_specs IS 'JSON with min_cup_score, certifications, moisture_max, etc.';
COMMENT ON COLUMN rfq_offers.quality_certifications IS 'JSON array of certifications: ["Organic", "Fair Trade"]';
COMMENT ON COLUMN rfq_broadcasts.relevance_score IS 'Matching score 0-1 based on region, variety, capacity, reputation';
