"""
Test Aggregated DPP Generation

Tests multi-batch DPP generation for containers with multiple source batches.
Validates farmer contribution calculations, blockchain proofs, and EUDR compliance.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import SessionLocal, CoffeeBatch, FarmerIdentity, AggregationRelationship, EPCISEvent
from dpp.dpp_builder import build_aggregated_dpp, build_recursive_dpp
from datetime import datetime, timezone
import json
import base64
import os


def cleanup_test_data(db):
    """
    Systematically clean up test data in correct order to avoid FK violations.
    Order: aggregations → events → batches → farmers
    """
    print("🧹 Cleaning up any existing test data...")
    
    # 1. Delete aggregation relationships (no FK dependencies)
    deleted_agg = db.query(AggregationRelationship).filter(
        (AggregationRelationship.parent_sscc.like('%TEST%')) | 
        (AggregationRelationship.parent_sscc.like('%RECURSIVE%')) |
        (AggregationRelationship.parent_sscc.like('306141411%')) |  # Test SSCCs
        (AggregationRelationship.child_identifier.like('TEST%')) |
        (AggregationRelationship.child_identifier.like('RECURSIVE%'))
    ).delete(synchronize_session=False)
    print(f"   Deleted {deleted_agg} aggregation relationships")
    
    # 2. Get all test batches first (to find their events)
    test_batches = db.query(CoffeeBatch).filter(
        (CoffeeBatch.batch_id.like('TEST%')) | 
        (CoffeeBatch.batch_id.like('RECURSIVE%'))
    ).all()
    batch_ids = [b.id for b in test_batches]
    print(f"   Found {len(test_batches)} test batches")
    
    # 3. Delete events linked to test batches
    if batch_ids:
        deleted_events = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id.in_(batch_ids)
        ).delete(synchronize_session=False)
        print(f"   Deleted {deleted_events} events")
    
    # 4. Delete test batches
    if batch_ids:
        deleted_batches = db.query(CoffeeBatch).filter(
            CoffeeBatch.id.in_(batch_ids)
        ).delete(synchronize_session=False)
        print(f"   Deleted {deleted_batches} batches")
    
    # 5. Delete test farmers (now safe - no FK references)
    deleted_farmers = db.query(FarmerIdentity).filter(
        (FarmerIdentity.farmer_id.like('FARMER-TEST%')) | 
        (FarmerIdentity.farmer_id.like('FARMER-RECURSIVE%'))
    ).delete(synchronize_session=False)
    print(f"   Deleted {deleted_farmers} farmers")
    
    db.commit()
    print("   ✅ Cleanup complete\n")


def test_aggregated_dpp_generation():
    """Test DPP generation for container with multiple farmer batches"""
    
    print("=" * 70)
    print("🧪 TESTING AGGREGATED DPP GENERATION")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    
    # Clean up any existing test data first
    cleanup_test_data(db)
    
    try:
        # Step 1: Create test farmers
        print("👨‍🌾 Step 1: Creating test farmers...")
        farmers = []
        
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        import base64
        
        # Helper to generate keys
        def generate_keypair():
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            return base64.b64encode(private_bytes).decode(), base64.b64encode(public_bytes).decode()
        
        priv1, pub1 = generate_keypair()
        farmer1 = FarmerIdentity(
            farmer_id="FARMER-TEST-001",
            name="Abebe Tadesse",
            did="did:key:farmer1test",
            encrypted_private_key=priv1,
            public_key=pub1,
            latitude=6.1234,
            longitude=38.5678,
            region="Yirgacheffe",
            country_code="ET",
            certification_status="Organic"
        )
        db.add(farmer1)
        farmers.append(farmer1)
        
        priv2, pub2 = generate_keypair()
        farmer2 = FarmerIdentity(
            farmer_id="FARMER-TEST-002",
            name="Tigist Alemu",
            did="did:key:farmer2test",
            encrypted_private_key=priv2,
            public_key=pub2,
            latitude=6.2345,
            longitude=38.6789,
            region="Yirgacheffe",
            country_code="ET",
            certification_status="Organic"
        )
        db.add(farmer2)
        farmers.append(farmer2)
        
        priv3, pub3 = generate_keypair()
        farmer3 = FarmerIdentity(
            farmer_id="FARMER-TEST-003",
            name="Kebede Worku",
            did="did:key:farmer3test",
            encrypted_private_key=priv3,
            public_key=pub3,
            latitude=6.3456,
            longitude=38.7890,
            region="Gedeo",
            country_code="ET",
            certification_status="Fair Trade"
        )
        db.add(farmer3)
        farmers.append(farmer3)
        
        db.commit()
        print(f"   ✅ Created {len(farmers)} farmers")
        print()
        
        # Step 2: Create farmer batches
        print("📦 Step 2: Creating farmer batches...")
        batches = []
        
        batch1 = CoffeeBatch(
            batch_id="TEST-BATCH-001",
            batch_number="001",
            gtin="06141411234567",
            quantity_kg=500.0,
            variety="Arabica Heirloom",
            origin="Yirgacheffe, Ethiopia",
            origin_country="ET",  # ISO 3166-1 alpha-2 code
            origin_region="Yirgacheffe",
            farmer_id=farmer1.id,
            status="VERIFIED",
            created_at=datetime.now(timezone.utc)
        )
        db.add(batch1)
        batches.append(batch1)
        
        batch2 = CoffeeBatch(
            batch_id="TEST-BATCH-002",
            batch_number="002",
            gtin="06141411234568",
            quantity_kg=300.0,
            variety="Arabica Heirloom",
            origin="Yirgacheffe, Ethiopia",
            origin_country="ET",  # ISO 3166-1 alpha-2 code
            origin_region="Yirgacheffe",
            farmer_id=farmer2.id,
            status="VERIFIED",
            created_at=datetime.now(timezone.utc)
        )
        db.add(batch2)
        batches.append(batch2)
        
        batch3 = CoffeeBatch(
            batch_id="TEST-BATCH-003",
            batch_number="003",
            gtin="06141411234569",
            quantity_kg=200.0,
            variety="Arabica Heirloom",
            origin="Gedeo, Ethiopia",
            origin_country="ET",  # ISO 3166-1 alpha-2 code
            origin_region="Gedeo",
            farmer_id=farmer3.id,
            status="VERIFIED",
            created_at=datetime.now(timezone.utc)
        )
        db.add(batch3)
        batches.append(batch3)
        
        db.commit()
        print(f"   ✅ Created {len(batches)} farmer batches")
        for b in batches:
            print(f"      - {b.batch_id}: {b.quantity_kg} kg from {b.farmer.name}")
        print()
        
        # Step 3: Define container SSCC (no CoffeeBatch needed - SSCC is the identifier)
        print("📦 Step 3: Defining export container...")
        total_qty = sum(b.quantity_kg for b in batches)
        container_sscc = "306141411234567892"  # 18-digit SSCC for shipping container
        
        print(f"   ✅ Container SSCC: {container_sscc}")
        print(f"      Total to pack: {total_qty} kg from {len(batches)} batches")
        print()
        
        # Step 4: Create aggregation event using actual implementation
        print("⛓️  Step 4: Creating aggregation event (packing batches)...")
        from voice.epcis.aggregation_events import create_aggregation_event
        
        # Create aggregation event - this will create relationships AND store event
        event_result = create_aggregation_event(
            db=db,
            parent_sscc=container_sscc,
            child_batch_ids=[b.batch_id for b in batches],
            action="ADD",
            biz_step="packing",
            location_gln="0614141000010",
            operator_did="did:key:test_operator",
            submitter_db_id=None
        )
        
        if not event_result:
            raise Exception("Failed to create aggregation event")
        
        print(f"   ✅ Created aggregation event")
        print(f"      Event hash: {event_result['event_hash'][:16]}...")
        print(f"      IPFS CID: {event_result['ipfs_cid']}")
        print(f"      Blockchain TX: {event_result.get('blockchain_tx_hash', 'pending')[:16] if event_result.get('blockchain_tx_hash') else 'pending'}...")
        print(f"      Created {len(event_result['aggregation_ids'])} aggregation relationships")
        print()
        
        # Step 5: Build aggregated DPP
        print("🏗️  Step 5: Building aggregated DPP...")
        dpp = build_aggregated_dpp(container_sscc)
        print(f"   ✅ Generated DPP: {dpp['passportId']}")
        print()
        
        # Step 6: Validate DPP structure
        print("✅ Step 6: Validating DPP structure...")
        
        # Check basic structure
        assert dpp['passportId'] == f"DPP-AGGREGATED-{container_sscc}"
        assert dpp['version'] == "2.0.0"
        assert dpp['type'] == "AggregatedProductPassport"
        print("   ✅ Basic structure valid")
        
        # Check product information
        prod_info = dpp['productInformation']
        assert container_sscc in prod_info['containerID']
        assert prod_info['numberOfContributors'] == 3
        print(f"   ✅ Product info: {prod_info['numberOfContributors']} contributors")
        
        # Check traceability
        contributors = dpp['traceability']['contributors']
        assert len(contributors) == 3
        print(f"   ✅ Traceability: {len(contributors)} farmers")
        
        # Validate contributions
        total_percent = 0.0
        for contributor in contributors:
            farmer_name = contributor['farmer']
            contribution_pct = float(contributor['contributionPercent'].rstrip('%'))
            total_percent += contribution_pct
            
            print(f"      - {farmer_name}: {contributor['contributionPercent']}")
            
            # Check required fields
            assert 'did' in contributor
            assert 'contribution' in contributor
            assert 'origin' in contributor
            assert contributor['origin']['lat'] is not None
            assert contributor['origin']['lon'] is not None
        
        # Contributions should add up to ~100%
        assert 99.0 <= total_percent <= 101.0, f"Contributions total {total_percent}%, expected 100%"
        print(f"   ✅ Contribution percentages valid (total: {total_percent:.1f}%)")
        
        # Check EUDR compliance
        due_diligence = dpp['dueDiligence']
        assert due_diligence['eudrCompliant'] == True
        assert due_diligence['allFarmersGeolocated'] == True
        print("   ✅ EUDR compliance: All farmers geolocated")
        
        # Check blockchain proofs
        blockchain = dpp['blockchain']
        assert blockchain['network'] == "Base Sepolia"
        assert len(blockchain.get('aggregationProofs', [])) > 0
        print(f"   ✅ Blockchain: {len(blockchain.get('aggregationProofs', []))} proofs")
        
        print()
        print("=" * 70)
        print("✅ ALL AGGREGATED DPP TESTS PASSED")
        print("=" * 70)
        print()
        
        # Print summary
        print("📊 DPP Summary:")
        print(f"   Container: {container_sscc}")
        print(f"   Total Quantity: {prod_info['totalQuantity']}")
        print(f"   Contributors: {prod_info['numberOfContributors']} farmers")
        print(f"   EUDR Compliant: ✅ Yes")
        print(f"   All Geolocated: ✅ Yes")
        print(f"   QR Code URL: {dpp['qrCode']['url']}")
        print()
        
        # Optionally save DPP to file
        dpp_file = Path(__file__).parent.parent / "dpp" / "passports" / f"{container_sscc}_aggregated_dpp.json"
        dpp_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dpp_file, 'w') as f:
            json.dump(dpp, f, indent=2)
        print(f"💾 Saved DPP to: {dpp_file}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup test data
        print("\n🧹 Cleaning up test data...")
        try:
            db.rollback()  # Rollback any pending transaction
            db.query(AggregationRelationship).filter(
                AggregationRelationship.parent_sscc == "306141411234567892"
            ).delete()
            db.query(EPCISEvent).filter(
                EPCISEvent.parent_id == "306141411234567892"
            ).delete()
            db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id.in_([
                    "TEST-BATCH-001", "TEST-BATCH-002", "TEST-BATCH-003", "TEST-CONTAINER-001"
                ])
            ).delete()
            db.query(FarmerIdentity).filter(
                FarmerIdentity.did.in_([
                    "did:key:farmer1test", "did:key:farmer2test", "did:key:farmer3test"
                ])
            ).delete()
            db.commit()
            print("   ✅ Test data cleaned up")
        except Exception as e:
            print(f"   ⚠️  Cleanup error (may be ok): {e}")
            db.rollback()
        finally:
            db.close()


def test_recursive_dpp_generation():
    """Test recursive DPP generation for multi-level aggregation"""
    
    print("\n" + "=" * 70)
    print("🧪 TESTING RECURSIVE DPP GENERATION (MULTI-LEVEL)")
    print("=" * 70)
    print()
    
    from voice.epcis.aggregation_events import create_aggregation_event
    from dpp.dpp_builder import build_recursive_dpp
    
    db = SessionLocal()
    
    # Clean up any existing test data first
    cleanup_test_data(db)
    
    try:
        # ============================================================
        # LEVEL 1: Create farmers and batches
        # ============================================================
        print("📦 Level 1: Creating farmer batches...")
        
        # Create 6 farmers (2 per container)
        farmers = []
        for i in range(1, 7):
            farmer = FarmerIdentity(
                farmer_id=f'FARMER-RECURSIVE-{i:03d}',
                did=f'did:key:recursivefarmer{i}',
                encrypted_private_key=base64.b64encode(os.urandom(32)).decode('utf-8'),
                public_key=base64.b64encode(os.urandom(32)).decode('utf-8'),
                name=f'Recursive Farmer {i}',
                latitude=6.0 + (i * 0.1),
                longitude=38.0 + (i * 0.1),
                region='Yirgacheffe',
                country_code='ET',
                certification_status='Organic'
            )
            db.add(farmer)
            farmers.append(farmer)
        
        db.commit()
        print(f"   ✅ Created {len(farmers)} farmers")
        
        # Create 6 batches (100kg each)
        batches = []
        for i, farmer in enumerate(farmers, 1):
            batch = CoffeeBatch(
                batch_id=f'RECURSIVE-BATCH-{i:03d}',
                gtin=f'0614141123456{i}',
                batch_number=f'{i:03d}',
                quantity_kg=100.0,
                origin=f'{farmer.region}, Ethiopia',
                origin_country='ET',
                origin_region=farmer.region,
                variety='Arabica Heirloom',
                farmer_id=farmer.id,
                status='VERIFIED'
            )
            db.add(batch)
            batches.append(batch)
        
        db.commit()
        print(f"   ✅ Created {len(batches)} batches (100kg each)")
        
        # ============================================================
        # LEVEL 2: Aggregate batches into 3 containers
        # ============================================================
        print("\n📦 Level 2: Aggregating batches into containers...")
        
        containers = []
        
        # Container 1: Batches 1-2 (200kg total)
        container1_sscc = "306141411111111118"
        result1 = create_aggregation_event(
            db=db,
            parent_sscc=container1_sscc,
            child_batch_ids=[batches[0].batch_id, batches[1].batch_id],
            action="ADD",
            biz_step="packing",
            location_gln="0614141000010",
            operator_did="did:key:test_operator"
        )
        containers.append({'sscc': container1_sscc, 'kg': 200.0})
        print(f"   ✅ Container 1: {container1_sscc} (200kg from 2 batches)")
        
        # Container 2: Batches 3-4 (200kg total)
        container2_sscc = "306141412222222227"
        result2 = create_aggregation_event(
            db=db,
            parent_sscc=container2_sscc,
            child_batch_ids=[batches[2].batch_id, batches[3].batch_id],
            action="ADD",
            biz_step="packing",
            location_gln="0614141000010",
            operator_did="did:key:test_operator"
        )
        containers.append({'sscc': container2_sscc, 'kg': 200.0})
        print(f"   ✅ Container 2: {container2_sscc} (200kg from 2 batches)")
        
        # Container 3: Batches 5-6 (200kg total)
        container3_sscc = "306141413333333336"
        result3 = create_aggregation_event(
            db=db,
            parent_sscc=container3_sscc,
            child_batch_ids=[batches[4].batch_id, batches[5].batch_id],
            action="ADD",
            biz_step="packing",
            location_gln="0614141000010",
            operator_did="did:key:test_operator"
        )
        containers.append({'sscc': container3_sscc, 'kg': 200.0})
        print(f"   ✅ Container 3: {container3_sscc} (200kg from 2 batches)")
        
        # ============================================================
        # TEST: Generate aggregated DPPs for each container
        # ============================================================
        print("\n🏗️  Testing aggregated DPP generation for containers...")
        
        # Test container 1 (should trace back to 2 farmers)
        dpp1 = build_aggregated_dpp(container1_sscc)
        print(f"   ✅ Container 1 DPP: {len(dpp1.get('contributors', []))} farmers, {dpp1.get('totalQuantity')}kg")
        
        # Test container 2 (should trace back to 2 farmers)
        dpp2 = build_aggregated_dpp(container2_sscc)
        print(f"   ✅ Container 2 DPP: {len(dpp2.get('contributors', []))} farmers, {dpp2.get('totalQuantity')}kg")
        
        # Test container 3 (should trace back to 2 farmers)
        dpp3 = build_aggregated_dpp(container3_sscc)
        print(f"   ✅ Container 3 DPP: {len(dpp3.get('contributors', []))} farmers, {dpp3.get('totalQuantity')}kg")
        
        # Note: Level 3 (container→pallet) aggregation requires extending create_aggregation_event()
        # to support SSCC children, not just batch_id children. Skipping for now.
        
        # ============================================================
        # VALIDATION
        # ============================================================
        print("\n✅ Validating all container DPPs...")
        
        # Validate each container DPP
        for i, (dpp, sscc) in enumerate([(dpp1, container1_sscc), (dpp2, container2_sscc), (dpp3, container3_sscc)], 1):
            print(f"\n   Container {i} ({sscc}):")
            
            # Check basic structure
            assert dpp['containerId'] == sscc
            assert dpp['type'] == 'AggregatedProductPassport'
            print(f"      ✅ Basic structure valid")
            
            # Check total quantity (200kg per container)
            total_qty = dpp['productInformation']['totalQuantity']
            # Handle both numeric and string formats
            if isinstance(total_qty, str):
                total_qty_num = float(total_qty.replace(' kg', ''))
            else:
                total_qty_num = total_qty
            assert abs(total_qty_num - 200.0) < 0.01, f"Expected 200kg, got {total_qty}"
            print(f"      ✅ Total quantity: {total_qty}")
            
            # Check farmer count (should trace back to 2 farmers per container)
            contributors = dpp['traceability']['contributors']
            assert len(contributors) == 2, f"Expected 2 farmers, got {len(contributors)}"
            print(f"      ✅ Traced to {len(contributors)} farmers")
            
            # Check contribution percentages (should be 50% each)
            for contributor in contributors:
                percentage = float(contributor['contributionPercent'].rstrip('%'))
                assert 49.0 <= percentage <= 51.0, f"Expected ~50%, got {percentage}%"
            print(f"      ✅ Equal contributions: 50% each")
            
            # Check EUDR compliance
            due_diligence = dpp['dueDiligence']
            assert due_diligence['eudrCompliant'] == True
            assert due_diligence['allFarmersGeolocated'] == True
            print(f"      ✅ EUDR compliant")
        
        print()
        print("=" * 70)
        print("✅ ALL MULTI-LEVEL AGGREGATION TESTS PASSED")
        print("=" * 70)
        
        print("\n📊 Test Summary:")
        print(f"   Total Farmers: 6")
        print(f"   Total Batches: 6 (100kg each)")
        print(f"   Containers Created: 3 (200kg each)")
        print(f"   Total Quantity: 600kg")
        print(f"   EUDR Compliant: ✅ Yes")
        print(f"   All Geolocated: ✅ Yes")
        print()
        print("   Note: This test validates 2-level aggregation (batches → containers).")
        print("   3-level aggregation (containers → pallet) requires extending")
        print("   create_aggregation_event() to support SSCC children.")
        print()
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print("🧹 Cleaning up test data...")
        try:
            # Delete in correct order: aggregations → events → batches → farmers
            db.query(AggregationRelationship).filter(
                AggregationRelationship.parent_sscc.in_([
                    container1_sscc, container2_sscc, container3_sscc
                ])
            ).delete(synchronize_session=False)
            
            db.query(EPCISEvent).filter(
                EPCISEvent.event_hash.like('RECURSIVE-%')
            ).delete(synchronize_session=False)
            
            db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id.like('RECURSIVE-BATCH-%')
            ).delete(synchronize_session=False)
            
            db.query(FarmerIdentity).filter(
                FarmerIdentity.farmer_id.like('FARMER-RECURSIVE-%')
            ).delete(synchronize_session=False)
            
            db.commit()
            print("   ✅ Test data cleaned up")
        except Exception as e:
            print(f"   ⚠️  Cleanup error: {e}")
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    print("🧪 Starting Aggregated DPP Tests\n")
    
    success = test_aggregated_dpp_generation()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        test_recursive_dpp_generation()
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
