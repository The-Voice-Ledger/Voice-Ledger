"""
Test multi-actor registration for Lab 14: Marketplace Implementation

Tests the complete registration flow for:
- Exporters (with export license, port access, shipping capacity)
- Buyers (with business type, country, quality preferences)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import SessionLocal, UserIdentity, Organization, PendingRegistration, Exporter, Buyer, UserReputation
from datetime import datetime

def test_exporter_registration():
    """Test complete exporter registration flow"""
    print("\n🧪 Test 1: Exporter Registration")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Create pending registration (simulates /register flow)
        pending = PendingRegistration(
            telegram_user_id=999001,
            telegram_username="test_exporter",
            telegram_first_name="Mohammed",
            telegram_last_name="Ahmed",
            requested_role="EXPORTER",
            full_name="Mohammed Ahmed",
            organization_name="Addis Export Company",
            location="Addis Ababa, Ethiopia",
            phone_number="+251911234567",
            export_license="EXP-2025-1234",
            port_access="DJIBOUTI",
            shipping_capacity_tons=500.0,
            status="PENDING"
        )
        db.add(pending)
        db.commit()
        print(f"✓ Created pending registration: REG-{pending.id:04d}")
        
        # Step 2: Admin approves (simulates /approve command)
        # First create organization
        from ssi.org_identity import generate_organization_did
        org_did_data = generate_organization_did()
        
        organization = Organization(
            name=pending.organization_name,
            type="EXPORTER",
            did=org_did_data['did'],
            encrypted_private_key=org_did_data['encrypted_private_key'],
            public_key=org_did_data['public_key'],
            location=pending.location,
            phone_number=pending.phone_number,
            registration_number=pending.export_license
        )
        db.add(organization)
        db.commit()
        print(f"✓ Created organization: {organization.name} (ID: {organization.id})")
        
        # Create user identity
        from ssi.user_identity import get_or_create_user_identity
        user_response = get_or_create_user_identity(
            telegram_user_id=str(pending.telegram_user_id),
            telegram_username=pending.telegram_username,
            telegram_first_name=pending.telegram_first_name,
            telegram_last_name=pending.telegram_last_name,
            db_session=db
        )
        
        # Get the actual user object
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(pending.telegram_user_id)).first()
        user.role = "EXPORTER"
        user.organization_id = organization.id
        user.is_approved = True
        user.approved_at = datetime.utcnow()
        db.commit()
        print(f"✓ Created user: {user.telegram_username} (Role: {user.role})")
        
        # Create exporter record
        exporter = Exporter(
            organization_id=organization.id,
            export_license=pending.export_license,
            port_access=pending.port_access,
            shipping_capacity_tons=pending.shipping_capacity_tons,
            active_shipping_lines=["Maersk", "MSC"],
            customs_clearance_capability=True,
            certifications={"ISO9001": True, "HACCP": True}
        )
        db.add(exporter)
        db.commit()
        print(f"✓ Created exporter record (ID: {exporter.id})")
        
        # Create reputation record
        reputation = UserReputation(
            user_id=user.id,
            reputation_level="BRONZE"
        )
        db.add(reputation)
        db.commit()
        print(f"✓ Created reputation record for user {user.id}")
        
        # Update pending registration status
        pending.status = "APPROVED"
        pending.reviewed_at = datetime.utcnow()
        db.commit()
        print(f"✓ Approved registration: REG-{pending.id:04d}")
        
        # Verify complete setup
        exporter_check = db.query(Exporter).filter_by(organization_id=organization.id).first()
        assert exporter_check is not None, "Exporter record not found"
        assert exporter_check.export_license == "EXP-2025-1234"
        assert exporter_check.port_access == "DJIBOUTI"
        assert exporter_check.shipping_capacity_tons == 500.0
        
        print(f"\n✅ Exporter registration complete!")
        print(f"   Organization: {organization.name}")
        print(f"   DID: {organization.did[:50]}...")
        print(f"   User: {user.telegram_username} (ID: {user.id})")
        print(f"   Export License: {exporter.export_license}")
        print(f"   Port: {exporter.port_access}")
        print(f"   Capacity: {exporter.shipping_capacity_tons} tons/year")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_buyer_registration():
    """Test complete buyer registration flow"""
    print("\n🧪 Test 2: Buyer Registration")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Create pending registration
        pending = PendingRegistration(
            telegram_user_id=999002,
            telegram_username="test_buyer",
            telegram_first_name="Sofia",
            telegram_last_name="Martinez",
            requested_role="BUYER",
            full_name="Sofia Martinez",
            organization_name="European Coffee Roasters",
            location="Barcelona, Spain",
            phone_number="+34612345678",
            business_type="ROASTER",
            country="Spain",
            target_volume_tons_annual=100.0,
            quality_preferences={"min_cup_score": 84, "certifications": ["Organic", "Fair Trade"]},
            status="PENDING"
        )
        db.add(pending)
        db.commit()
        print(f"✓ Created pending registration: REG-{pending.id:04d}")
        
        # Step 2: Admin approves
        from ssi.org_identity import generate_organization_did
        org_did_data = generate_organization_did()
        
        organization = Organization(
            name=pending.organization_name,
            type="BUYER",
            did=org_did_data['did'],
            encrypted_private_key=org_did_data['encrypted_private_key'],
            public_key=org_did_data['public_key'],
            location=pending.location,
            phone_number=pending.phone_number
        )
        db.add(organization)
        db.commit()
        print(f"✓ Created organization: {organization.name} (ID: {organization.id})")
        
        # Create user identity
        from ssi.user_identity import get_or_create_user_identity
        user_response = get_or_create_user_identity(
            telegram_user_id=str(pending.telegram_user_id),
            telegram_username=pending.telegram_username,
            telegram_first_name=pending.telegram_first_name,
            telegram_last_name=pending.telegram_last_name,
            db_session=db
        )
        
        # Get the actual user object
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(pending.telegram_user_id)).first()
        user.role = "BUYER"
        user.organization_id = organization.id
        user.is_approved = True
        user.approved_at = datetime.utcnow()
        db.commit()
        print(f"✓ Created user: {user.telegram_username} (Role: {user.role})")
        
        # Create buyer record
        buyer = Buyer(
            organization_id=organization.id,
            business_type=pending.business_type,
            country=pending.country,
            target_volume_tons_annual=pending.target_volume_tons_annual,
            quality_preferences=pending.quality_preferences,
            payment_terms="NET_30",
            import_licenses={"EU_IMPORT": "EU-2025-5678"},
            certifications_required=["Organic", "Fair Trade"]
        )
        db.add(buyer)
        db.commit()
        print(f"✓ Created buyer record (ID: {buyer.id})")
        
        # Create reputation record
        reputation = UserReputation(
            user_id=user.id,
            reputation_level="BRONZE"
        )
        db.add(reputation)
        db.commit()
        print(f"✓ Created reputation record for user {user.id}")
        
        # Update pending registration status
        pending.status = "APPROVED"
        pending.reviewed_at = datetime.utcnow()
        db.commit()
        print(f"✓ Approved registration: REG-{pending.id:04d}")
        
        # Verify complete setup
        buyer_check = db.query(Buyer).filter_by(organization_id=organization.id).first()
        assert buyer_check is not None, "Buyer record not found"
        assert buyer_check.business_type == "ROASTER"
        assert buyer_check.country == "Spain"
        assert buyer_check.target_volume_tons_annual == 100.0
        
        print(f"\n✅ Buyer registration complete!")
        print(f"   Organization: {organization.name}")
        print(f"   DID: {organization.did[:50]}...")
        print(f"   User: {user.telegram_username} (ID: {user.id})")
        print(f"   Business Type: {buyer.business_type}")
        print(f"   Country: {buyer.country}")
        print(f"   Target Volume: {buyer.target_volume_tons_annual} tons/year")
        print(f"   Quality Prefs: {buyer.quality_preferences}")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_reputation_system():
    """Test reputation tracking"""
    print("\n🧪 Test 3: Reputation System")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Find a user with reputation
        reputation = db.query(UserReputation).first()
        if not reputation:
            print("⚠️ No reputation records found (expected if fresh database)")
            return True
        
        # Update reputation
        reputation.completed_transactions += 1
        reputation.total_volume_kg += 500.0
        reputation.on_time_deliveries += 1
        reputation.average_rating = 4.5
        reputation.last_transaction_at = datetime.utcnow()
        
        # Check level upgrade
        if reputation.completed_transactions >= 10 and reputation.reputation_level == "BRONZE":
            reputation.reputation_level = "SILVER"
            print(f"✓ User upgraded to SILVER level!")
        
        db.commit()
        
        print(f"✓ Updated reputation for user {reputation.user_id}")
        print(f"   Transactions: {reputation.completed_transactions}")
        print(f"   Volume: {reputation.total_volume_kg} kg")
        print(f"   On-time: {reputation.on_time_deliveries}")
        print(f"   Rating: {reputation.average_rating}/5.0")
        print(f"   Level: {reputation.reputation_level}")
        
        print(f"\n✅ Reputation system working!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("LAB 14: Multi-Actor Marketplace Registration Tests")
    print("=" * 60)
    
    results = []
    
    # Test 1: Exporter registration
    results.append(("Exporter Registration", test_exporter_registration()))
    
    # Test 2: Buyer registration  
    results.append(("Buyer Registration", test_buyer_registration()))
    
    # Test 3: Reputation system
    results.append(("Reputation System", test_reputation_system()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All marketplace registration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
