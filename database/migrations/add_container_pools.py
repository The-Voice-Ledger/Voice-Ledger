"""
Database Migration: Add Container Pool & Buyer Commitment tables

Creates the demand-side aggregation model for shared container buying.
SME roasters from the same region can co-purchase a container by committing
fractional quantities into a geographically grouped pool.

Author: Voice Ledger Team
Date: March 2026
Phase: 4.6 - Shared Container Buying
"""

import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db

load_dotenv()


def migrate():
    """
    Create container_pools and buyer_commitments tables.

    Tables:
      container_pools     -- demand-side pool per destination region
      buyer_commitments   -- individual buyer fractional commitments
    """

    print("Starting container-pool migration...")
    print("=" * 70)

    migration_sql = [
        # ── container_pools ──────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS container_pools (
            id              SERIAL PRIMARY KEY,
            container_offering_id INTEGER NOT NULL
                            REFERENCES container_offerings(id),
            destination_region    VARCHAR(50) NOT NULL,
            destination_port      VARCHAR(100) NOT NULL,
            fill_target_kg        DOUBLE PRECISION NOT NULL,
            filled_kg             DOUBLE PRECISION NOT NULL DEFAULT 0,
            status                VARCHAR(20) NOT NULL DEFAULT 'FILLING',
            deadline              TIMESTAMPTZ,
            estimated_departure   TIMESTAMPTZ,
            estimated_arrival     TIMESTAMPTZ,
            shipping_reference    VARCHAR(100),
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            updated_at            TIMESTAMPTZ DEFAULT NOW(),
            confirmed_at          TIMESTAMPTZ,
            shipped_at            TIMESTAMPTZ
        );
        """,

        # Indexes for container_pools
        """
        CREATE INDEX IF NOT EXISTS idx_pool_offering
            ON container_pools(container_offering_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_pool_region
            ON container_pools(destination_region);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_pool_status
            ON container_pools(status);
        """,

        # ── buyer_commitments ────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS buyer_commitments (
            id              SERIAL PRIMARY KEY,
            pool_id         INTEGER NOT NULL
                            REFERENCES container_pools(id),
            buyer_id        INTEGER NOT NULL
                            REFERENCES user_identities(id),
            organization_id INTEGER
                            REFERENCES organizations(id),
            quantity_kg     DOUBLE PRECISION NOT NULL,
            unit_price      DOUBLE PRECISION NOT NULL,
            total_amount    DOUBLE PRECISION NOT NULL,
            currency        VARCHAR(3) DEFAULT 'USD',
            delivery_country VARCHAR(2),
            delivery_city   VARCHAR(200),
            delivery_address TEXT,
            status          VARCHAR(20) NOT NULL DEFAULT 'COMMITTED',
            payment_reference VARCHAR(100),
            paid_at         TIMESTAMPTZ,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        # Indexes for buyer_commitments
        """
        CREATE INDEX IF NOT EXISTS idx_commitment_pool
            ON buyer_commitments(pool_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_commitment_buyer
            ON buyer_commitments(buyer_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_commitment_status
            ON buyer_commitments(status);
        """,
    ]

    with get_db() as db:
        try:
            for i, sql in enumerate(migration_sql, 1):
                print(f"  Step {i}/{len(migration_sql)}...")
                db.execute(text(sql))
                db.commit()
                print(f"  Step {i} complete")

            print()
            print("=" * 70)
            print("Migration complete!")
            print()
            print("New tables:")
            print("  - container_pools       (demand-side aggregation)")
            print("  - buyer_commitments     (fractional buyer purchases)")
            print()
            print("Indexes created on offering, region, status, pool, buyer")

        except Exception as e:
            db.rollback()
            print(f"Migration failed: {e}")
            raise


def rollback():
    """Drop the new tables (safe to re-run)."""
    print("Rolling back container-pool migration...")
    with get_db() as db:
        db.execute(text("DROP TABLE IF EXISTS buyer_commitments CASCADE;"))
        db.execute(text("DROP TABLE IF EXISTS container_pools CASCADE;"))
        db.commit()
        print("Rollback complete -- tables dropped.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if args.rollback:
        rollback()
    else:
        migrate()
