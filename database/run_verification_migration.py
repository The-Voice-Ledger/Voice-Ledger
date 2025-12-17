"""
Run verification system database migration using SQLAlchemy
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
migration_file = 'database/migrations/add_verification_system.sql'

print('🔄 Running migration: Add verification and registration system...')
print(f'📁 Migration file: {migration_file}')
print(f'🗄️  Database: {DATABASE_URL.split("@")[1].split("?")[0] if "@" in DATABASE_URL else "hidden"}')
print()

# Create engine
engine = create_engine(DATABASE_URL)

# Read migration SQL
with open(migration_file, 'r') as f:
    migration_sql = f.read()

# Execute migration
with engine.connect() as conn:
    conn.execute(text(migration_sql))
    conn.commit()

print('✅ Migration completed successfully!')
print()
print('📊 Verifying tables...')

# Verify tables exist
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('organizations', 'pending_registrations', 'farmer_cooperatives', 'verification_evidence')
        ORDER BY table_name
    """))
    tables = result.fetchall()
    print(f'✅ New tables created: {len(tables)}')
    for table in tables:
        print(f'   - {table[0]}')
    
    # Verify new columns in user_identities
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'user_identities' 
        AND column_name IN ('role', 'organization_id', 'is_approved')
        ORDER BY column_name
    """))
    cols = result.fetchall()
    print(f'\n✅ user_identities new columns: {len(cols)}')
    for col in cols:
        print(f'   - {col[0]}')
    
    # Verify new columns in coffee_batches
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'coffee_batches' 
        AND column_name IN ('status', 'verification_token', 'verified_by_did', 'verifying_organization_id')
        ORDER BY column_name
    """))
    cols = result.fetchall()
    print(f'\n✅ coffee_batches new columns: {len(cols)}')
    for col in cols:
        print(f'   - {col[0]}')

print('\n🎉 Verification system database schema ready!')
