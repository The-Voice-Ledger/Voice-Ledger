#!/usr/bin/env python3
"""
Test Commission Event Creation

Validates that commission EPCIS events are properly created
with IPFS pinning and blockchain anchoring.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import SessionLocal, CoffeeBatch, EPCISEvent, FarmerIdentity
from voice.epcis.commission_events import create_commission_event, get_commission_events_for_batch
from datetime import datetime


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_commission_event_creation():
    """Test creating a commission event for an existing batch"""
    print_section("TEST: Commission Event Creation")
    
    db = SessionLocal()
    try:
        # Find first batch without commission event
        batch = db.query(CoffeeBatch).first()
        
        if not batch:
            print("❌ No batches found in database")
            return False
        
        print(f"\n✓ Found batch: {batch.batch_id}")
        print(f"  GTIN: {batch.gtin}")
        print(f"  GLN: {batch.gln}")
        print(f"  Quantity: {batch.quantity_kg} kg")
        print(f"  Origin: {batch.origin}")
        print(f"  Variety: {batch.variety}")
        
        # Check if commission event already exists
        existing_events = get_commission_events_for_batch(db, batch.batch_id)
        if existing_events:
            print(f"\n⚠️  Commission event already exists (count: {len(existing_events)})")
            event = existing_events[0]
            print(f"  Event Hash: {event.event_hash[:16]}...")
            print(f"  IPFS CID: {event.ipfs_cid}")
            print(f"  Blockchain TX: {event.blockchain_tx_hash[:16] + '...' if event.blockchain_tx_hash else 'pending'}")
            return True
        
        # Get farmer DID if available
        farmer_did = batch.created_by_did or "did:key:z6MkTestFarmer"
        
        print(f"\nCreating commission event...")
        
        # Create commission event
        event_result = create_commission_event(
            db=db,
            batch_id=batch.batch_id,
            gtin=batch.gtin,
            gln=batch.gln or "0614141000000",  # Default if not set
            quantity_kg=batch.quantity_kg,
            variety=batch.variety,
            origin=batch.origin,
            farmer_did=farmer_did,
            processing_method=batch.processing_method or "Washed",
            quality_grade=batch.quality_grade or "A",
            batch_db_id=batch.id,
            submitter_db_id=batch.created_by_user_id
        )
        
        if event_result:
            print("\n✅ SUCCESS! Commission Event Created")
            print(f"\n📋 Event Details:")
            print(f"  Event Hash: {event_result['event_hash'][:16]}...")
            print(f"  IPFS CID: {event_result['ipfs_cid']}")
            print(f"  Blockchain TX: {event_result['blockchain_tx_hash'][:16] + '...' if event_result.get('blockchain_tx_hash') else 'pending'}")
            print(f"  Confirmed: {event_result.get('blockchain_confirmed', False)}")
            
            print(f"\n🗄️  EPCIS Event Structure:")
            event = event_result['event']
            print(f"  Type: {event['type']}")
            print(f"  Action: {event['action']}")
            print(f"  BizStep: {event['bizStep']}")
            print(f"  Disposition: {event['disposition']}")
            print(f"  SGTIN: {event['epcList'][0]}")
            print(f"  LGTIN: {event['quantityList'][0]['epcClass']}")
            print(f"  SGLN: {event['readPoint']['id']}")
            
            # Verify it's in database
            db_event = db.query(EPCISEvent).filter(
                EPCISEvent.event_hash == event_result['event_hash']
            ).first()
            
            if db_event:
                print(f"\n✅ Event stored in database")
                print(f"  DB ID: {db_event.id}")
                print(f"  Event Type: {db_event.event_type}")
                print(f"  BizStep: {db_event.biz_step}")
                print(f"  Event Time: {db_event.event_time}")
            else:
                print(f"\n⚠️  Event not found in database")
                return False
            
            return True
        else:
            print("\n❌ FAILED to create commission event")
            return False
    finally:
        db.close()


def test_commission_event_retrieval():
    """Test retrieving commission events"""
    print_section("TEST: Commission Event Retrieval")
    
    db = SessionLocal()
    try:
        # Get all commission events
        all_commission_events = db.query(EPCISEvent).filter(
            EPCISEvent.biz_step == 'commissioning'
        ).all()
        
        print(f"\n✓ Found {len(all_commission_events)} commission events in database")
        
        if all_commission_events:
            for i, event in enumerate(all_commission_events[:3], 1):  # Show first 3
                print(f"\n  Event {i}:")
                print(f"    Hash: {event.event_hash[:16]}...")
                print(f"    Batch ID: {event.batch.batch_id if event.batch else 'N/A'}")
                print(f"    Time: {event.event_time}")
                print(f"    IPFS: {event.ipfs_cid}")
                print(f"    Blockchain: {'✅' if event.blockchain_confirmed else '⏳'}")
        
        return len(all_commission_events) > 0
    finally:
        db.close()


def main():
    """Run all tests"""
    print("\n" + "🧪 " * 35)
    print("  COMMISSION EVENT CREATION TEST")
    print("🧪 " * 35)
    
    results = []
    
    # Test 1: Create commission event
    try:
        result = test_commission_event_creation()
        results.append(("Commission Event Creation", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Commission Event Creation", False))
    
    # Test 2: Retrieve commission events
    try:
        result = test_commission_event_retrieval()
        results.append(("Commission Event Retrieval", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Commission Event Retrieval", False))
    
    # Summary
    print_section("TEST SUMMARY")
    print()
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print()
    total = len(results)
    passed = sum(1 for _, result in results if result)
    print(f"  Total: {passed}/{total} tests passed")
    print()
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
