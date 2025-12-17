"""
Add new columns to existing tables for verification system
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print('🔄 Adding new columns to existing tables...\n')

with engine.connect() as conn:
    # Add columns to user_identities
    print('📝 Altering user_identities table...')
    conn.execute(text("""
        ALTER TABLE user_identities 
        ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'FARMER',
        ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id),
        ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS approved_by_admin_id INTEGER;
    """))
    conn.commit()
    print('✅ user_identities updated')
    
    # Add indexes
    print('\n📝 Creating indexes on user_identities...')
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_role ON user_identities(role);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_org ON user_identities(organization_id);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_approved ON user_identities(is_approved);"))
    conn.commit()
    print('✅ Indexes created')
    
    # Add columns to coffee_batches
    print('\n📝 Altering coffee_batches table...')
    conn.execute(text("""
        ALTER TABLE coffee_batches 
        ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'PENDING_VERIFICATION',
        ADD COLUMN IF NOT EXISTS verification_token VARCHAR(64) UNIQUE,
        ADD COLUMN IF NOT EXISTS verification_expires_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS verification_used BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS verified_quantity FLOAT,
        ADD COLUMN IF NOT EXISTS verified_by_did VARCHAR(200),
        ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS verification_notes TEXT,
        ADD COLUMN IF NOT EXISTS has_photo_evidence BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS verifying_organization_id INTEGER REFERENCES organizations(id);
    """))
    conn.commit()
    print('✅ coffee_batches updated')
    
    # Add indexes
    print('\n📝 Creating indexes on coffee_batches...')
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_batch_status ON coffee_batches(status);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_verification_token ON coffee_batches(verification_token);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_verified_by_did ON coffee_batches(verified_by_did);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_batch_verifying_org ON coffee_batches(verifying_organization_id);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_verification_expires_at ON coffee_batches(verification_expires_at);"))
    conn.commit()
    print('✅ Indexes created')
    
    # Backfill existing data
    print('\n📝 Backfilling existing data...')
    conn.execute(text("UPDATE coffee_batches SET status = 'VERIFIED' WHERE status IS NULL;"))
    conn.execute(text("UPDATE user_identities SET role = 'FARMER', is_approved = TRUE, approved_at = created_at WHERE role IS NULL;"))
    conn.commit()
    print('✅ Backfill complete')

print('\n🎉 Database schema migration complete!')
