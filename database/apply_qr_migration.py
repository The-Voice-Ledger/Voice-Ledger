"""
Apply migration to add QR code column to coffee_batches
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_FILE = 'database/migrations/add_qr_code_column.sql'

def run_migration():
    print(f"🔄 Running migration: {MIGRATION_FILE}...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        with open(MIGRATION_FILE, 'r') as f:
            migration_sql = f.read()
        
        cur.execute(migration_sql)
        conn.commit()
        
        print("✅ Migration completed successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
