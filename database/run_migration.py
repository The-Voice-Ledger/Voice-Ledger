"""
Run database migrations to add EUDR fields and fix relationships
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

migrations = [
    ('database/migrations/add_eudr_fields.sql', 'Add EUDR geolocation fields to farmer_identities'),
    ('database/migrations/add_origin_fields.sql', 'Add EUDR origin fields to coffee_batches'),
    ('database/migrations/add_blockchain_confirmed_at.sql', 'Add blockchain confirmation timestamp to epcis_events')
]

# Execute migrations
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    for migration_file, description in migrations:
        print(f"\n🔄 Running migration: {description}...")
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        cur.execute(migration_sql)
        conn.commit()
        print(f"✅ {description} - completed!")
    
    print("\n" + "="*60)
    print("✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
    print("="*60)
    print("\nUpdated schema:")
    print("\n📍 farmer_identities:")
    print("  - latitude, longitude, region, country_code")
    print("  - farm_size_hectares, certification_status")
    print("\n🌍 coffee_batches:")
    print("  - origin_country, origin_region, farm_name")
    print("  - process_method (alias for DPP)")
    print("\n📜 verifiable_credentials:")
    print("  - farmer_id (FK to farmer_identities)")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    raise
