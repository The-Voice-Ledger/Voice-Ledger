#!/usr/bin/env python3
"""
Integration Test: Batch Commission with EPCIS Event

Tests the complete flow of creating a batch with automatic
commission EPCIS event creation, IPFS pinning, and blockchain anchoring.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import SessionLocal, CoffeeBatch, EPCISEvent, FarmerIdentity
from voice.command_integration import handle_record_commission
from datetime import datetime


def test_batch_commission_with_event():
    """Test creating a batch triggers commission event"""
    print("\n" + "=" * 70)
    print("  INTEGRATION TEST: Batch Commission with EPCIS Event")
    print("=" * 70 + "\n")
    
    db = SessionLocal()
    
    try:
        # Get or create a test farmer
        farmer = db.query(FarmerIdentity).first()
        if not farmer:
            print("❌ No farmer found. Please create a farmer first.")
            return False
        
        print(f"✓ Using farmer: {farmer.name} (DID: {farmer.did[:20]}...)\n")
        
        # Prepare test entities (simulating voice command extraction)
        entities = {
            'quantity': 50,  # bags
            'unit': 'bags',
            'product': 'Arabica',
            'origin': 'Yirgacheffe'
        }
        
        print("Creating batch with entities:")
        print(f"  Quantity: {entities['quantity']} {entities['unit']}")
        print(f"  Product: {entities['product']}")
        print(f"  Origin: {entities['origin']}\n")
        
        # Call the command handler
        message, result = handle_record_commission(
            db=db,
            entities=entities,
            user_id=farmer.id,
            user_did=farmer.did
        )
        
        print(f"✅ {message}\n")
        print("📦 Batch Details:")
        print(f"  Batch ID: {result['batch_id']}")
        print(f"  GTIN: {result['gtin']}")
        print(f"  GLN: {result.get('gln', 'N/A')}")
        print(f"  Quantity: {result['quantity_kg']} kg")
        print(f"  Status: {result['status']}")
        
        # Check if EPCIS event was created
        if result.get('epcis_event'):
            print(f"\n🗄️  EPCIS Commission Event:")
            event_info = result['epcis_event']
            print(f"  Event Hash: {event_info.get('event_hash', 'N/A')}")
            print(f"  IPFS CID: {event_info.get('ipfs_cid', 'N/A')}")
            print(f"  Blockchain TX: {event_info.get('blockchain_tx', 'N/A')}")
            print(f"  Confirmed: {'✅' if event_info.get('blockchain_confirmed') else '⏳'}")
            
            # Verify in database
            batch = db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id == result['batch_id']
            ).first()
            
            if batch:
                commission_events = db.query(EPCISEvent).filter(
                    EPCISEvent.batch_id == batch.id,
                    EPCISEvent.biz_step == 'commissioning'
                ).all()
                
                print(f"\n✓ Found {len(commission_events)} commission event(s) in database")
                
                if commission_events:
                    event = commission_events[0]
                    print(f"\n📋 Event Details:")
                    print(f"  Type: {event.event_type}")
                    print(f"  BizStep: {event.biz_step}")
                    print(f"  Event Time: {event.event_time}")
                    print(f"  BizLocation: {event.biz_location}")
                    
                    # Show GS1 identifiers from event JSON
                    event_json = event.event_json
                    if 'epcList' in event_json and event_json['epcList']:
                        print(f"\n🏷️  GS1 Identifiers:")
                        print(f"  SGTIN: {event_json['epcList'][0]}")
                        if 'quantityList' in event_json and event_json['quantityList']:
                            print(f"  LGTIN: {event_json['quantityList'][0]['epcClass']}")
                        if 'readPoint' in event_json:
                            print(f"  SGLN: {event_json['readPoint']['id']}")
                    
                    print("\n✅ INTEGRATION TEST PASSED")
                    return True
            else:
                print("\n⚠️  Batch not found in database")
                return False
        else:
            print("\n❌ No EPCIS event created")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_batch_commission_with_event()
    sys.exit(0 if success else 1)
