#!/usr/bin/env python3
"""
Verify Coffee Batch

This script allows an administrator or authorized user to verify a Coffee Batch
manually from the command line. It updates the database, issues a verification
credential, and records an EPCIS verification event.
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Ensure UTF-8 output for Windows terminals (avoid UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_db
from database.models import CoffeeBatch, UserIdentity
from ssi.user_identity import get_user_by_telegram_id

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_batch(batch_id: str, verifier_telegram_id: str, verified_quantity: float = None, notes: str = None) -> bool:
    """Manually verify a batch using a verifier's telegram ID."""
    try:
        with get_db() as db:
            # Look up the user who is verifying
            user = get_user_by_telegram_id(verifier_telegram_id, db)
            if not user:
                user = db.query(UserIdentity).filter(UserIdentity.telegram_user_id == str(verifier_telegram_id)).first()
                if not user:
                    print(f"❌ Verifier User with Telegram ID {verifier_telegram_id} not found")
                    return False

            if not user.organization_id:
                print(f"❌ User {user.telegram_first_name} is not associated with an organization. Only cooperative managers/exporters can verify.")
                return False

            # Validate batch
            batch = db.query(CoffeeBatch).filter(
                (CoffeeBatch.batch_id == batch_id) | (CoffeeBatch.batch_number == batch_id)
            ).first()
            
            if not batch:
                print(f"❌ Batch with ID/Number '{batch_id}' not found.")
                return False

            if batch.status == "VERIFIED":
                print(f"⚠️ Batch {batch.batch_id} is already verified.")
                return False

            # Set verified quantity to claimed quantity if not provided
            if verified_quantity is None:
                verified_quantity = batch.quantity_kg
                print(f"ℹ️ Verified quantity not provided. Defaulting to claimed quantity: {verified_quantity} kg")

            print(f"\n📦 Verifying Batch: {batch.batch_id} (Claimed: {batch.quantity_kg} kg)")
            print(f"👤 Verifier: {user.telegram_first_name} (Role: {user.role}, Org ID: {user.organization_id})")

            # Update batch model
            batch.status = "VERIFIED"
            batch.verified_quantity = verified_quantity
            batch.verification_notes = notes
            batch.verified_by_did = user.did
            batch.verifying_organization_id = user.organization_id
            batch.verified_at = datetime.utcnow()
            batch.verification_used = True
            batch.has_photo_evidence = False
            
            db.commit()
            print("  ✅ Database updated successfully")
            
            # Issue verification credential
            try:
                from ssi.verification_credentials import issue_verification_credential
                credential = issue_verification_credential(
                    batch_id=batch.batch_id,
                    farmer_did=batch.created_by_did,
                    organization_id=user.organization_id,
                    verified_quantity_kg=verified_quantity,
                    claimed_quantity_kg=batch.quantity_kg,
                    variety=batch.variety,
                    origin=batch.origin,
                    quality_notes=notes,
                    verifier_did=user.did,
                    verifier_name=user.telegram_first_name,
                    has_photo_evidence=False
                )
                print("  ✅ Verification credential issued successfully")
            except Exception as e:
                logger.error(f"Failed to issue verification credential: {e}")
                print(f"  ⚠️ Warning: Failed to issue verification credential: {e}")

            # Create EPCIS event
            if user.organization:
                try:
                    from voice.verification.verification_events import create_verification_event
                    event = create_verification_event(
                        batch_id=batch.batch_id,
                        verifier_did=user.did,
                        verifier_name=user.telegram_first_name or "Manager",
                        organization_did=user.organization.did,
                        organization_name=user.organization.name,
                        verified_quantity_kg=verified_quantity,
                        claimed_quantity_kg=batch.quantity_kg,
                        quality_notes=notes,
                        location=batch.origin or "",
                        has_photo_evidence=False
                    )
                    if event:
                        print(f"  ✅ Verification EPCIS event created (IPFS: {event.ipfs_cid[:10]}...)")
                except Exception as e:
                    logger.error(f"Failed to create verification event: {e}")
                    print(f"  ⚠️ Warning: Failed to create EPCIS event: {e}")

            print(f"\n🎉 Batch {batch.batch_id} successfully verified!")
            return True

    except Exception as e:
        logger.error(f"Error verifying batch: {e}", exc_info=True)
        print(f"❌ Error during verification: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Verify a Coffee Batch manually")
    parser.add_argument(
        "--batch-id", 
        required=True, 
        help="The short batch_id (e.g., BATCH-1234) or batch_number of the coffee batch"
    )
    parser.add_argument(
        "--telegram-id", 
        required=True, 
        help="The Telegram ID of the user performing the verification (must be linked to an Organization)"
    )
    parser.add_argument(
        "--quantity", 
        type=float,
        help="The actual verified quantity (kg). If omitted, defaults to the claimed quantity."
    )
    parser.add_argument(
        "--notes", 
        type=str,
        help="Optional notes describing the verified quality, grade, etc."
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📦 VOICE LEDGER BATCH VERIFICATION TOOL 📦")
    print("=" * 60)
    
    verify_batch(
        batch_id=args.batch_id,
        verifier_telegram_id=args.telegram_id,
        verified_quantity=args.quantity,
        notes=args.notes
    )

if __name__ == "__main__":
    main()
