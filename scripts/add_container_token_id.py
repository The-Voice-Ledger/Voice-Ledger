#!/usr/bin/env python3
"""
Add container_token_id column to aggregation_relationships table.

This migration adds blockchain token tracking for aggregated containers.
Part of Phase 2: Container Token Minting.
"""

from sqlalchemy import create_engine, text, BigInteger, Column, MetaData, Table
from sqlalchemy.exc import OperationalError
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    exit(1)

engine = create_engine(DATABASE_URL)

def add_container_token_id_column():
    """Add container_token_id column to aggregation_relationships table"""
    
    with engine.connect() as conn:
        # Check if column already exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'aggregation_relationships' 
            AND column_name = 'container_token_id'
        """)
        
        result = conn.execute(check_query)
        if result.fetchone():
            print("✅ Column container_token_id already exists, skipping")
            return
        
        # Add the column
        print("Adding container_token_id column...")
        alter_query = text("""
            ALTER TABLE aggregation_relationships 
            ADD COLUMN container_token_id BIGINT
        """)
        conn.execute(alter_query)
        
        # Add index for performance
        print("Creating index on container_token_id...")
        index_query = text("""
            CREATE INDEX IF NOT EXISTS ix_aggregation_relationships_container_token_id 
            ON aggregation_relationships(container_token_id)
        """)
        conn.execute(index_query)
        
        conn.commit()
        print("✅ Successfully added container_token_id column with index")

if __name__ == "__main__":
    print("="*60)
    print("Migration: Add container_token_id to aggregation_relationships")
    print("="*60)
    
    try:
        add_container_token_id_column()
        print("\n✅ Migration completed successfully!")
    except OperationalError as e:
        print(f"\n❌ Migration failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
