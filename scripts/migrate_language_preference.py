#!/usr/bin/env python3
"""
Database Migration Helper for Conversational AI Feature

Options:
1. Drop all data and recreate (fresh start)
2. Run migration to add language preference (preserve data)

Usage:
    python scripts/migrate_language_preference.py --drop-all    # Fresh start
    python scripts/migrate_language_preference.py --migrate     # Add columns only
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import Base, SessionLocal, engine
from sqlalchemy import text
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def drop_all_and_recreate():
    """Drop all tables and recreate from models (DESTRUCTIVE)"""
    print("\n⚠️  WARNING: This will DELETE ALL DATA in the database!")
    confirm = input("Type 'YES' to continue: ")
    
    if confirm != 'YES':
        print("Migration cancelled.")
        return
    
    logger.info("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    logger.info("Creating all tables from models...")
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ Database recreated successfully!")
    print("\nAll tables recreated with fresh schema.")
    print("Language preference columns are included in UserIdentity table.")


def run_migration():
    """Run migration to add language preference columns (non-destructive)"""
    logger.info("Running language preference migration...")
    
    db = SessionLocal()
    try:
        # Read migration SQL
        migration_file = project_root / "database" / "migrations" / "add_language_preference.sql"
        
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return
        
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        # Execute migration
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for statement in statements:
            if statement.strip():
                logger.info(f"Executing: {statement[:60]}...")
                try:
                    result = db.execute(text(statement))
                    db.commit()
                    
                    # Show results if SELECT statement
                    if statement.strip().upper().startswith('SELECT'):
                        rows = result.fetchall()
                        for row in rows:
                            print(f"  {dict(row._mapping)}")
                except Exception as e:
                    logger.warning(f"Statement failed (may be normal if column exists): {e}")
                    db.rollback()
        
        logger.info("✅ Migration completed successfully!")
        print("\nLanguage preference columns added.")
        print("Existing users default to English ('en').")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_schema():
    """Check if language preference columns exist"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'user_identities' 
            AND column_name IN ('preferred_language', 'language_set_at')
            ORDER BY column_name
        """))
        
        columns = result.fetchall()
        
        if columns:
            print("\n✅ Language preference columns exist:")
            for col in columns:
                print(f"  - {col.column_name} ({col.data_type}): {col.column_default}")
        else:
            print("\n❌ Language preference columns NOT found.")
            print("Run migration with: python scripts/migrate_language_preference.py --migrate")
        
        # Count users by language
        result = db.execute(text("""
            SELECT preferred_language, COUNT(*) as count 
            FROM user_identities 
            WHERE preferred_language IS NOT NULL
            GROUP BY preferred_language
        """))
        
        counts = result.fetchall()
        if counts:
            print("\nUser language distribution:")
            for row in counts:
                lang_name = "English" if row.preferred_language == 'en' else "Amharic"
                print(f"  {row.preferred_language} ({lang_name}): {row.count} users")
        
    except Exception as e:
        logger.error(f"Schema check failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate database for conversational AI feature")
    parser.add_argument("--drop-all", action="store_true", help="Drop all data and recreate (DESTRUCTIVE)")
    parser.add_argument("--migrate", action="store_true", help="Add language preference columns (safe)")
    parser.add_argument("--check", action="store_true", help="Check if migration is needed")
    
    args = parser.parse_args()
    
    if args.drop_all:
        drop_all_and_recreate()
    elif args.migrate:
        run_migration()
    elif args.check:
        check_schema()
    else:
        print("Please specify an action:")
        print("  --drop-all  : Drop all data and recreate tables")
        print("  --migrate   : Add language preference columns")
        print("  --check     : Check current schema")
        parser.print_help()
