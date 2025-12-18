"""
Migration: Add exporters, buyers, and user_reputation tables for Lab 9 Extension

Extends the Voice Ledger system to support multiple actor types:
- Exporters with licensing and shipping capacity
- Buyers with business types and quality preferences
- Reputation tracking for all users
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def run_migration():
    """Create exporters, buyers, and user_reputation tables"""
    
    engine = create_engine(DATABASE_URL)
    
    # SQL statements for table creation
    statements = [
        # 1. Update organizations table to include organization_type
        """
        ALTER TABLE organizations 
        ADD COLUMN IF NOT EXISTS organization_type VARCHAR(50) DEFAULT 'COOPERATIVE';
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_organizations_type 
        ON organizations(organization_type);
        """,
        
        # 2. Create exporters table
        """
        CREATE TABLE IF NOT EXISTS exporters (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER REFERENCES organizations(id) UNIQUE,
            export_license VARCHAR(100) NOT NULL,
            port_access VARCHAR(100),
            shipping_capacity_tons DECIMAL(10,2),
            active_shipping_lines JSONB,
            customs_clearance_capability BOOLEAN DEFAULT FALSE,
            certifications JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_exporters_org 
        ON exporters(organization_id);
        """,
        
        # 3. Create buyers table
        """
        CREATE TABLE IF NOT EXISTS buyers (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER REFERENCES organizations(id) UNIQUE,
            business_type VARCHAR(50) NOT NULL,
            country VARCHAR(100) NOT NULL,
            target_volume_tons_annual DECIMAL(10,2),
            quality_preferences JSONB,
            payment_terms VARCHAR(50),
            import_licenses JSONB,
            certifications_required JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_buyers_org 
        ON buyers(organization_id);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_buyers_business_type 
        ON buyers(business_type);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_buyers_country 
        ON buyers(country);
        """,
        
        # 4. Create user_reputation table
        """
        CREATE TABLE IF NOT EXISTS user_reputation (
            user_id INTEGER PRIMARY KEY REFERENCES user_identities(id),
            completed_transactions INTEGER DEFAULT 0,
            total_volume_kg DECIMAL(12,2) DEFAULT 0,
            on_time_deliveries INTEGER DEFAULT 0,
            quality_disputes INTEGER DEFAULT 0,
            average_rating DECIMAL(3,2),
            reputation_level VARCHAR(20) DEFAULT 'BRONZE',
            last_transaction_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_reputation_level 
        ON user_reputation(reputation_level);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_reputation_rating 
        ON user_reputation(average_rating);
        """,
        
        # 5. Add role-specific fields to pending_registrations
        """
        ALTER TABLE pending_registrations 
        ADD COLUMN IF NOT EXISTS export_license VARCHAR(100),
        ADD COLUMN IF NOT EXISTS port_access VARCHAR(100),
        ADD COLUMN IF NOT EXISTS shipping_capacity_tons DECIMAL(10,2),
        ADD COLUMN IF NOT EXISTS business_type VARCHAR(50),
        ADD COLUMN IF NOT EXISTS country VARCHAR(100),
        ADD COLUMN IF NOT EXISTS target_volume_tons_annual DECIMAL(10,2),
        ADD COLUMN IF NOT EXISTS quality_preferences JSONB;
        """
    ]
    
    with engine.connect() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
                conn.commit()
                print(f"✅ Executed: {statement[:80]}...")
            except Exception as e:
                print(f"❌ Error: {e}")
                print(f"   Statement: {statement[:100]}...")
                conn.rollback()
    
    print("\n✅ Migration completed!")
    print("\nCreated tables:")
    print("  - exporters (organization-specific exporter details)")
    print("  - buyers (organization-specific buyer details)")
    print("  - user_reputation (reputation tracking for all users)")
    print("\nUpdated tables:")
    print("  - organizations (added organization_type column)")
    print("  - pending_registrations (added role-specific fields)")

if __name__ == "__main__":
    run_migration()
