"""
Migration: Add GPS-verified photo fields to farmer_identities for EUDR compliance
Date: 2025-12-22
Purpose: Enable photo-based GPS verification for EU Deforestation Regulation (EUDR) Article 9 compliance
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Apply GPS photo verification schema changes."""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("Starting migration: Add GPS photo fields to farmer_identities")
        
        # Add photo verification columns to farmer_identities table
        session.execute(text("""
            ALTER TABLE farmer_identities 
            ADD COLUMN IF NOT EXISTS farm_photo_url VARCHAR(500),
            ADD COLUMN IF NOT EXISTS farm_photo_hash VARCHAR(64),
            ADD COLUMN IF NOT EXISTS farm_photo_ipfs VARCHAR(100),
            ADD COLUMN IF NOT EXISTS photo_latitude FLOAT,
            ADD COLUMN IF NOT EXISTS photo_longitude FLOAT,
            ADD COLUMN IF NOT EXISTS photo_timestamp TIMESTAMP,
            ADD COLUMN IF NOT EXISTS gps_verified_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS photo_device_make VARCHAR(100),
            ADD COLUMN IF NOT EXISTS photo_device_model VARCHAR(100),
            ADD COLUMN IF NOT EXISTS blockchain_proof_hash VARCHAR(66)
        """))
        logger.info("✓ Added GPS photo fields to farmer_identities")
        
        # Create indexes
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_farmer_gps_verified ON farmer_identities(gps_verified_at)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_farmer_photo_hash ON farmer_identities(farm_photo_hash)
        """))
        logger.info("✓ Created indexes on farmer_identities")
        
        # Create verification_photos table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS verification_photos (
                id SERIAL PRIMARY KEY,
                batch_id INTEGER REFERENCES coffee_batches(id) ON DELETE CASCADE,
                photo_url VARCHAR(500) NOT NULL,
                photo_hash VARCHAR(64) NOT NULL,
                photo_ipfs VARCHAR(100),
                latitude FLOAT,
                longitude FLOAT,
                photo_timestamp TIMESTAMP,
                device_make VARCHAR(100),
                device_model VARCHAR(100),
                verified_at TIMESTAMP DEFAULT NOW(),
                distance_from_farm_km FLOAT,
                blockchain_proof_hash VARCHAR(66),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(photo_hash)
            )
        """))
        logger.info("✓ Created verification_photos table")
        
        # Create indexes for verification_photos
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verification_photos_batch ON verification_photos(batch_id)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verification_photos_hash ON verification_photos(photo_hash)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verification_photos_verified_at ON verification_photos(verified_at)
        """))
        logger.info("✓ Created indexes on verification_photos")
        
        # Create EUDR compliance view
        session.execute(text("""
            CREATE OR REPLACE VIEW farmer_eudr_compliance AS
            SELECT 
                fi.id,
                fi.farmer_id,
                fi.name,
                fi.latitude AS registered_latitude,
                fi.longitude AS registered_longitude,
                fi.photo_latitude,
                fi.photo_longitude,
                fi.gps_verified_at,
                fi.farm_photo_ipfs,
                fi.blockchain_proof_hash,
                CASE 
                    WHEN fi.latitude IS NULL OR fi.longitude IS NULL THEN 'NO_GPS'
                    WHEN fi.gps_verified_at IS NULL THEN 'GPS_UNVERIFIED'
                    WHEN fi.blockchain_proof_hash IS NULL THEN 'NOT_ANCHORED'
                    ELSE 'COMPLIANT'
                END AS compliance_status,
                COUNT(DISTINCT cb.id) AS total_batches,
                COUNT(DISTINCT vp.id) AS verified_batches
            FROM farmer_identities fi
            LEFT JOIN coffee_batches cb ON fi.id = cb.farmer_id
            LEFT JOIN verification_photos vp ON cb.id = vp.batch_id
            GROUP BY fi.id, fi.farmer_id, fi.name, fi.latitude, fi.longitude, 
                     fi.photo_latitude, fi.photo_longitude, fi.gps_verified_at, 
                     fi.farm_photo_ipfs, fi.blockchain_proof_hash
        """))
        logger.info("✓ Created farmer_eudr_compliance view")
        
        session.commit()
        logger.info("✅ Migration completed successfully")
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_migration()
