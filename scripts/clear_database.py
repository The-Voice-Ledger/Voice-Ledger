"""
Clear all data from Neon database (for fresh migration)
"""

from database.models import SessionLocal, Base, engine
from database.crud import get_all_batches, get_all_farmers
from sqlalchemy import text

def clear_database():
    """Clear all data from tables."""
    db = SessionLocal()
    
    try:
        print("Clearing database...")
        
        # Delete in correct order (respecting foreign keys)
        db.execute(text("DELETE FROM epcis_events"))
        db.execute(text("DELETE FROM verifiable_credentials"))
        db.execute(text("DELETE FROM offline_queue"))
        db.execute(text("DELETE FROM coffee_batches"))
        db.execute(text("DELETE FROM farmer_identities"))
        
        db.commit()
        print("✓ Database cleared")
        
    except Exception as e:
        print(f"✗ Error clearing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    confirm = input("Clear all data from Neon database? (yes/no): ")
    if confirm.lower() == "yes":
        clear_database()
    else:
        print("Cancelled")
