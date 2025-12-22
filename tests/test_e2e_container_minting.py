#!/usr/bin/env python3
"""
End-to-End Test: Container Token Minting (Phase 2)

Tests the complete flow:
1. Create test batches with mock token IDs
2. Pack batches into container
3. Verify container token minted on blockchain
4. Verify child tokens burned
5. Verify database records
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from database.models import CoffeeBatch, UserIdentity, AggregationRelationship, FarmerIdentity
from voice.command_integration import handle_pack_batches
from blockchain.token_manager import get_token_manager, mint_batch_token

def setup_test_data():
    """Create test batches using existing user"""
    print("🔧 Setting up test data...")
    
    with get_db() as db:
        # Use existing real user (Manu_Acho)
        user = db.query(UserIdentity).filter_by(telegram_user_id="5753848438").first()
        if not user:
            print("  ❌ User not found! Please create user first via Telegram")
            sys.exit(1)
        
        user_id = user.id
        user_did = user.did
        user_name = user.telegram_username
        
        print(f"  ✅ Using user: {user_name} (ID: {user_id})")
        
        # Create test farmer with GPS coordinates (for EUDR compliance)
        farmer = db.query(FarmerIdentity).filter_by(name="Test Farmer E2E").first()
        if not farmer:
            farmer = FarmerIdentity(
                farmer_id="FARMER-E2E-001",
                did=f"did:key:test-farmer-e2e",
                encrypted_private_key="test_encrypted_key",
                public_key="test_public_key",
                name="Test Farmer E2E",
                phone_number="+251912345678",
                location="Addis Ababa",
                latitude=9.0320,  # Addis Ababa coordinates
                longitude=38.7469,
                region="Addis Ababa",
                country_code="ET",
                farm_size_hectares=2.5,
                created_at=datetime.utcnow()
            )
            db.add(farmer)
            db.commit()
            db.refresh(farmer)
            print(f"  ✅ Created test farmer with GPS: {farmer.name}")
        else:
            print(f"  ✅ Using existing farmer: {farmer.name}")
        
        farmer_id = farmer.id
        
        # Create 3 test batches
        batches = []
        batch_ids = ["TEST-E2E-001", "TEST-E2E-002", "TEST-E2E-003"]
        quantities = [50.0, 60.0, 40.0]
        
        for idx, (batch_id, quantity) in enumerate(zip(batch_ids, quantities)):
            # Check if batch exists
            batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                batch = CoffeeBatch(
                    batch_id=batch_id,
                    batch_number=idx + 1,  # Required field
                    gtin=f"006141418522{idx+51}",
                    quantity_kg=quantity,
                    variety="Yirgacheffe",
                    origin_region="Addis_Ababa",
                    harvest_date=datetime.utcnow(),
                    created_by_user_id=user_id,
                    created_by_did=user_did,
                    farmer_id=farmer_id,  # Link to farmer for EUDR compliance
                    status='VERIFIED',
                    verified_quantity=quantity,
                    created_at=datetime.utcnow()
                )
                db.add(batch)
                db.commit()
                db.refresh(batch)
                print(f"  ✅ Created batch: {batch_id} ({quantity} kg)")
            else:
                # Update existing batch with farmer link
                if not batch.farmer_id:
                    batch.farmer_id = farmer_id
                    db.commit()
                print(f"  ✅ Using existing batch: {batch_id}")
            
            batches.append(batch)
        
        # Return user IDs and batch database IDs
        return user_id, user_did, [b.id for b in batches]

def mint_test_tokens(user_id, batch_db_ids):
    """Mint tokens for test batches"""
    print("\n🪙 Minting batch tokens on blockchain...")
    
    manager = get_token_manager()
    cooperative_wallet = manager.account.address
    
    print(f"  📍 Cooperative wallet: {cooperative_wallet}")
    
    minted_tokens = []
    
    with get_db() as db:
        for batch_db_id in batch_db_ids:
            batch = db.query(CoffeeBatch).filter_by(id=batch_db_id).first()
            if not batch:
                print(f"  ❌ Batch ID {batch_db_id} not found")
                continue
            
            if batch.token_id:
                print(f"  ✅ Batch {batch.batch_id} already has token ID: {batch.token_id}")
                minted_tokens.append((batch.batch_id, batch.token_id))
                continue
            
            # Mint token
            metadata = {
                "batch_id": batch.batch_id,
                "variety": batch.variety,
                "origin": batch.origin_region,
                "quantity_kg": batch.quantity_kg
            }
            
            token_id = mint_batch_token(
                recipient=cooperative_wallet,
                quantity_kg=batch.quantity_kg,
                batch_id=batch.batch_id,
                metadata=metadata,
                ipfs_cid="QmTest123"
            )
            
            if token_id:
                # Update database
                batch.token_id = token_id
                db.commit()
                minted_tokens.append((batch.batch_id, token_id))
                print(f"  ✅ Minted token for {batch.batch_id}: Token ID {token_id}")
            else:
                print(f"  ❌ Failed to mint token for {batch.batch_id}")
                return False, []
    
    return True, minted_tokens

def test_pack_command(user_id, user_did, batch_db_ids):
    """Test /pack command with container minting"""
    print("\n📦 Testing /pack command...")
    
    # Get batch_id strings from database
    with get_db() as db:
        batches = [db.query(CoffeeBatch).filter_by(id=bid).first() for bid in batch_db_ids]
        batch_id_strings = [b.batch_id for b in batches if b]
        
        # Clear any existing aggregation relationships for these batches
        from database.models import AggregationRelationship
        for batch_id in batch_id_strings:
            existing = db.query(AggregationRelationship).filter_by(
                child_identifier=batch_id,
                is_active=True
            ).all()
            for rel in existing:
                rel.is_active = False
            if existing:
                db.commit()
                print(f"  🧹 Cleared {len(existing)} existing aggregation(s) for {batch_id}")
    
    # Use valid 18-digit SSCC format with timestamp to ensure uniqueness
    import time
    timestamp = str(int(time.time()))[-9:]  # Last 9 digits of timestamp
    container_id = f"123456789{timestamp}"  # 18 digits total
    
    print(f"  📦 Container ID: {container_id}")
    
    # Prepare entities as command_integration expects
    entities = {
        "batch_ids": batch_id_strings,
        "container_id": container_id,
        "container_type": "pallet"
    }
    
    with get_db() as db:
        try:
            message, result = handle_pack_batches(
                db=db,
                entities=entities,
                user_id=user_id,
                user_did=user_did
            )
            
            print(f"\n  📋 Result: {message}")
            print(f"  - Container ID: {result.get('container_id')}")
            print(f"  - Batch IDs: {', '.join(batch_id_strings)}")
            print(f"  - IPFS CID: {result.get('ipfs_cid')}")
            print(f"  - Container Token ID: {result.get('container_token_id', 'NOT MINTED')}")
            
            return result.get('container_token_id'), result.get('container_id')
            
        except Exception as e:
            print(f"  ❌ Pack command failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None

def verify_blockchain_state(container_token_id, child_token_ids):
    """Verify container token and burned children on blockchain"""
    print("\n🔍 Verifying blockchain state...")
    
    manager = get_token_manager()
    cooperative_wallet = manager.account.address
    
    # Check container token exists and get child token IDs
    try:
        # Query if token is a container
        is_container = manager.contract.functions.isContainer(container_token_id).call()
        
        if not is_container:
            print(f"  ❌ Token {container_token_id} is not a container")
            return False
        
        print(f"\n  ✅ Container Token ID {container_token_id}:")
        print(f"     - Is Container: True")
        
        # Get child token IDs from blockchain
        child_token_ids_onchain = manager.contract.functions.getChildTokenIds(container_token_id).call()
        print(f"     - Child Tokens: {child_token_ids_onchain}")
        
        # Verify balance
        balance = manager.contract.functions.balanceOf(cooperative_wallet, container_token_id).call()
        print(f"     - Balance: {balance}")
        
        if balance == 0:
            print(f"  ❌ Container token has 0 balance")
            return False
            
    except Exception as e:
        print(f"  ❌ Failed to query container token: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check child tokens are burned
    print("\n  🔥 Verifying child tokens burned:")
    all_burned = True
    for token_id in child_token_ids:
        balance = manager.get_batch_balance(cooperative_wallet, token_id)
        if balance == 0:
            print(f"     ✅ Token {token_id}: Burned (balance = 0)")
        else:
            print(f"     ❌ Token {token_id}: NOT burned (balance = {balance})")
            all_burned = False
    
    return all_burned

def verify_database_state(container_id, container_token_id):
    """Verify database records"""
    print("\n💾 Verifying database state...")
    
    with get_db() as db:
        agg = db.query(AggregationRelationship).filter_by(
            parent_sscc=container_id
        ).first()
        
        if not agg:
            print(f"  ❌ No aggregation record found for {container_id}")
            return False
        
        print(f"\n  ✅ Aggregation record found:")
        print(f"     - Parent SSCC: {agg.parent_sscc}")
        print(f"     - Container Token ID: {agg.container_token_id}")
        print(f"     - Aggregated At: {agg.aggregated_at}")
        print(f"     - Is Active: {agg.is_active}")
        
        if agg.container_token_id != container_token_id:
            print(f"  ❌ Token ID mismatch: DB={agg.container_token_id}, Expected={container_token_id}")
            return False
        
        return True

def main():
    """Run end-to-end test"""
    print("="*60)
    print("Phase 2: Container Token Minting - End-to-End Test")
    print("="*60)
    
    try:
        # Step 1: Setup
        user_id, user_did, batch_db_ids = setup_test_data()
        
        # Step 2: Mint batch tokens
        success, minted_tokens = mint_test_tokens(user_id, batch_db_ids)
        if not success:
            print("\n❌ Token minting failed, aborting test")
            return False
        
        child_token_ids = [token_id for _, token_id in minted_tokens]
        print(f"\n  📊 Child tokens: {child_token_ids}")
        
        # Step 3: Pack into container
        container_token_id, container_id = test_pack_command(user_id, user_did, batch_db_ids)
        if not container_token_id:
            print("\n❌ Container minting failed, aborting test")
            return False
        
        # Step 4: Verify blockchain
        if not verify_blockchain_state(container_token_id, child_token_ids):
            print("\n❌ Blockchain verification failed")
            return False
        
        # Step 5: Verify database
        if not verify_database_state(container_id, container_token_id):
            print("\n❌ Database verification failed")
            return False
        
        # Success!
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)
        print("\nPhase 2 Container Token Minting: FULLY OPERATIONAL ✨")
        print(f"\nView container on Basescan:")
        print(f"https://sepolia.basescan.org/token/0x2ff41d578a945036743d83972d4ab85f155a96fe?a={container_token_id}")
        print("")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
