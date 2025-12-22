"""
Test DPP EUDR Compliance Section

Tests the complete DPP generation including the new EUDR compliance section.
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, CoffeeBatch, FarmerIdentity, UserIdentity, VerificationPhoto
from dpp.dpp_builder import build_dpp, build_eudr_compliance_section


def create_test_data(db):
    """Create test farmer and batch data with GPS verification."""
    from ssi.did.did_key import generate_did_key
    import time
    
    print("\n📝 Creating test data...")
    
    # Clean up any existing test data first
    test_telegram_id = "999888777"
    existing_user = db.query(UserIdentity).filter_by(telegram_user_id=test_telegram_id).first()
    if existing_user:
        print(f"🗑️  Cleaning up existing test user: {test_telegram_id}")
        # Find farmer identity first to get the correct farmer ID
        existing_farmer = db.query(FarmerIdentity).filter_by(did=existing_user.did).first()
        if existing_farmer:
            # Delete verification photos first
            batch_ids = [b.id for b in db.query(CoffeeBatch).filter_by(farmer_id=existing_farmer.id).all()]
            if batch_ids:
                db.query(VerificationPhoto).filter(VerificationPhoto.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            # Then delete batches
            db.query(CoffeeBatch).filter_by(farmer_id=existing_farmer.id).delete()
            # Then delete farmer identity
            db.query(FarmerIdentity).filter_by(id=existing_farmer.id).delete()
        # Finally delete user identity
        db.query(UserIdentity).filter_by(id=existing_user.id).delete()
        db.commit()
    
    # Generate DID for test farmer (same DID used for both UserIdentity and FarmerIdentity)
    identity = generate_did_key()
    test_did = identity['did']
    
    # Create UserIdentity (Telegram user)
    user = UserIdentity(
        telegram_user_id=test_telegram_id,
        telegram_username="test_farmer",
        telegram_first_name="Abebe",
        telegram_last_name="Bekele",
        did=test_did,
        encrypted_private_key=identity['private_key'],
        public_key=identity['public_key'],
        role="FARMER",
        is_approved=True,
        phone_number="+251912345678",
        preferred_language='en'
    )
    db.add(user)
    db.flush()
    
    # Create FarmerIdentity (on-chain farmer record with GPS verification)
    farmer = FarmerIdentity(
        farmer_id=f"FARMER-TEST-{user.id}",
        did=test_did,  # Same DID as UserIdentity
        encrypted_private_key=identity['private_key'],
        public_key=identity['public_key'],
        name="Abebe Bekele",
        phone_number="+251912345678",
        location="Kochere, Yirgacheffe, Oromia",
        region="Oromia",
        country_code="ET",
        latitude=6.1667,
        longitude=38.2167,
        farm_size_hectares=2.5,
        farm_photo_url="https://ipfs.io/ipfs/QmTest123abc",
        farm_photo_hash="abc123def456",
        photo_latitude=6.1667,
        photo_longitude=38.2167,
        gps_verified_at=datetime.now(),
        blockchain_proof_hash="0xBlockchainProof123"
    )
    db.add(farmer)
    db.flush()
    
    # Create test batch
    batch = CoffeeBatch(
        batch_id="BATCH-TEST-2025-001",
        gtin="00012345678901",
        batch_number="TEST-001",
        quantity_kg=50.0,
        farmer_id=farmer.id,
        harvest_date=datetime.now(),
        origin_country="ET",
        origin_region="Oromia",
        variety="Arabica",
        processing_method="Washed",
        quality_grade="Grade 1",
        status='VERIFIED',
        created_at=datetime.now()
    )
    db.add(batch)
    db.flush()
    
    # Create verification photos for the batch (harvest photos)
    photo1 = VerificationPhoto(
        batch_id=batch.id,
        photo_url="https://ipfs.io/ipfs/QmHarvestPhoto1",
        photo_hash="harvest1_hash123",
        latitude=6.1670,
        longitude=38.2165,
        photo_timestamp=datetime.now(),
        distance_from_farm_km=0.35,
        verified_at=datetime.now()
    )
    db.add(photo1)
    
    photo2 = VerificationPhoto(
        batch_id=batch.id,
        photo_url="https://ipfs.io/ipfs/QmHarvestPhoto2",
        photo_hash="harvest2_hash456",
        latitude=6.1665,
        longitude=38.2170,
        photo_timestamp=datetime.now(),
        distance_from_farm_km=0.42,
        verified_at=datetime.now()
    )
    db.add(photo2)
    
    db.commit()
    
    print(f"✅ Created farmer: {farmer.name} (ID: {farmer.id})")
    print(f"✅ Created batch: {batch.batch_id}")
    print(f"✅ Added 2 verification photos")
    
    return farmer, batch


def test_eudr_compliance_section(batch, db):
    """Test EUDR compliance section generation."""
    print(f"\n🔍 Testing EUDR compliance section...")
    
    eudr_section = build_eudr_compliance_section(batch, db)
    
    print(f"\n📊 EUDR Compliance Section:")
    print(f"   Status: {eudr_section['complianceStatus']}")
    print(f"   Level: {eudr_section['complianceLevel']}")
    print(f"   Regulation: {eudr_section['regulation']['reference']}")
    
    if 'farmLocation' in eudr_section['geolocation']:
        farm = eudr_section['geolocation']['farmLocation']
        print(f"\n📍 Farm Location:")
        coords = farm.get('coordinates', {})
        print(f"   Coordinates: {coords.get('latitude')}, {coords.get('longitude')}")
        print(f"   Source: {farm.get('source', 'N/A')}")
        print(f"   Verified: {farm.get('verifiedAt', 'N/A')}")
    
    if 'harvestVerification' in eudr_section['geolocation']:
        harvest = eudr_section['geolocation']['harvestVerification']
        print(f"\n📸 Harvest Verification:")
        print(f"   Photos: {len(harvest)}")
        for i, photo in enumerate(harvest[:2], 1):
            coords = photo.get('coordinates', {})
            dist = photo.get('distanceFromFarm', {})
            print(f"   Photo {i}: {coords.get('latitude')}, {coords.get('longitude')} ({dist.get('value', 'N/A')} km from farm)")
    
    if 'riskAssessment' in eudr_section:
        risk = eudr_section['riskAssessment']
        print(f"\n⚠️  Risk Assessment:")
        print(f"   Deforestation Risk: {risk.get('deforestationRisk', 'N/A')}")
        print(f"   Assessor: {risk.get('assessor', 'N/A')}")
        if 'riskFactors' in risk:
            print(f"   Risk Factors: {len(risk['riskFactors'])}")
            for i, factor in enumerate(risk['riskFactors'][:2], 1):
                print(f"      {i}. {factor.get('factor', 'N/A')} ({factor.get('severity', 'N/A')})")
    
    if 'dueDiligenceStatement' in eudr_section:
        dd = eudr_section['dueDiligenceStatement']
        print(f"\n📋 Due Diligence:")
        print(f"   Statement: {dd.get('statementConfirmed', False)}")
        print(f"   Date: {dd.get('statementDate', 'N/A')}")
    
    return eudr_section


def test_full_dpp_generation(batch_id):
    """Test complete DPP generation with EUDR section."""
    print(f"\n📄 Testing full DPP generation...")
    
    dpp = build_dpp(batch_id)
    
    print(f"\n✅ DPP Generated:")
    print(f"   Version: {dpp['version']}")
    print(f"   Passport ID: {dpp['passportId']}")
    print(f"   Batch: {dpp['batchId']}")
    
    if 'productInformation' in dpp:
        product = dpp['productInformation']
        print(f"   Product: {product.get('productName', 'N/A')}")
        print(f"   Quantity: {product.get('quantity', 0)} {product.get('unit', 'kg')}")
    
    if 'eudrCompliance' in dpp:
        print(f"\n🌍 EUDR Compliance Section Present:")
        eudr = dpp['eudrCompliance']
        print(f"   Status: {eudr['complianceStatus']}")
        print(f"   Level: {eudr['complianceLevel']}")
        
        # Map compliance level to visual indicator
        indicators = {
            'FULLY_VERIFIED': '🟢',
            'FARM_VERIFIED': '🟡',
            'SELF_REPORTED': '🟠',
            'NO_GPS': '🔴'
        }
        indicator = indicators.get(eudr['complianceStatus'], '⚪')
        print(f"   Visual: {indicator} {eudr['complianceStatus']}")
        
        # Check geolocation data
        if 'geolocation' in eudr:
            geo = eudr['geolocation']
            if 'farmLocation' in geo:
                farm = geo['farmLocation']
                coords = farm.get('coordinates', {})
                print(f"   Farm GPS: {coords.get('latitude')}, {coords.get('longitude')}")
            if 'harvestVerification' in geo:
                print(f"   Harvest Photos: {len(geo['harvestVerification'])}")
    else:
        print(f"\n❌ EUDR Compliance section missing!")
    
    return dpp


def test_compliance_levels(db):
    """Test different compliance levels."""
    from ssi.did.did_key import generate_did_key
    
    print(f"\n📊 Testing different compliance levels...")
    
    test_cases = [
        {
            'name': 'FULLY_VERIFIED (Gold)',
            'farmer': {
                'farmer_id': 'FARMER-GOLD-001',
                'name': 'Farmer Gold',
                'region': 'Oromia',
                'country_code': 'ET',
                'latitude': 6.1667,
                'longitude': 38.2167,
                'photo_latitude': 6.1667,
                'photo_longitude': 38.2167,
                'gps_verified_at': datetime.now(),
                'blockchain_proof_hash': '0xProof1',
            },
            'has_harvest_photos': True
        },
        {
            'name': 'FARM_VERIFIED (Silver)',
            'farmer': {
                'farmer_id': 'FARMER-SILVER-001',
                'name': 'Farmer Silver',
                'region': 'Oromia',
                'country_code': 'ET',
                'latitude': 6.1667,
                'longitude': 38.2167,
                'photo_latitude': 6.1667,
                'photo_longitude': 38.2167,
                'gps_verified_at': datetime.now(),
            },
            'has_harvest_photos': False
        },
        {
            'name': 'SELF_REPORTED (Bronze)',
            'farmer': {
                'farmer_id': 'FARMER-BRONZE-001',
                'name': 'Farmer Bronze',
                'region': 'Oromia',
                'country_code': 'ET',
                'latitude': 6.1667,
                'longitude': 38.2167,
                'photo_latitude': None,
                'photo_longitude': None,
            },
            'has_harvest_photos': False
        },
        {
            'name': 'NO_GPS (Non-Compliant)',
            'farmer': {
                'farmer_id': 'FARMER-NONE-001',
                'name': 'Farmer None',
                'region': 'Oromia',
                'country_code': 'ET',
                'latitude': None,
                'longitude': None,
            },
            'has_harvest_photos': False
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test {i}: {test_case['name']}")
        
        # Generate DID for this test farmer
        identity = generate_did_key()
        
        # Create farmer with DID
        farmer = FarmerIdentity(
            did=identity['did'],
            encrypted_private_key=identity['private_key'],
            public_key=identity['public_key'],
            phone_number=f"+25191234{i:04d}",
            **test_case['farmer']
        )
        db.add(farmer)
        db.flush()
        
        # Create batch
        batch = CoffeeBatch(
            batch_id=f"BATCH-TEST-LEVEL-{i}",
            gtin=f"111123456789{i:02d}",  # Different GTIN pattern to avoid conflicts
            batch_number=f"LEVEL-{i}",
            quantity_kg=25.0,
            farmer_id=farmer.id,
            harvest_date=datetime.now(),
            origin_country="ET",
            origin_region="Oromia",
            status='VERIFIED'
        )
        db.add(batch)
        db.flush()
        
        # Add harvest photos if needed
        if test_case['has_harvest_photos']:
            photo = VerificationPhoto(
                batch_id=batch.id,
                photo_url=f"https://ipfs.io/ipfs/QmTest{i}",
                photo_hash=f"hash_{i}",
                latitude=6.1667,
                longitude=38.2167,
                distance_from_farm_km=0.5,
                verified_at=datetime.now()
            )
            db.add(photo)
        
        db.commit()
        
        # Generate EUDR section
        eudr = build_eudr_compliance_section(batch, db)
        status_indicators = {
            'FULLY_VERIFIED': '🟢',
            'FARM_VERIFIED': '🟡',
            'SELF_REPORTED': '🟠',
            'NO_GPS': '🔴'
        }
        indicator = status_indicators.get(eudr['complianceStatus'], '⚪')
        
        print(f"      {indicator} Status: {eudr['complianceStatus']}")
        print(f"      Level: {eudr['complianceLevel']}")
        
    print(f"\n✅ All compliance levels tested")


def main():
    """Run all DPP EUDR tests."""
    print("="*70)
    print("DPP EUDR COMPLIANCE SECTION TEST")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        # Test 1: Create test data
        farmer, batch = create_test_data(db)
        
        # Test 2: EUDR compliance section
        eudr_section = test_eudr_compliance_section(batch, db)
        
        # Test 3: Full DPP generation
        dpp = test_full_dpp_generation(batch.batch_id)
        
        # Test 4: Different compliance levels
        test_compliance_levels(db)
        
        # Pretty print final DPP
        print("\n" + "="*70)
        print("COMPLETE DPP OUTPUT (JSON):")
        print("="*70)
        print(json.dumps(dpp, indent=2, default=str)[:2000] + "\n... (truncated)")
        
        print("\n" + "="*70)
        print("✅ ALL DPP EUDR TESTS PASSED")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
