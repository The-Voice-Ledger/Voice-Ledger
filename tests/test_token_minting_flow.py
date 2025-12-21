#!/usr/bin/env python3
"""
Integration Test: Full Token Minting Flow

Tests the complete flow from farmer batch creation through cooperative 
verification to token minting.

Flow:
1. Farmer creates batch via voice → PENDING_VERIFICATION
2. Commission event created (IPFS + blockchain)
3. ❌ No token minted yet
4. Cooperative verifies batch
5. ✅ Token minted with verified quantity
6. Token ID stored in batch record

Run: python test_token_minting_flow.py
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from database.connection import SessionLocal
from database.crud import create_batch
from database.models import CoffeeBatch, EPCISEvent, UserIdentity, Organization
from voice.epcis.commission_events import create_commission_event
from blockchain.token_manager import mint_batch_token

# Test configuration
# Get wallet address from private key
import os
from web3 import Web3
from eth_account import Account

private_key = os.getenv('PRIVATE_KEY_SEP')
if private_key:
    account = Account.from_key(private_key)
    TEST_COOPERATIVE_WALLET = account.address
else:
    TEST_COOPERATIVE_WALLET = None

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_step(step, text):
    """Print test step"""
    print(f"\n[STEP {step}] {text}")

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")

def cleanup_test_data(db, batch_id):
    """Remove test data"""
    try:
        db.rollback()  # Clear any pending transactions
        batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        if batch:
            db.query(EPCISEvent).filter_by(batch_id=batch.id).delete()
            db.delete(batch)
            db.commit()
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
        db.rollback()

def test_full_flow():
    """Test complete token minting flow"""
    print_header("TOKEN MINTING INTEGRATION TEST")
    
    # Generate unique test batch ID
    batch_id = f"TEST_YEHA_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    test_user_did = "did:test:farmer001"
    
    db = SessionLocal()
    
    try:
        # Clean up any previous test data
        cleanup_test_data(db, batch_id)
        
        # =============================================
        # STEP 1: Farmer creates batch (via voice)
        # =============================================
        print_step(1, "Farmer creates batch via voice command")
        
        # Find or create test user
        user = db.query(UserIdentity).filter_by(telegram_user_id="test_12345").first()
        if not user:
            print_info("Creating test user...")
            from ssi.did.did_key import generate_did_key
            keypair = generate_did_key()
            user = UserIdentity(
                telegram_user_id="test_12345",
                telegram_username="test_farmer",
                did=keypair['did'],
                encrypted_private_key=keypair['private_key'],  # hex format
                public_key=keypair['public_key'],  # hex format
                role='FARMER'
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        test_user_did = user.did  # Use actual DID from database
        
        # Create batch
        from gs1.identifiers import gtin as generate_gtin, gln as generate_gln
        # gtin() signature: gtin(product_code: str, gtin_format: str = "GTIN-14")
        # product_code must be 5 digits for GTIN-14 format
        # Use timestamp seconds to make it unique
        product_code = str(int(datetime.utcnow().timestamp()) % 100000).zfill(5)
        gtin = generate_gtin(product_code, "GTIN-14")  # Returns exactly 14-digit GTIN
        # gln() signature: gln(location_code: str)  
        gln = generate_gln("00001")  # Returns exactly 13-digit GLN
        
        batch_data = {
            "batch_id": batch_id,
            "gtin": gtin,
            "gln": gln,
            "batch_number": "TEST-001",
            "quantity_kg": 150.0,  # Farmer claims 150kg
            "origin": "Yeha",
            "variety": "Arabica",
            "processing_method": "Washed",
            "quality_grade": "A",
            "created_by_user_id": user.id,
            "created_by_did": test_user_did,
            "status": "PENDING_VERIFICATION"
        }
        
        batch = create_batch(db, batch_data)
        print_success(f"Batch created: {batch.batch_id}")
        print_info(f"  Status: {batch.status}")
        print_info(f"  Claimed quantity: {batch.quantity_kg} kg")
        print_info(f"  Token ID: {batch.token_id}")
        
        # =============================================
        # STEP 2: Create commission event
        # =============================================
        print_step(2, "Create commission EPCIS event (IPFS + blockchain)")
        
        event_result = create_commission_event(
            db=db,
            batch_id=batch.batch_id,
            gtin=batch.gtin,
            gln=batch.gln,
            quantity_kg=batch.quantity_kg,
            variety=batch.variety,
            origin=batch.origin,
            farmer_did=test_user_did,
            processing_method=batch.processing_method,
            quality_grade=batch.quality_grade,
            batch_db_id=batch.id,
            submitter_db_id=None  # No FarmerIdentity entry for test user
        )
        
        if event_result:
            print_success("Commission event created")
            print_info(f"  IPFS CID: {event_result['ipfs_cid']}")
            print_info(f"  Blockchain TX: {event_result['blockchain_tx_hash'][:16]}..." if event_result.get('blockchain_tx_hash') else "  Blockchain: pending")
        else:
            print_error("Failed to create commission event")
            return False
        
        # =============================================
        # STEP 3: Verify no token minted yet
        # =============================================
        print_step(3, "Verify NO token minted yet")
        
        db.refresh(batch)
        if batch.token_id is None:
            print_success("Correct! No token minted before verification")
        else:
            print_error(f"Token already minted: {batch.token_id}")
            return False
        
        # =============================================
        # STEP 4: Cooperative verifies batch
        # =============================================
        print_step(4, "Cooperative manager verifies batch")
        
        # Find or create test organization
        org = db.query(Organization).filter_by(type='COOPERATIVE').first()
        if not org:
            print_info("Creating test cooperative...")
            from ssi.did.did_key import generate_did_key
            org_keypair = generate_did_key()
            org = Organization(
                name="Test Cooperative",
                type="COOPERATIVE",
                did=org_keypair['did'],
                encrypted_private_key=org_keypair['private_key'],  # hex format
                public_key=org_keypair['public_key']  # hex format
            )
            db.add(org)
            db.commit()
            db.refresh(org)
        
        # Simulate verification (what happens when cooperative scans QR)
        verified_quantity = 145.0  # Cooperative verifies actual: 145kg (5kg less than claim)
        
        batch.status = 'VERIFIED'
        batch.verified_quantity = verified_quantity
        batch.verified_at = datetime.utcnow()
        batch.verified_by_did = org.did
        batch.verification_used = True
        batch.verification_notes = f"Verified - actual quantity: {verified_quantity} kg"
        batch.verifying_organization_id = org.id
        db.commit()
        
        print_success("Batch verified by cooperative")
        print_info(f"  Verified quantity: {verified_quantity} kg (claimed: {batch.quantity_kg} kg)")
        
        # =============================================
        # STEP 5: Mint token AFTER verification
        # =============================================
        print_step(5, "Mint token to cooperative wallet")
        
        if not TEST_COOPERATIVE_WALLET:
            print_error("WALLET_ADDRESS_SEP not set in .env")
            return False
        
        # Get IPFS CID from commission event
        commission_event = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id == batch.id,
            EPCISEvent.biz_step == 'commissioning'
        ).first()
        
        if not commission_event or not commission_event.ipfs_cid:
            print_error("No commission event IPFS CID found")
            return False
        
        print_info(f"  Minting to: {TEST_COOPERATIVE_WALLET[:16]}...")
        print_info(f"  Using verified quantity: {verified_quantity} kg")
        
        token_id = mint_batch_token(
            recipient=TEST_COOPERATIVE_WALLET,
            quantity_kg=verified_quantity,  # Use VERIFIED quantity
            batch_id=batch.batch_id,
            metadata={
                'variety': batch.variety,
                'origin': batch.origin,
                'processing_method': batch.processing_method,
                'quality_grade': batch.quality_grade,
                'farmer_did': test_user_did,
                'gtin': batch.gtin,
                'gln': batch.gln,
                'verified_by': org.did,
                'verification_date': datetime.utcnow().isoformat()
            },
            ipfs_cid=commission_event.ipfs_cid
        )
        
        if token_id:
            print_success(f"Token minted! Token ID: {token_id}")
            
            # Store token ID
            batch.token_id = token_id
            db.commit()
            print_success("Token ID stored in database")
        else:
            print_error("Token minting failed")
            return False
        
        # =============================================
        # STEP 6: Verify final state
        # =============================================
        print_step(6, "Verify final state")
        
        db.refresh(batch)
        
        checks = [
            ("Status is VERIFIED", batch.status == 'VERIFIED'),
            ("Token ID stored", batch.token_id is not None),
            ("Token ID matches", batch.token_id == token_id),
            ("Verified quantity recorded", batch.verified_quantity == verified_quantity),
            ("Verification timestamp set", batch.verified_at is not None),
            ("Verifier recorded", batch.verified_by_did == org.did)
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print_success(check_name)
            else:
                print_error(check_name)
                all_passed = False
        
        # =============================================
        # SUCCESS
        # =============================================
        if all_passed:
            print_header("✅ ALL TESTS PASSED")
            print("\nFlow Summary:")
            print(f"  1. Farmer claimed: {batch.quantity_kg} kg")
            print(f"  2. Cooperative verified: {verified_quantity} kg")
            print(f"  3. Token minted with: {verified_quantity} kg")
            print(f"  4. Token ID: {token_id}")
            print(f"  5. IPFS CID: {commission_event.ipfs_cid}")
            print(f"\n✅ Only VERIFIED batches get on-chain tokens!")
            return True
        else:
            print_header("❌ SOME TESTS FAILED")
            return False
            
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup (optional - comment out to inspect data)
        print_info("\nCleaning up test data...")
        cleanup_test_data(db, batch_id)
        db.close()

if __name__ == "__main__":
    success = test_full_flow()
    sys.exit(0 if success else 1)
