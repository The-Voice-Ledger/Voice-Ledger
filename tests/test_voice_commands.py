"""
Test voice command integration for aggregation and split operations.
Tests Section 1.2 implementation.
"""

from database.connection import SessionLocal
from voice.command_integration import execute_voice_command
from voice.epcis.commission_events import create_commission_event
from database.models import CoffeeBatch
import sys

def test_pack_batches():
    """Test packing batches into container via voice command."""
    print("\n" + "="*60)
    print("TEST 1: Pack Batches (Aggregation)")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Create 3 test batches using record_commission command
        batch_ids = []
        for i in range(3):
            entities = {
                "quantity": 500,
                "origin": f"Test-Origin-{i}",
                "product": "Arabica",
                "unit": "kg"
            }
            
            message, result = execute_voice_command(
                db=db,
                intent="record_commission",
                entities=entities,
                user_id=None,
                user_did="did:key:test_farmer"
            )
            if result:
                batch_ids.append(result["batch_id"])
        
        print(f"✓ Created {len(batch_ids)} test batches")
        for idx, bid in enumerate(batch_ids, 1):
            print(f"  {idx}. {bid}")
        
        # Voice command: Pack batches
        print("\nVoice Command: 'Pack batches into container PALLET-001'")
        entities = {
            "batch_ids": batch_ids,
            "container_id": "PALLET-001",
            "container_type": "pallet"
        }
        
        message, result = execute_voice_command(
            db=db,
            intent="pack_batches",
            entities=entities,
            user_id=None,
            user_did="did:key:test_user"
        )
        
        print(f"\n✅ {message}")
        print(f"Container: {result['container_id']}")
        print(f"Batches packed: {len(result['batch_ids'])}")
        print(f"IPFS CID: {result['ipfs_cid']}")
        print(f"Blockchain TX: {result['blockchain_tx'][:20]}...")
        
        return result['container_id'], batch_ids
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, []
    finally:
        db.close()


def test_unpack_batches(container_id):
    """Test unpacking container via voice command."""
    print("\n" + "="*60)
    print("TEST 2: Unpack Container (Disaggregation)")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Voice command: Unpack container
        print(f"\nVoice Command: 'Unpack container {container_id}'")
        entities = {
            "container_id": container_id
        }
        
        message, result = execute_voice_command(
            db=db,
            intent="unpack_batches",
            entities=entities,
            user_id=None,
            user_did="did:key:test_user"
        )
        
        print(f"\n✅ {message}")
        print(f"Container: {result['container_id']}")
        print(f"Batches unpacked: {len(result['batch_ids'])}")
        print(f"IPFS CID: {result['ipfs_cid']}")
        print(f"Blockchain TX: {result['blockchain_tx'][:20]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_split_batch():
    """Test splitting batch via voice command."""
    print("\n" + "="*60)
    print("TEST 3: Split Batch (Transformation)")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Create parent batch (10,000kg) using record_commission
        entities = {
            "quantity": 10000,
            "origin": "Sidama",
            "product": "Arabica-Premium",
            "unit": "kg"
        }
        
        message, result = execute_voice_command(
            db=db,
            intent="record_commission",
            entities=entities,
            user_id=None,
            user_did="did:key:test_farmer_split"
        )
        
        parent_batch_id = result["batch_id"]
        print(f"✓ Created parent batch: {parent_batch_id} (10,000kg)")
        
        # Voice command: Split batch
        print("\nVoice Command: 'Split batch into 6000kg for EU and 4000kg for US'")
        entities = {
            "batch_id": parent_batch_id,
            "splits": [
                {"quantity_kg": 6000.0, "destination": "EU"},
                {"quantity_kg": 4000.0, "destination": "US"}
            ]
        }
        
        message, result = execute_voice_command(
            db=db,
            intent="split_batch",
            entities=entities,
            user_id=None,
            user_did="did:key:test_user"
        )
        
        print(f"\n✅ {message}")
        print(f"Parent batch: {result['parent_batch_id']}")
        print(f"Child batches created:")
        for idx, child_id in enumerate(result['child_batch_ids'], 1):
            # Get child batch details
            child = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == child_id).first()
            print(f"  {idx}. {child_id} ({child.quantity_kg}kg)")
        
        print(f"\nTransformation ID: {result['transformation_id']}")
        print(f"IPFS CID: {result['ipfs_cid']}")
        print(f"Blockchain TX: {result['blockchain_tx'][:20]}...")
        
        # Verify parent status
        parent = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == parent_batch_id).first()
        print(f"Parent status: {parent.status}")
        
        # Verify mass balance
        children = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id.in_(result['child_batch_ids'])).all()
        total_child_mass = sum(c.quantity_kg for c in children)
        print(f"\nMass balance check:")
        print(f"  Parent: 10000.0 kg")
        print(f"  Children total: {total_child_mass} kg")
        print(f"  Balance: {'✅ OK' if abs(10000.0 - total_child_mass) < 0.1 else '❌ FAILED'}")
        
        # Verify farmer inheritance
        print(f"\nFarmer inheritance check:")
        for idx, child in enumerate(children, 1):
            print(f"  Child {idx}: farmer_id={child.farmer_id} (inherited: {'✅' if child.farmer_id == parent.farmer_id else '❌'})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Run all voice command tests."""
    print("\n" + "#"*60)
    print("# Voice Command Integration Test Suite")
    print("# Section 1.2: NLU Parser & Voice Commands")
    print("#"*60)
    
    # Test 1: Pack batches
    container_id, batch_ids = test_pack_batches()
    
    # Test 2: Unpack batches (if pack succeeded)
    if container_id:
        test_unpack_batches(container_id)
    
    # Test 3: Split batch
    test_split_batch()
    
    print("\n" + "#"*60)
    print("# All voice command tests completed!")
    print("#"*60 + "\n")


if __name__ == "__main__":
    main()
