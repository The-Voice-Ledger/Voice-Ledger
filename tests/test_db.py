"""
Test script to verify Neon database integration
"""

from database.connection import get_db
from database.crud import (
    create_farmer,
    create_batch,
    create_event,
    get_batch_by_gtin,
    get_farmer_by_did,
    get_batch_events
)
from datetime import datetime

def test_database():
    """Test database operations."""
    
    print("Testing Neon database integration...")
    
    with get_db() as db:
        # 1. Create a test farmer
        print("\n1. Creating test farmer...")
        farmer = create_farmer(db, {
            "farmer_id": "F001",
            "did": "did:key:test123",
            "encrypted_private_key": "encrypted_key_data_here",
            "public_key": "public_key_here",
            "name": "Abebe Kebede",
            "phone_number": "+251911234567",
            "location": "Yirgacheffe, Ethiopia",
            "gln": "9520123456789"
        })
        print(f"   ✓ Created farmer: {farmer.name} (ID: {farmer.id})")
        
        # 2. Create a test batch
        print("\n2. Creating test coffee batch...")
        batch = create_batch(db, {
            "batch_id": "YRG-2025-001",
            "gtin": "09520000000001",
            "batch_number": "001",
            "quantity_kg": 500.0,
            "origin": "Yirgacheffe",
            "variety": "Arabica Heirloom",
            "harvest_date": datetime(2025, 12, 1),
            "processing_method": "Washed",
            "quality_grade": "Grade 1",
            "farmer_id": farmer.id
        })
        print(f"   ✓ Created batch: {batch.batch_id} ({batch.quantity_kg} kg)")
        
        # 3. Create a test event
        print("\n3. Creating test EPCIS event...")
        event = create_event(db, {
            "event_hash": "abc123def456",
            "event_type": "ObjectEvent",
            "canonical_nquads": "canonical N-Quads here",
            "event_json": {
                "type": "ObjectEvent",
                "action": "OBSERVE",
                "bizStep": "harvesting",
                "eventTime": "2025-12-01T08:00:00Z"
            },
            "event_time": datetime(2025, 12, 1, 8, 0, 0),
            "biz_step": "harvesting",
            "biz_location": "9520123456789",
            "batch_id": batch.id,
            "submitter_id": farmer.id
        })
        print(f"   ✓ Created event: {event.event_hash}")
        
        # 4. Query batch by GTIN
        print("\n4. Querying batch by GTIN...")
        found_batch = get_batch_by_gtin(db, "09520000000001")
        print(f"   ✓ Found batch: {found_batch.batch_id} (Farmer: {found_batch.farmer.name})")
        
        # 5. Query farmer by DID
        print("\n5. Querying farmer by DID...")
        found_farmer = get_farmer_by_did(db, "did:key:test123")
        print(f"   ✓ Found farmer: {found_farmer.name} ({len(found_farmer.batches)} batches)")
        
        # 6. Get all events for batch
        print("\n6. Getting events for batch...")
        events = get_batch_events(db, batch.id)
        print(f"   ✓ Found {len(events)} events for batch {batch.batch_id}")
        
        print("\n" + "="*50)
        print("✓ All database tests passed!")
        print("="*50)
        print(f"\nDatabase URL: {db.bind.url}")
        print("Tables created:")
        print("  - farmer_identities")
        print("  - coffee_batches")
        print("  - epcis_events")
        print("  - verifiable_credentials")
        print("  - offline_queue")

if __name__ == "__main__":
    test_database()
