"""
Database Migration: Add Deforestation Check Fields to FarmerIdentity

Adds EUDR Article 10 compliance fields for satellite imagery verification.

Author: Voice Ledger Team
Date: December 22, 2025
Phase: 4 - Deforestation Detection
"""

from sqlalchemy import create_engine, Column, Float, String, Boolean, DateTime, JSON, text
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database import get_db

load_dotenv()

def migrate():
    """
    Add deforestation check fields to farmer_identities table.
    
    New fields:
    - deforestation_checked_at: When check was performed
    - deforestation_risk: LOW, MEDIUM, HIGH, UNKNOWN
    - deforestation_compliant: Boolean compliance status
    - tree_cover_loss_hectares: Hectares lost after Dec 31, 2020
    - deforestation_data_source: Data source (Global Forest Watch, etc.)
    - deforestation_confidence: Confidence score 0.0-1.0
    - deforestation_details: JSON with detailed results
    """
    
    print("🌳 Starting deforestation fields migration...")
    print("=" * 70)
    
    # Get database connection using context manager
    with get_db() as db:
        
        # SQL statements to add new columns
        migration_sql = [
        # Deforestation check timestamp
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_checked_at TIMESTAMPTZ;
        """,
        
        # Risk level
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_risk VARCHAR(20) 
        CHECK (deforestation_risk IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'));
        """,
        
        # Compliance status
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_compliant BOOLEAN;
        """,
        
        # Tree cover loss amount
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS tree_cover_loss_hectares FLOAT;
        """,
        
        # Data source
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_data_source VARCHAR(200);
        """,
        
        # Confidence score
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_confidence FLOAT 
        CHECK (deforestation_confidence >= 0.0 AND deforestation_confidence <= 1.0);
        """,
        
        # Detailed results (JSON)
        """
        ALTER TABLE farmer_identities 
        ADD COLUMN IF NOT EXISTS deforestation_details JSONB;
        """,
        
        # Create index for querying by deforestation status
        """
        CREATE INDEX IF NOT EXISTS idx_farmer_deforestation_compliant 
        ON farmer_identities(deforestation_compliant) 
        WHERE deforestation_compliant IS NOT NULL;
        """,
        
        # Create index for querying by risk level
        """
        CREATE INDEX IF NOT EXISTS idx_farmer_deforestation_risk 
        ON farmer_identities(deforestation_risk) 
        WHERE deforestation_risk IS NOT NULL;
        """
        ]
        
        # Execute migrations
        try:
            for i, sql in enumerate(migration_sql, 1):
                print(f"Executing migration step {i}/{len(migration_sql)}...")
                db.execute(text(sql))
                db.commit()
                print(f"✅ Step {i} complete")
            
            print()
            print("=" * 70)
            print("✅ Migration complete!")
            print()
            print("New fields added to farmer_identities:")
            print("  - deforestation_checked_at (TIMESTAMPTZ)")
            print("  - deforestation_risk (VARCHAR(20))")
            print("  - deforestation_compliant (BOOLEAN)")
            print("  - tree_cover_loss_hectares (FLOAT)")
            print("  - deforestation_data_source (VARCHAR(200))")
            print("  - deforestation_confidence (FLOAT)")
            print("  - deforestation_details (JSONB)")
            print()
            print("Indexes created:")
            print("  - idx_farmer_deforestation_compliant")
            print("  - idx_farmer_deforestation_risk")
            print()
            print("🇪🇺 EUDR Article 10 compliance now active!")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.rollback()
            raise


def rollback():
    """
    Rollback migration by removing deforestation fields.
    
    USE WITH CAUTION: This will delete all deforestation check data!
    """
    
    print("⚠️  WARNING: Rolling back deforestation fields migration")
    print("This will DELETE all deforestation check data!")
    
    confirmation = input("Type 'ROLLBACK' to confirm: ")
    if confirmation != "ROLLBACK":
        print("Rollback cancelled.")
        return
    
    with get_db() as db:
        
        rollback_sql = [
        "DROP INDEX IF EXISTS idx_farmer_deforestation_risk;",
        "DROP INDEX IF EXISTS idx_farmer_deforestation_compliant;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_details;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_confidence;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_data_source;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS tree_cover_loss_hectares;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_compliant;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_risk;",
        "ALTER TABLE farmer_identities DROP COLUMN IF EXISTS deforestation_checked_at;"
        ]
        
        try:
            for sql in rollback_sql:
                db.execute(text(sql))
                db.commit()
            
            print("✅ Rollback complete. Deforestation fields removed.")
            
        except Exception as e:
            print(f"❌ Rollback failed: {str(e)}")
            db.rollback()
            raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
