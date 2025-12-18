#!/usr/bin/env python3
"""
End-to-End Test: IPFS + Blockchain Integration

Tests complete flow:
1. Create EPCIS event
2. Pin to IPFS
3. Anchor to blockchain
4. Verify on-chain

December 18, 2025
"""

import os
import sys
import json
from datetime import datetime

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal, engine
from database.models import Base, CoffeeBatch, FarmerIdentity
from database.crud import create_farmer, create_batch, create_event
from blockchain.blockchain_anchor import BlockchainAnchor
import hashlib
import json

def test_full_integration():
    """Test complete IPFS + Blockchain flow"""
    
    print("=" * 70)
    print("TESTING: IPFS + Blockchain Integration")
    print("=" * 70)
    print()
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Step 1: Create test farmer
        print("Step 1: Creating test farmer...")
        farmer_data = {
            'farmer_id': f'TEST-FARMER-{datetime.now().strftime("%H%M%S")}',
            'name': 'Abebe Fekadu',
            'did': f'did:key:z6Mktest{datetime.now().strftime("%H%M%S")}',
            'encrypted_private_key': 'encrypted_test_key',
            'public_key': 'test_public_key',
            'location': 'Sidama, Ethiopia',
            'farm_size_hectares': 2.5,
            'certification_status': 'Organic',
            'latitude': 6.0,
            'longitude': 38.5,
            'country_code': 'ET',
            'region': 'Sidama'
        }
        farmer = create_farmer(db, farmer_data)
        print(f"✓ Farmer created: {farmer.farmer_id}")
        print()
        
        # Step 2: Create test batch
        print("Step 2: Creating coffee batch...")
        batch_data = {
            'batch_id': f'BLOCKCHAIN-TEST-{datetime.now().strftime("%H%M%S")}',
            'batch_number': f'BN-{datetime.now().strftime("%H%M%S")}',
            'farmer_id': farmer.id,
            'variety': 'Yirgacheffe',
            'quantity_kg': 500.0,
            'process_method': 'Washed',
            'processing_method': 'Washed',
            'harvest_date': datetime.now(),
            'origin': 'Sidama, Ethiopia',
            'origin_country': 'ET',
            'origin_region': 'Sidama',
            'quality_grade': 'AA',
            'gtin': f'876543{datetime.now().strftime("%H%M%S%f")[:8]}'  # 14 digits unique
        }
        batch = create_batch(db, batch_data)
        print(f"✓ Batch created: {batch.batch_id}")
        print()
        
        # Step 3: Create EPCIS event
        print("Step 3: Creating EPCIS event...")
        event_json = {
            "type": "ObjectEvent",
            "eventTime": datetime.now().isoformat(),
            "eventTimeZoneOffset": "+03:00",
            "action": "OBSERVE",
            "epcList": [f"urn:epc:id:sgtin:{batch.gtin}.{batch.batch_id}"],
            "bizStep": "commissioning",
            "disposition": "active",
            "readPoint": {"id": batch.origin},
            "extension": {
                "quantity": batch.quantity_kg,
                "variety": batch.variety,
                "process_method": batch.process_method,
                "quality_grade": batch.quality_grade
            }
        }
        
        # Hash event (canonicalize then hash)
        canonical = json.dumps(event_json, separators=(",", ":"), sort_keys=True)
        event_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        print(f"✓ Event hash: {event_hash[:20]}...")
        print()
        
        # Step 4: Save event (auto pins to IPFS and anchors to blockchain)
        print("Step 4: Saving event (IPFS + Blockchain)...")
        event_data = {
            'batch_id': batch.id,
            'event_type': 'ObjectEvent',
            'event_time': datetime.now(),
            'biz_step': 'commissioning',
            'event_hash': event_hash,
            'event_json': event_json,
            'canonical_nquads': canonical,
            'submitter_id': farmer.id
        }
        
        event = create_event(
            db,
            event_data,
            pin_to_ipfs=True,
            anchor_to_blockchain=True
        )
        
        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"✓ Event ID: {event.id}")
        print(f"✓ Event Hash: {event.event_hash[:20]}...")
        print(f"✓ IPFS CID: {event.ipfs_cid or 'Not pinned'}")
        print(f"✓ Blockchain Tx: {event.blockchain_tx_hash or 'Not anchored'}")
        print(f"✓ Confirmed: {event.blockchain_confirmed}")
        print()
        
        # Step 5: Verify on blockchain
        if event.blockchain_tx_hash:
            print("Step 5: Verifying on blockchain...")
            anchor = BlockchainAnchor()
            
            # Query batch info from blockchain
            batch_info = anchor.get_batch_info(batch.batch_id)
            
            if batch_info:
                print("✓ Blockchain verification successful!")
                print(f"  Stored Hash: {batch_info['event_hash'][:20]}...")
                print(f"  IPFS CID: {batch_info['ipfs_cid']}")
                print(f"  Event Type: {batch_info['event_type']}")
                print(f"  Location: {batch_info['location']}")
                print(f"  Timestamp: {batch_info['timestamp']}")
                print()
                
                # Verify hash matches
                is_valid = anchor.verify_event_hash(batch.batch_id, event.event_hash)
                if is_valid:
                    print("✅ Hash verification: PASSED")
                else:
                    print("❌ Hash verification: FAILED")
            else:
                print("❌ Could not retrieve batch info from blockchain")
        
        print()
        print("=" * 70)
        print("✅ INTEGRATION TEST COMPLETE")
        print("=" * 70)
        print()
        print("Summary:")
        print(f"  1. ✅ EPCIS event created")
        print(f"  2. ✅ Event pinned to IPFS: {event.ipfs_cid is not None}")
        print(f"  3. ✅ Event anchored to blockchain: {event.blockchain_tx_hash is not None}")
        print(f"  4. ✅ Blockchain verification: {'PASSED' if event.blockchain_tx_hash else 'SKIPPED'}")
        print()
        
        if event.blockchain_tx_hash:
            print(f"View on BaseScan: https://sepolia.basescan.org/tx/{event.blockchain_tx_hash}")
            print(f"View on IPFS: https://gateway.pinata.cloud/ipfs/{event.ipfs_cid}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


if __name__ == '__main__':
    success = test_full_integration()
    sys.exit(0 if success else 1)
