"""
Test script for Lab 9 Extension: Multi-Actor Registration

Tests:
1. Exporter registration flow
2. Buyer registration flow
3. Admin approval with role-specific records
4. Reputation initialization
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, PendingRegistration, UserIdentity, Organization, Exporter, Buyer, UserReputation
from datetime import datetime

def cleanup_test_data():
    """Remove test registrations and organizations"""
    db = SessionLocal()
    try:
        # Test user IDs
        test_users = [999998, 999999, 9999997]
        
        # Delete test pending registrations
        db.query(PendingRegistration).filter(
            PendingRegistration.telegram_user_id.in_(test_users)
        ).delete(synchronize_session=False)
        
        # Find test organizations
        test_org_names = ['Test Exporter Ltd', 'Test Roasters Inc', 'TestCooperative123']
        test_orgs = db.query(Organization).filter(
            Organization.name.in_(test_org_names)
        ).all()
        
        for org in test_orgs:
            # Delete exporter/buyer records
            db.query(Exporter).filter_by(organization_id=org.id).delete()
            db.query(Buyer).filter_by(organization_id=org.id).delete()
            
            # Delete user identities linked to this org
            users = db.query(UserIdentity).filter_by(organization_id=org.id).all()
            for user in users:
                # Delete reputation
                db.query(UserReputation).filter_by(user_id=user.id).delete()
            
            db.query(UserIdentity).filter_by(organization_id=org.id).delete()
            
            # Delete organization
            db.query(Organization).filter_by(id=org.id).delete()
        
        # Delete test users by telegram_user_id
        for user_id in test_users:
            user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
            if user:
                db.query(UserReputation).filter_by(user_id=user.id).delete()
                db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).delete()
        
        db.commit()
        print("✅ Cleaned up test data")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Cleanup error: {e}")
    finally:
        db.close()


def test_exporter_registration():
    """Test exporter registration with license and port"""
    print("\n" + "="*60)
    print("TEST 1: Exporter Registration")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Create test exporter registration
        exporter_reg = PendingRegistration(
            telegram_user_id=999998,
            telegram_username="test_exporter",
            telegram_first_name="John",
            telegram_last_name="Exporter",
            requested_role="EXPORTER",
            full_name="John Exporter Smith",
            organization_name="Test Exporter Ltd",
            location="Addis Ababa, Ethiopia",
            phone_number="+251911234567",
            registration_number="EXP-REG-2024-001",
            export_license="EXP-LICENSE-2024-5678",
            port_access="DJIBOUTI",
            shipping_capacity_tons=150.0,
            reason="Want to export Ethiopian coffee globally",
            status="PENDING"
        )
        
        db.add(exporter_reg)
        db.commit()
        db.refresh(exporter_reg)
        
        print(f"✅ Created exporter registration REG-{exporter_reg.id:04d}")
        print(f"   Role: {exporter_reg.requested_role}")
        print(f"   Export License: {exporter_reg.export_license}")
        print(f"   Primary Port: {exporter_reg.port_access}")
        print(f"   Shipping Capacity: {exporter_reg.shipping_capacity_tons} tons/year")
        
        return exporter_reg.id
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating exporter registration: {e}")
        return None
    finally:
        db.close()


def test_buyer_registration():
    """Test buyer registration with business type and country"""
    print("\n" + "="*60)
    print("TEST 2: Buyer Registration")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Create test buyer registration
        buyer_reg = PendingRegistration(
            telegram_user_id=999999,
            telegram_username="test_buyer",
            telegram_first_name="Sarah",
            telegram_last_name="Buyer",
            requested_role="BUYER",
            full_name="Sarah Buyer Johnson",
            organization_name="Test Roasters Inc",
            location="New York, USA",
            phone_number="+12125551234",
            registration_number="BUYER-REG-2024-002",
            business_type="ROASTER",
            country="United States",
            target_volume_tons_annual=50.0,
            quality_preferences={"description": "Grade 1, Organic certified, cup score 85+"},
            reason="Looking for high-quality Ethiopian coffee",
            status="PENDING"
        )
        
        db.add(buyer_reg)
        db.commit()
        db.refresh(buyer_reg)
        
        print(f"✅ Created buyer registration REG-{buyer_reg.id:04d}")
        print(f"   Role: {buyer_reg.requested_role}")
        print(f"   Business Type: {buyer_reg.business_type}")
        print(f"   Country: {buyer_reg.country}")
        print(f"   Target Volume: {buyer_reg.target_volume_tons_annual} tons/year")
        print(f"   Quality Prefs: {buyer_reg.quality_preferences}")
        
        return buyer_reg.id
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating buyer registration: {e}")
        return None
    finally:
        db.close()


def verify_approval_results(registration_id, expected_role):
    """Verify that approval created all necessary records"""
    print(f"\n📊 Verifying approval results for REG-{registration_id:04d}")
    
    db = SessionLocal()
    try:
        # Check registration status
        registration = db.query(PendingRegistration).filter_by(id=registration_id).first()
        if not registration:
            print(f"❌ Registration not found")
            return False
        
        if registration.status != 'APPROVED':
            print(f"❌ Registration status is {registration.status}, expected APPROVED")
            return False
        
        print(f"✅ Registration status: {registration.status}")
        
        # Check organization was created
        org = db.query(Organization).filter_by(name=registration.organization_name).first()
        if not org:
            print(f"❌ Organization not created")
            return False
        
        print(f"✅ Organization created: {org.name} (ID: {org.id})")
        print(f"   Type: {org.organization_type}")
        print(f"   DID: {org.did[:50]}...")
        
        # Check role-specific record
        if expected_role == 'EXPORTER':
            exporter = db.query(Exporter).filter_by(organization_id=org.id).first()
            if not exporter:
                print(f"❌ Exporter record not created")
                return False
            print(f"✅ Exporter record created:")
            print(f"   Export License: {exporter.export_license}")
            print(f"   Primary Port: {exporter.port_access}")
            print(f"   Shipping Capacity: {exporter.shipping_capacity_tons} tons/year")
            
        elif expected_role == 'BUYER':
            buyer = db.query(Buyer).filter_by(organization_id=org.id).first()
            if not buyer:
                print(f"❌ Buyer record not created")
                return False
            print(f"✅ Buyer record created:")
            print(f"   Business Type: {buyer.business_type}")
            print(f"   Country: {buyer.country}")
            print(f"   Target Volume: {buyer.target_volume_tons_annual} tons/year")
        
        # Check user identity
        user = db.query(UserIdentity).filter_by(
            telegram_user_id=str(registration.telegram_user_id)
        ).first()
        if not user:
            print(f"❌ User identity not created")
            return False
        
        print(f"✅ User identity created/updated:")
        print(f"   Role: {user.role}")
        print(f"   Organization ID: {user.organization_id}")
        print(f"   Is Approved: {user.is_approved}")
        print(f"   DID: {user.did[:50]}...")
        
        # Check reputation record
        reputation = db.query(UserReputation).filter_by(user_id=user.id).first()
        if not reputation:
            print(f"❌ Reputation record not created")
            return False
        
        print(f"✅ Reputation record initialized:")
        print(f"   Level: {reputation.reputation_level}")
        print(f"   Completed Transactions: {reputation.completed_transactions}")
        print(f"   Average Rating: {reputation.average_rating or 'N/A'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("LAB 9 EXTENSION: Multi-Actor Registration Tests")
    print("="*60)
    
    # Cleanup first
    cleanup_test_data()
    
    # Test 1: Exporter registration
    exporter_reg_id = test_exporter_registration()
    if not exporter_reg_id:
        print("\n❌ Exporter registration test failed")
        return
    
    # Test 2: Buyer registration
    buyer_reg_id = test_buyer_registration()
    if not buyer_reg_id:
        print("\n❌ Buyer registration test failed")
        return
    
    print("\n" + "="*60)
    print("MANUAL APPROVAL STEP")
    print("="*60)
    print("\nℹ️  To complete the tests, approve these registrations:")
    print(f"\n1. Visit: http://localhost:8000/admin/registrations")
    print(f"2. Approve REG-{exporter_reg_id:04d} (Exporter)")
    print(f"3. Approve REG-{buyer_reg_id:04d} (Buyer)")
    print(f"\nAfter approving, run this script again with --verify flag:")
    print(f"   python test_multi_actor_registration.py --verify {exporter_reg_id} {buyer_reg_id}")
    
    # If verify flag is passed, verify the results
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        if len(sys.argv) < 4:
            print("\n❌ Please provide both registration IDs to verify")
            print("   Usage: python test_multi_actor_registration.py --verify <exporter_id> <buyer_id>")
            return
        
        exporter_id = int(sys.argv[2])
        buyer_id = int(sys.argv[3])
        
        print("\n" + "="*60)
        print("VERIFICATION PHASE")
        print("="*60)
        
        # Verify exporter approval
        print("\n--- Exporter Approval Verification ---")
        exporter_ok = verify_approval_results(exporter_id, 'EXPORTER')
        
        # Verify buyer approval
        print("\n--- Buyer Approval Verification ---")
        buyer_ok = verify_approval_results(buyer_id, 'BUYER')
        
        # Final result
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        
        if exporter_ok and buyer_ok:
            print("\n✅ ALL TESTS PASSED!")
            print("\nSuccessfully verified:")
            print("  ✓ Exporter registration → Organization → Exporter record → User → Reputation")
            print("  ✓ Buyer registration → Organization → Buyer record → User → Reputation")
            print("  ✓ Role-specific fields captured and stored")
            print("  ✓ DIDs generated for all entities")
        else:
            print("\n❌ SOME TESTS FAILED")
            if not exporter_ok:
                print("  ✗ Exporter approval verification failed")
            if not buyer_ok:
                print("  ✗ Buyer approval verification failed")


if __name__ == "__main__":
    main()
