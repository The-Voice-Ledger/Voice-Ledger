"""
Database Migration: Add Quality Assessment Fields to CoffeeBatch

Adds cupping score, moisture, screen size, defect count, defect category,
and sensory notes columns.  These are populated by the cooperative manager
during physical verification.

Author: Voice Ledger Team
Date: March 9, 2026
"""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv()

from database import get_db


def migrate():
    """Add quality assessment columns to coffee_batches table."""

    columns = [
        ("cupping_score",    "FLOAT"),
        ("moisture_pct",     "FLOAT"),
        ("screen_size",      "VARCHAR(20)"),
        ("defect_count",     "INTEGER"),
        ("defect_category",  "VARCHAR(20)"),
        ("sensory_notes",    "JSONB"),
    ]

    with get_db() as db:
        for col_name, col_type in columns:
            try:
                db.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE coffee_batches ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
                db.commit()
                print(f"  + {col_name} ({col_type})")
            except Exception as e:
                db.rollback()
                if "already exists" in str(e).lower():
                    print(f"  ~ {col_name} already exists, skipping")
                else:
                    print(f"  ! {col_name} FAILED: {e}")

    print("\n[OK] Quality fields migration complete.")


if __name__ == "__main__":
    migrate()
