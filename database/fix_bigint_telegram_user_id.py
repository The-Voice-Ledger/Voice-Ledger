"""
Fix telegram_user_id column in pending_registrations table to use BigInteger.

Telegram user IDs can exceed the PostgreSQL INTEGER max value (2,147,483,647).
This migration changes the column type to BIGINT.
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def run_migration():
    """Apply the BigInteger fix to pending_registrations table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("🔧 Altering pending_registrations.telegram_user_id to BIGINT...")
        
        # PostgreSQL: ALTER COLUMN type to BIGINT
        conn.execute(text("""
            ALTER TABLE pending_registrations 
            ALTER COLUMN telegram_user_id TYPE BIGINT;
        """))
        
        conn.commit()
        
        print("✅ Migration complete: telegram_user_id is now BIGINT")
        print("   This supports Telegram user IDs up to 9,223,372,036,854,775,807")

if __name__ == "__main__":
    print("Starting BigInteger migration for pending_registrations...")
    run_migration()
    print("\n🎉 All done!")
