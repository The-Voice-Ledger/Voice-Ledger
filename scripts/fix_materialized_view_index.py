#!/usr/bin/env python3
"""
Fix Materialized View Index for Concurrent Refresh

Adds a unique index to product_farmer_lineage to enable concurrent refresh.
This is required for the database trigger to work properly.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from sqlalchemy import text

def fix_materialized_view_index():
    """Add unique index to product_farmer_lineage materialized view"""
    print("🔧 Fixing materialized view index...")
    
    with get_db() as db:
        try:
            # Check if unique index already exists
            check_sql = """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'product_farmer_lineage' 
            AND indexdef LIKE '%UNIQUE%'
            """
            result = db.execute(text(check_sql)).fetchall()
            
            if result:
                print(f"  ℹ️  Unique index already exists: {result[0][0]}")
                return True
            
            print("  📊 Creating unique index on (product_id, farmer_id)...")
            
            # Create unique index - combination of product_id and farmer_id
            # This allows the same product to have multiple farmers and vice versa
            # but prevents duplicate (product, farmer) pairs
            create_index_sql = """
            CREATE UNIQUE INDEX idx_product_farmer_lineage_unique 
            ON product_farmer_lineage (product_id, farmer_id);
            """
            
            db.execute(text(create_index_sql))
            db.commit()
            
            print("  ✅ Unique index created successfully!")
            print("  📋 Index name: idx_product_farmer_lineage_unique")
            print("  🔑 Columns: (product_id, farmer_id)")
            
            # Verify it worked
            verify_sql = """
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'product_farmer_lineage' 
            AND indexname = 'idx_product_farmer_lineage_unique'
            """
            result = db.execute(text(verify_sql)).fetchone()
            
            if result:
                print(f"\n  ✅ Verified: {result[0]}")
                print(f"     Definition: {result[1]}")
                return True
            else:
                print("  ⚠️  Index created but verification failed")
                return False
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    print("="*60)
    print("Fix Materialized View Index")
    print("="*60)
    
    success = fix_materialized_view_index()
    
    if success:
        print("\n" + "="*60)
        print("✅ Materialized view can now be refreshed concurrently!")
        print("="*60)
        print("\nYou can now:")
        print("1. Re-run the E2E test: python tests/test_e2e_container_minting.py")
        print("2. Or test via Telegram bot with /pack command")
        print("")
        return True
    else:
        print("\n❌ Failed to fix materialized view index")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
