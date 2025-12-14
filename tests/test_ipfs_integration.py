"""
Test IPFS Integration with Database

Tests the complete flow:
1. Create EPCIS event
2. Pin to IPFS
3. Store in database with IPFS CID
4. Retrieve and verify
"""

import json
import hashlib
from datetime import datetime
from database import get_db, create_event, create_batch, create_farmer, get_event_by_hash
from ipfs import pin_epcis_event, get_from_ipfs

def test_ipfs_integration():
    """Test complete IPFS + database integration."""
    
    print("🧪 Testing IPFS Integration with Database\n")
    
    # Step 1: Create test EPCIS event
    print("1️⃣ Creating test EPCIS event...")
    test_event = {
        "@context": "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld",
        "type": "ObjectEvent",
        "eventTime": datetime.utcnow().isoformat() + "Z",
        "eventTimeZoneOffset": "+00:00",
        "action": "OBSERVE",
        "bizStep": "commissioning",
        "readPoint": {
            "id": "urn:epc:id:sgln:0614141.00001.0"
        },
        "quantityList": [
            {
                "epcClass": "urn:epc:idpat:sgtin:0614141.012345.*",
                "quantity": 50,
                "uom": "KGM"
            }
        ]
    }
    
    # Step 2: Calculate event hash
    print("2️⃣ Calculating event hash...")
    canonical = json.dumps(test_event, sort_keys=True, separators=(',', ':'))
    event_hash = hashlib.sha256(canonical.encode()).hexdigest()
    print(f"   Event hash: {event_hash[:16]}...")
    
    # Step 3: Pin to IPFS
    print("\n3️⃣ Pinning event to IPFS...")
    ipfs_cid = pin_epcis_event(test_event, event_hash)
    
    if not ipfs_cid:
        print("❌ IPFS pinning failed")
        return False
    
    print(f"   ✅ Pinned to IPFS: {ipfs_cid}")
    
    # Step 4: Store in database
    print("\n4️⃣ Storing event in database...")
    with get_db() as db:
        event_data = {
            'event_hash': event_hash,
            'event_type': 'ObjectEvent',
            'canonical_nquads': canonical,
            'event_json': test_event,
            'ipfs_cid': ipfs_cid,
            'event_time': datetime.utcnow(),
            'biz_step': 'commissioning'
        }
        
        db_event = create_event(db, event_data, pin_to_ipfs=False)  # Already pinned
        print(f"   ✅ Stored in database (ID: {db_event.id})")
        print(f"   IPFS CID: {db_event.ipfs_cid}")
    
    # Step 5: Retrieve from IPFS
    print("\n5️⃣ Retrieving from IPFS...")
    retrieved_event = get_from_ipfs(ipfs_cid)
    
    if not retrieved_event:
        print("❌ IPFS retrieval failed")
        return False
    
    print("   ✅ Retrieved from IPFS")
    
    # Step 6: Verify data matches
    print("\n6️⃣ Verifying data integrity...")
    matches = (retrieved_event == test_event)
    
    if matches:
        print("   ✅ Data matches original event")
    else:
        print("   ❌ Data mismatch!")
        return False
    
    # Step 7: Query from database
    print("\n7️⃣ Querying from database...")
    with get_db() as db:
        db_event = get_event_by_hash(db, event_hash)
        if db_event:
            print(f"   ✅ Found in database")
            print(f"   Event hash: {db_event.event_hash[:16]}...")
            print(f"   IPFS CID: {db_event.ipfs_cid}")
            print(f"   Biz step: {db_event.biz_step}")
            # Store CID outside session scope
            stored_cid = db_event.ipfs_cid
        else:
            print("   ❌ Not found in database")
            return False
    
    # Step 8: Retrieve via database CID
    print("\n8️⃣ Retrieving via database IPFS CID...")
    ipfs_data = get_from_ipfs(stored_cid)
    
    if ipfs_data:
        print("   ✅ Retrieved using CID from database")
        print(f"   Event type: {ipfs_data.get('type')}")
        print(f"   Biz step: {ipfs_data.get('bizStep')}")
    else:
        print("   ❌ Failed to retrieve via CID")
        return False
    
    print("\n" + "="*60)
    print("✅ IPFS Integration Test Passed!")
    print("="*60)
    print("\n📊 Summary:")
    print(f"   • Event hashed: {event_hash[:16]}...")
    print(f"   • IPFS CID: {ipfs_cid}")
    print(f"   • Gateway URL: https://gateway.pinata.cloud/ipfs/{ipfs_cid}")
    
    return True


if __name__ == "__main__":
    success = test_ipfs_integration()
    exit(0 if success else 1)
