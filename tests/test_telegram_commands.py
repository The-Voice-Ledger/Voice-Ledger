#!/usr/bin/env python3
"""
Test suite for Telegram bot commands.

Tests all commands to ensure they work with both GTIN and batch_id formats.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import SessionLocal
from database.crud import get_batch_by_id_or_gtin, get_batch_by_gtin
from ssi.user_identity import get_user_by_telegram_id


def test_batch_lookup():
    """Test GTIN and batch_id lookup functionality."""
    print("\n=== Testing Batch Lookup ===")
    
    db = SessionLocal()
    try:
        # Test with GTIN
        gtin = "00614141737059"
        print(f"\n1. Looking up by GTIN: {gtin}")
        batch = get_batch_by_id_or_gtin(db, gtin)
        if batch:
            print(f"   ✅ Found: {batch.batch_id}")
            print(f"      Quantity: {batch.quantity_kg} kg")
            print(f"      Status: {batch.status}")
        else:
            print(f"   ❌ Not found")
        
        # Test with batch_id if we found one
        if batch:
            print(f"\n2. Looking up by batch_id: {batch.batch_id}")
            batch2 = get_batch_by_id_or_gtin(db, batch.batch_id)
            if batch2:
                print(f"   ✅ Found: {batch2.batch_id}")
            else:
                print(f"   ❌ Not found")
        
        # Test with invalid identifier
        print(f"\n3. Looking up invalid identifier: INVALID123")
        batch3 = get_batch_by_id_or_gtin(db, "INVALID123")
        if batch3:
            print(f"   ❌ Unexpectedly found: {batch3.batch_id}")
        else:
            print(f"   ✅ Correctly returned None")
            
    finally:
        db.close()


def test_user_roles():
    """Test user role lookup."""
    print("\n=== Testing User Roles ===")
    
    db = SessionLocal()
    try:
        telegram_id = "5753848438"  # Manu's ID
        print(f"\nLooking up user: {telegram_id}")
        user = get_user_by_telegram_id(telegram_id, db_session=db)
        if user:
            print(f"   ✅ Found user")
            print(f"      Username: {user.telegram_username}")
            print(f"      Role: {user.role}")
            print(f"      Approved: {user.is_approved}")
            print(f"      DID: {user.did}")
        else:
            print(f"   ❌ User not found")
    finally:
        db.close()


def test_verify_command_simulation():
    """Simulate /verify command logic."""
    print("\n=== Testing /verify Command Logic ===")
    
    db = SessionLocal()
    try:
        # Test parameters
        telegram_id = "5753848438"
        gtin = "00614141737059"
        verified_quantity = 50.0
        notes = "Quality excellent"
        
        print(f"\nCommand: /verify {gtin} {verified_quantity} {notes}")
        
        # Step 1: Check user authorization
        print("\n1. Checking user authorization...")
        user = get_user_by_telegram_id(telegram_id, db_session=db)
        if not user:
            print("   ❌ User not found")
            return
        
        print(f"   ✅ User found: {user.telegram_username}")
        
        if user.role != 'COOPERATIVE_MANAGER':
            print(f"   ❌ Wrong role: {user.role}")
            return
        
        print(f"   ✅ Role: {user.role}")
        
        if not user.is_approved:
            print("   ❌ Not approved")
            return
        
        print("   ✅ Approved")
        
        # Step 2: Look up batch
        print(f"\n2. Looking up batch by GTIN: {gtin}")
        batch = get_batch_by_id_or_gtin(db, gtin)
        if not batch:
            print("   ❌ Batch not found")
            return
        
        print(f"   ✅ Batch found: {batch.batch_id}")
        print(f"      Current status: {batch.status}")
        print(f"      Quantity: {batch.quantity_kg} kg")
        
        # Step 3: Check if already verified
        if batch.status == 'VERIFIED':
            print("   ⚠️  Already verified")
            if batch.verified_at:
                print(f"      Verified at: {batch.verified_at}")
            return
        
        # Step 4: Format success message
        print("\n3. Formatting success message...")
        diff = verified_quantity - batch.quantity_kg
        diff_text = ""
        if abs(diff) > 0.1:
            diff_sign = "+" if diff > 0 else ""
            diff_text = f"\n   Difference: {diff_sign}{diff:.1f} kg ({diff_sign}{(diff/batch.quantity_kg)*100:.1f}%)"
        
        # Escape Markdown special characters
        safe_batch_id = batch.batch_id.replace('_', '\\_')
        notes_line = f"   Notes: {notes}\n" if notes else ""
        credential_line = "✅ Verification credential issued"
        
        message = (
            f"✅ *Batch Verified*\n\n"
            f"📦 {safe_batch_id}\n"
            f"   GTIN: {batch.gtin}\n"
            f"   Claimed: {batch.quantity_kg} kg\n"
            f"   Verified: {verified_quantity} kg{diff_text}\n"
            f"   Variety: {batch.variety}\n"
            f"   Origin: {batch.origin}\n"
            f"{notes_line}\n"
            f"{credential_line}"
        )
        
        print("   ✅ Message formatted:")
        print("\n" + message)
        
        print("\n✅ ALL CHECKS PASSED - Command would succeed")
        
    finally:
        db.close()


def test_ship_command_simulation():
    """Simulate /ship command logic."""
    print("\n=== Testing /ship Command Logic ===")
    
    db = SessionLocal()
    try:
        gtin = "00614141737059"
        destination = "Addis_Warehouse"
        
        print(f"\nCommand: /ship {gtin} {destination}")
        
        print(f"\n1. Looking up batch by GTIN: {gtin}")
        batch = get_batch_by_id_or_gtin(db, gtin)
        if not batch:
            print("   ❌ Batch not found")
            return
        
        print(f"   ✅ Batch found: {batch.batch_id}")
        print(f"      Can ship to: {destination}")
        print("\n✅ Command would succeed")
        
    finally:
        db.close()


def test_receive_command_simulation():
    """Simulate /receive command logic."""
    print("\n=== Testing /receive Command Logic ===")
    
    db = SessionLocal()
    try:
        gtin = "00614141737059"
        condition = "good"
        
        print(f"\nCommand: /receive {gtin} {condition}")
        
        print(f"\n1. Looking up batch by GTIN: {gtin}")
        batch = get_batch_by_id_or_gtin(db, gtin)
        if not batch:
            print("   ❌ Batch not found")
            return
        
        print(f"   ✅ Batch found: {batch.batch_id}")
        print(f"      Receive with condition: {condition}")
        print("\n✅ Command would succeed")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Telegram Bot Commands Test Suite")
    print("=" * 60)
    
    test_batch_lookup()
    test_user_roles()
    test_verify_command_simulation()
    test_ship_command_simulation()
    test_receive_command_simulation()
    
    print("\n" + "=" * 60)
    print("Test Suite Complete")
    print("=" * 60)
