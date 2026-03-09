"""
Migration: Add settlement & payment-coordination columns.

Adds columns to:
  - rfq_acceptances  (buyer payment + coop payout tracking)
  - buyer_commitments (buyer payment + coop payout tracking)

Run:
    cd /path/to/Voice-Ledger
    ./venv/bin/python database/migrations/add_settlement_columns.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# ── Columns to add ─────────────────────────────────────────────────────────
# (table, column, sql_type, default)

COLUMNS = [
    # --- rfq_acceptances: payment coordination ---
    ("rfq_acceptances", "payment_method",                  "VARCHAR(30)",  None),
    ("rfq_acceptances", "payment_receipt_url",             "VARCHAR(500)", None),
    ("rfq_acceptances", "payment_confirmed_by_buyer_at",   "TIMESTAMP",    None),
    ("rfq_acceptances", "payment_received_by_coop_at",     "TIMESTAMP",    None),
    ("rfq_acceptances", "payment_dispute_reason",          "TEXT",         None),
    ("rfq_acceptances", "payment_disputed_at",             "TIMESTAMP",    None),
    # rfq_acceptances: buyer settlement
    ("rfq_acceptances", "settlement_tx_hash",              "VARCHAR(66)",  None),
    ("rfq_acceptances", "settlement_recorded_at",          "TIMESTAMP",    None),
    ("rfq_acceptances", "settlement_blockchain_confirmed", "BOOLEAN",      "FALSE"),
    # rfq_acceptances: cooperative payout
    ("rfq_acceptances", "coop_payout_tx_hash",             "VARCHAR(66)",  None),
    ("rfq_acceptances", "coop_payout_at",                  "TIMESTAMP",    None),
    ("rfq_acceptances", "coop_payout_confirmed",           "BOOLEAN",      "FALSE"),

    # --- buyer_commitments: payment coordination ---
    ("buyer_commitments", "payment_method",                  "VARCHAR(30)",  None),
    ("buyer_commitments", "payment_receipt_url",             "VARCHAR(500)", None),
    ("buyer_commitments", "payment_confirmed_by_buyer_at",   "TIMESTAMP",    None),
    ("buyer_commitments", "payment_received_by_coop_at",     "TIMESTAMP",    None),
    ("buyer_commitments", "payment_dispute_reason",          "TEXT",         None),
    ("buyer_commitments", "payment_disputed_at",             "TIMESTAMP",    None),
    # buyer_commitments: buyer settlement
    ("buyer_commitments", "settlement_tx_hash",              "VARCHAR(66)",  None),
    ("buyer_commitments", "settlement_recorded_at",          "TIMESTAMP",    None),
    ("buyer_commitments", "settlement_blockchain_confirmed", "BOOLEAN",      "FALSE"),
    # buyer_commitments: cooperative payout
    ("buyer_commitments", "coop_payout_tx_hash",             "VARCHAR(66)",  None),
    ("buyer_commitments", "coop_payout_at",                  "TIMESTAMP",    None),
    ("buyer_commitments", "coop_payout_confirmed",           "BOOLEAN",      "FALSE"),
]


def run():
    added = 0
    skipped = 0

    with engine.begin() as conn:
        for table, col, sql_type, default in COLUMNS:
            # Check if column already exists
            exists = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = :col"
            ), {"tbl": table, "col": col}).fetchone()

            if exists:
                print(f"  ⏭  {table}.{col} already exists")
                skipped += 1
                continue

            default_clause = f" DEFAULT {default}" if default else ""
            stmt = f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}{default_clause}"
            conn.execute(text(stmt))
            print(f"  ✅ {table}.{col} ({sql_type})")
            added += 1

    print(f"\nDone - {added} added, {skipped} skipped.")


if __name__ == "__main__":
    print("=== Migration: add_settlement_columns ===\n")
    run()
