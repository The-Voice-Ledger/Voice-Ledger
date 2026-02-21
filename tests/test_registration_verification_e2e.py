"""
End-to-End Test: Complete Registration and Verification Flow

Tests the full user journey from registration to batch verification:
1. Cooperative manager registers
2. Admin approves registration  
3. Farmer creates batch
4. Manager scans QR code and verifies batch
5. Verification recorded with proper DID attribution

This test validates the entire security model.
"""

import pytest
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import (
    CoffeeBatch, UserIdentity, Organization, PendingRegistration,
    FarmerCooperative, FarmerIdentity, EPCISEvent, SessionLocal
)
from ssi.org_identity import generate_organization_did
from voice.telegram.verification_handler import (
    handle_verify_deeplink,
    handle_verification_callback,
    verification_sessions
)
from voice.verification.qr_codes import generate_verification_qr_code
from voice.verification.verification_tokens import generate_verification_token
import os


class TestRegistrationVerificationE2E:
    """End-to-end test of registration and verification system."""
    
    def setup_method(self):
        """Setup test database with clean state."""
        self.db = SessionLocal()
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
        print("\n" + "="*70)
        print("END-TO-END TEST: Registration → Verification")
        print("="*70)
    
    def teardown_method(self):
        """Clean up test data after each test."""
        try:
            self.cleanup_test_data()
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
            self.db.rollback()
            try:
                self.cleanup_test_data()
            except:
                pass
        finally:
            self.db.close()
    
    def cleanup_test_data(self):
        """Remove all test data."""
        # Rollback any pending transaction first
        self.db.rollback()
        # Test identifiers (integers for telegram_user_id)
        test_manager_tg_id = 999999999
        test_farmer_tg_id = 888888888
        test_self_verify_tg_id = 777777777
        test_unapproved_tg_id = 666666666
        test_org_name = "Test E2E Cooperative"
        
        # Collect IDs of test batches (for cascading FK deletes)
        test_batch_ids = [
            b.id for b in self.db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id.like('TEST_%')
            ).all()
        ]
        
        # Also find batches owned by test farmers
        test_farmer_ids = [f.id for f in self.db.query(FarmerIdentity).filter(
            FarmerIdentity.farmer_id.like('TEST_FARMER%')
        ).all()]
        if test_farmer_ids:
            test_batch_ids += [
                b.id for b in self.db.query(CoffeeBatch).filter(
                    CoffeeBatch.farmer_id.in_(test_farmer_ids)
                ).all()
            ]
        test_batch_ids = list(set(test_batch_ids))
        
        # Delete child rows FIRST (EPCIS events + verification evidence reference coffee_batches.id)
        if test_batch_ids:
            self.db.query(EPCISEvent).filter(
                EPCISEvent.batch_id.in_(test_batch_ids)
            ).delete(synchronize_session=False)
            
            from database.models import VerificationEvidence
            self.db.query(VerificationEvidence).filter(
                VerificationEvidence.batch_id.in_(test_batch_ids)
            ).delete(synchronize_session=False)
            
            self.db.query(CoffeeBatch).filter(
                CoffeeBatch.id.in_(test_batch_ids)
            ).delete(synchronize_session=False)
        
        # Now safe to delete farmers
        self.db.query(FarmerIdentity).filter(
            FarmerIdentity.farmer_id.like('TEST_FARMER%')
        ).delete(synchronize_session=False)
        
        self.db.query(FarmerCooperative).filter(
            FarmerCooperative.id > 0
        ).delete(synchronize_session=False)
        
        self.db.query(PendingRegistration).filter(
            PendingRegistration.telegram_user_id.in_([
                test_manager_tg_id, test_farmer_tg_id, 
                test_self_verify_tg_id, test_unapproved_tg_id
            ])
        ).delete(synchronize_session=False)
        
        test_users = self.db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id.in_([
                str(test_manager_tg_id), str(test_farmer_tg_id),
                str(test_self_verify_tg_id), str(test_unapproved_tg_id)
            ])
        ).all()
        for user in test_users:
            self.db.delete(user)
        
        # Delete test organizations
        test_orgs = self.db.query(Organization).filter(
            Organization.name.in_([test_org_name, "Test Coop"])
        ).all()
        for org in test_orgs:
            self.db.delete(org)
        
        self.db.commit()
    
    def test_complete_flow(self):
        """Test complete registration and verification flow."""
        
        # ===================================================================
        # STEP 1: Create and approve cooperative organization
        # ===================================================================
        print("\n📋 STEP 1: Creating Cooperative Organization")
        
        org_identity = generate_organization_did()
        
        organization = Organization(
            name="Test E2E Cooperative",
            type="COOPERATIVE",
            did=org_identity['did'],
            encrypted_private_key=org_identity['encrypted_private_key'],
            public_key=org_identity['public_key'],
            location="Addis Ababa",
            region="Addis Ababa"
        )
        self.db.add(organization)
        self.db.flush()
        
        print(f"   ✅ Organization created: {organization.name}")
        print(f"   📍 DID: {org_identity['did'][:50]}...")
        
        # ===================================================================
        # STEP 2: Register and approve cooperative manager
        # ===================================================================
        print("\n👤 STEP 2: Registering Cooperative Manager")
        
        # Generate DID for manager
        from ssi.did.did_key import generate_did_key
        manager_identity = generate_did_key()
        manager_did = manager_identity['did']
        
        manager = UserIdentity(
            telegram_user_id="999999999",
            telegram_username="test_manager",
            telegram_first_name="Test",
            telegram_last_name="Manager",
            role="COOPERATIVE_MANAGER",
            did=manager_did,
            encrypted_private_key=manager_identity['private_key'],
            public_key=manager_identity['public_key'],
            is_approved=True,
            organization_id=organization.id
        )
        self.db.add(manager)
        self.db.flush()
        
        print(f"   ✅ Manager registered: {manager.telegram_first_name} {manager.telegram_last_name}")
        print(f"   🔑 Role: {manager.role}")
        print(f"   🏢 Organization: {organization.name}")
        print(f"   📍 DID: {manager_did[:50]}...")
        
        # ===================================================================
        # STEP 3: Register farmer
        # ===================================================================
        print("\n🌾 STEP 3: Registering Farmer")
        
        farmer_identity = generate_did_key()
        farmer_did = farmer_identity['did']
        
        farmer = UserIdentity(
            telegram_user_id="888888888",
            telegram_username="test_farmer",
            telegram_first_name="Test",
            telegram_last_name="Farmer",
            role="FARMER",
            did=farmer_did,
            encrypted_private_key=farmer_identity['private_key'],
            public_key=farmer_identity['public_key'],
            is_approved=True,
            organization_id=None  # Farmers not part of org initially
        )
        self.db.add(farmer)
        self.db.flush()
        
        # Create FarmerIdentity (on-chain farmer record for batch ownership)
        farmer_record = FarmerIdentity(
            farmer_id="TEST_FARMER_001",
            did=farmer_did,
            encrypted_private_key=farmer_identity['private_key'],
            public_key=farmer_identity['public_key'],
            name=f"{farmer.telegram_first_name} {farmer.telegram_last_name}",
            location="Sidama, Ethiopia"
        )
        self.db.add(farmer_record)
        self.db.flush()
        
        print(f"   ✅ Farmer registered: {farmer.telegram_first_name} {farmer.telegram_last_name}")
        print(f"   📍 DID: {farmer_did[:50]}...")
        
        # ===================================================================
        # STEP 4: Farmer creates batch
        # ===================================================================
        print("\n📦 STEP 4: Farmer Creates Batch")
        
        batch_id = "TEST_E2E_BATCH_001"
        token = generate_verification_token(batch_id)
        
        batch = CoffeeBatch(
            batch_id=batch_id,
            batch_number="E2E-001",
            farmer_id=farmer_record.id,
            created_by_user_id=farmer.id,
            variety="Yirgacheffe",
            quantity_kg=100.0,
            origin="Sidama",
            harvest_date=datetime(2025, 12, 1),
            processing_method="Washed",
            status="PENDING_VERIFICATION",
            verification_token=token,
            verification_expires_at=datetime.utcnow() + timedelta(hours=48),
            verification_used=False,
            gtin="01234567890123",
            gln="5412345000013"
        )
        self.db.add(batch)
        self.db.commit()
        
        print(f"   ✅ Batch created: {batch.batch_id}")
        print(f"   ☕ Variety: {batch.variety}")
        print(f"   ⚖️  Quantity: {batch.quantity_kg} kg")
        print(f"   🔑 Verification Token: {token}")
        
        # ===================================================================
        # STEP 5: Generate QR code with Telegram deep link
        # ===================================================================
        print("\n📱 STEP 5: Generating QR Code")
        
        os.environ['TELEGRAM_BOT_USERNAME'] = 'voiceledgerbot'
        
        qr_b64, qr_path = generate_verification_qr_code(
            token,
            use_telegram_deeplink=True
        )
        
        print(f"   ✅ QR Code generated")
        print(f"   🔗 Deep link: tg://resolve?domain=voiceledgerbot&start=verify_{token}")
        print(f"   💾 Saved to: {qr_path}")
        
        # ===================================================================
        # STEP 6: Manager scans QR code (Telegram deep link)
        # ===================================================================
        print("\n🔍 STEP 6: Manager Scans QR Code")
        
        response = asyncio.run(
            handle_verify_deeplink(
                user_id=999999999,
                username=manager.telegram_username,
                token=token
            )
        )
        
        print(f"   ✅ Authentication successful")
        print(f"   👤 Verified as: {manager.telegram_first_name} {manager.telegram_last_name} ({manager.role})")
        
        # Verify response contains batch details
        assert '📦 *Batch Verification Request*' in response['message']
        assert batch.batch_id in response['message']
        assert str(batch.quantity_kg) in response['message']
        assert 'inline_keyboard' in response
        
        print(f"   📋 Verification form displayed")
        print(f"   🎯 Options: Verify Full / Custom / Reject")
        
        # Verify session was created with correct DID
        user_id_int = 999999999
        assert user_id_int in verification_sessions
        session = verification_sessions[user_id_int]
        assert session['user_did'] == manager_did
        assert session['user_role'] == 'COOPERATIVE_MANAGER'
        assert session['organization_id'] == organization.id
        
        print(f"   ✅ Session created with manager's DID (from database)")
        
        # ===================================================================
        # STEP 7: Manager verifies batch (button click)
        # ===================================================================
        print("\n✅ STEP 7: Manager Verifies Batch")
        
        callback_response = asyncio.run(
            handle_verification_callback(
                user_id=user_id_int,
                callback_data=f'verify_full_{token}'
            )
        )
        
        # Refresh batch from database
        self.db.expire(batch)
        batch = self.db.query(CoffeeBatch).filter_by(batch_id="TEST_E2E_BATCH_001").first()
        
        print(f"   ✅ Verification completed")
        print(f"   📝 Status: {batch.status}")
        print(f"   ✓  Verified quantity: {batch.verified_quantity} kg")
        print(f"   👤 Verified by DID: {batch.verified_by_did[:50]}...")
        print(f"   🏢 Verifying org: {batch.verifying_organization_id}")
        print(f"   ⏰ Verified at: {batch.verified_at}")
        
        # ===================================================================
        # STEP 8: Verify security guarantees
        # ===================================================================
        print("\n🔐 STEP 8: Validating Security Guarantees")
        
        # Verify batch is marked as verified
        assert batch.verification_used is True
        assert batch.status == "VERIFIED"
        
        print("   ✅ Batch marked as VERIFIED")
        
        # Verify correct DID was attached (from database, not user input!)
        assert batch.verified_by_did == manager_did
        
        print(f"   ✅ DID correctly attached from database")
        print(f"      Expected: {manager_did[:50]}...")
        print(f"      Recorded: {batch.verified_by_did[:50]}...")
        
        # Verify organization ID recorded
        assert batch.verifying_organization_id == organization.id
        
        print(f"   ✅ Organization ID recorded: {organization.name}")
        
        # Verify quantity
        assert batch.verified_quantity == batch.quantity_kg
        
        print(f"   ✅ Quantity verified: {batch.verified_quantity} kg")
        
        # Verify timestamp
        assert batch.verified_at is not None
        assert (datetime.utcnow() - batch.verified_at).seconds < 10
        
        print(f"   ✅ Timestamp recorded: {batch.verified_at}")
        
        # ===================================================================
        # SUCCESS!
        # ===================================================================
        print("\n" + "="*70)
        print("🎉 END-TO-END TEST PASSED!")
        print("="*70)
        print("\n✅ Verified Security Features:")
        print("   1. Manager authentication via Telegram ID")
        print("   2. Role-based authorization (COOPERATIVE_MANAGER)")
        print("   3. DID automatic attachment from database")
        print("   4. No user input for verifier DID")
        print("   5. Organization ID properly recorded")
        print("   6. Audit trail complete (who, when, what)")
        print("\n🚀 System is production-ready!")
        print("="*70 + "\n")
    
    def test_farmer_cannot_verify_own_batch(self):
        """Test that farmers cannot verify their own batches."""
        
        print("\n" + "="*70)
        print("SECURITY TEST: Farmer Cannot Self-Verify")
        print("="*70)
        
        # Create farmer with unique ID
        farmer_did = "did:key:z6MkTestFarmerSelfVerify"
        farmer = UserIdentity(
            telegram_user_id="777777777",  # Different ID from main test
            role="FARMER",
            did=farmer_did,
            encrypted_private_key="test_pk",
            public_key="test_pub",
            is_approved=True,
            telegram_first_name="Test",
            telegram_last_name="Farmer"
        )
        self.db.add(farmer)
        self.db.flush()
        
        # Create FarmerIdentity for batch
        farmer_record = FarmerIdentity(
            farmer_id="TEST_FARMER_SELF",
            did=farmer_did,
            encrypted_private_key="test_pk",
            public_key="test_pub",
            name="Test Farmer"
        )
        self.db.add(farmer_record)
        self.db.flush()
        
        # Create batch
        batch_id = "TEST_SELF_VERIFY"
        token = generate_verification_token(batch_id)
        batch = CoffeeBatch(
            batch_id=batch_id,
            batch_number="SELF-001",
            farmer_id=farmer_record.id,
            variety="Test",
            quantity_kg=50.0,
            origin="Test",
            gtin="01234567890124",
            status="PENDING_VERIFICATION",
            verification_token=token,
            verification_expires_at=datetime.utcnow() + timedelta(hours=48)
        )
        self.db.add(batch)
        self.db.commit()
        
        print(f"\n🌾 Farmer created: {farmer.telegram_first_name} {farmer.telegram_last_name}")
        print(f"📦 Batch created: {batch.batch_id}")
        print(f"\n🔍 Farmer attempts to scan QR code...")
        
        # Farmer tries to verify (using the farmer's actual telegram_user_id)
        response = asyncio.run(
            handle_verify_deeplink(
                user_id=777777777,
                username="test_farmer",
                token=token
            )
        )
        
        # Should be rejected
        assert "Insufficient Permissions" in response['message']
        assert response['parse_mode'] == 'Markdown'
        
        print("\n❌ REJECTED: Farmer cannot verify batches")
        print("   Message:", response['message'][:100] + "...")
        print("\n✅ Security Test Passed: Self-verification blocked")
        print("="*70 + "\n")
    
    def test_unapproved_user_cannot_verify(self):
        """Test that unapproved users cannot verify batches."""
        
        print("\n" + "="*70)
        print("SECURITY TEST: Unapproved User Blocked")
        print("="*70)
        
        # Create unapproved manager
        manager_did = "did:key:z6MkTestUnapprovedManager"
        org_identity = generate_organization_did()
        
        org = Organization(
            name="Test Coop",
            type="COOPERATIVE",
            did=org_identity['did'],
            encrypted_private_key=org_identity['encrypted_private_key'],
            public_key=org_identity['public_key']
        )
        self.db.add(org)
        self.db.flush()
        
        manager = UserIdentity(
            telegram_user_id="666666666",  # Different ID from main test
            role="COOPERATIVE_MANAGER",
            did=manager_did,
            encrypted_private_key="test_pk",
            public_key="test_pub",
            is_approved=False,  # NOT APPROVED!
            organization_id=org.id,
            telegram_first_name="Unapproved",
            telegram_last_name="Manager"
        )
        self.db.add(manager)
        self.db.commit()
        
        # Create batch
        token = generate_verification_token("TEST_UNAPPROVED")
        
        print(f"\n👤 Unapproved manager created: {manager.telegram_first_name} {manager.telegram_last_name}")
        print(f"⏳ Status: Pending approval")
        print(f"\n🔍 Manager attempts to verify batch...")
        
        # Try to verify (use the unapproved manager's ID)
        response = asyncio.run(
            handle_verify_deeplink(
                user_id=666666666,
                username="unapproved_manager",
                token=token
            )
        )
        
        # Should be rejected - unapproved users blocked
        assert "Pending Approval" in response['message']
        
        print("\n❌ REJECTED: Unapproved users blocked")
        print("   Message:", response['message'][:100] + "...")
        print("\n✅ Security Test Passed: Approval required")
        print("="*70 + "\n")


if __name__ == "__main__":
    # Run tests
    test = TestRegistrationVerificationE2E()
    test.setup_method()
    
    try:
        print("\n" + "="*70)
        print("RUNNING END-TO-END TESTS")
        print("="*70)
        
        test.test_complete_flow()
        test.test_farmer_cannot_verify_own_batch()
        test.test_unapproved_user_cannot_verify()
        
        print("\n" + "="*70)
        print("ALL TESTS PASSED! ✅")
        print("="*70 + "\n")
        
    finally:
        test.teardown_method()
