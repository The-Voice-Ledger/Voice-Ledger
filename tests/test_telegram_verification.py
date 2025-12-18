"""
Tests for Telegram-based authenticated verification workflow.

Tests the verification handler without requiring actual Telegram bot.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import CoffeeBatch, UserIdentity, Organization
from database.connection import SessionLocal
from voice.telegram.verification_handler import (
    handle_verify_deeplink,
    handle_verification_callback,
    handle_quantity_message,
    verification_sessions,
    _process_verification
)


class TestVerificationDeeplink:
    """Test verification deep link handling."""
    
    def setup_method(self):
        """Setup test data before each test."""
        self.db = SessionLocal()
        
        # Create test organization
        self.org = Organization(
            name="Test Cooperative",
            organization_type="COOPERATIVE",
            country="ET"
        )
        self.db.add(self.org)
        self.db.flush()
        
        # Create test cooperative manager
        self.manager = UserIdentity(
            telegram_user_id="123456",
            telegram_username="test_manager",
            telegram_first_name="Test",
            role="COOPERATIVE_MANAGER",
            did="did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            is_approved=True,
            organization_id=self.org.id
        )
        self.db.add(self.manager)
        self.db.flush()
        
        # Create test farmer
        self.farmer = UserIdentity(
            telegram_user_id="789012",
            telegram_username="test_farmer",
            telegram_first_name="Farmer",
            role="FARMER",
            did="did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
            is_approved=True
        )
        self.db.add(self.farmer)
        self.db.flush()
        
        # Create test batch
        self.batch = CoffeeBatch(
            batch_id="TEST_BATCH_001",
            gtin="00123456789012",
            batch_number="001",
            quantity_kg=50.0,
            variety="Yirgacheffe",
            origin="Gedeo",
            status="PENDING_VERIFICATION",
            verification_token="VRF-TEST1234-ABCD5678",
            verification_expires_at=datetime.utcnow() + timedelta(hours=48),
            verification_used=False,
            farmer_id=self.farmer.id,
            created_by_user_id=self.farmer.id
        )
        self.db.add(self.batch)
        self.db.commit()
        
    def teardown_method(self):
        """Cleanup after each test."""
        # Clean up test data
        self.db.query(CoffeeBatch).filter_by(batch_id="TEST_BATCH_001").delete()
        self.db.query(UserIdentity).filter_by(telegram_user_id="123456").delete()
        self.db.query(UserIdentity).filter_by(telegram_user_id="789012").delete()
        self.db.query(Organization).filter_by(name="Test Cooperative").delete()
        self.db.commit()
        self.db.close()
        
        # Clear verification sessions
        verification_sessions.clear()
    
    @pytest.mark.asyncio
    async def test_valid_verification_deeplink(self):
        """Test valid verification deep link shows verification form."""
        response = await handle_verify_deeplink(
            user_id=123456,
            username="test_manager",
            token="VRF-TEST1234-ABCD5678"
        )
        
        # Should return verification form
        assert 'message' in response
        assert 'Batch Verification Request' in response['message']
        assert 'TEST_BATCH_001' in response['message']
        assert '50.0 kg' in response['message']
        assert 'inline_keyboard' in response
        
        # Should have created session
        assert 123456 in verification_sessions
        session = verification_sessions[123456]
        assert session['token'] == "VRF-TEST1234-ABCD5678"
        assert session['user_did'] == self.manager.did
        assert session['organization_id'] == self.org.id
        
    @pytest.mark.asyncio
    async def test_unregistered_user_cannot_verify(self):
        """Test unregistered user gets authentication error."""
        response = await handle_verify_deeplink(
            user_id=999999,  # Non-existent user
            username="unknown",
            token="VRF-TEST1234-ABCD5678"
        )
        
        assert 'Authentication Required' in response['message']
        assert 999999 not in verification_sessions
        
    @pytest.mark.asyncio
    async def test_unapproved_user_cannot_verify(self):
        """Test unapproved user cannot verify."""
        # Create unapproved user
        unapproved = UserIdentity(
            telegram_user_id="555555",
            role="COOPERATIVE_MANAGER",
            is_approved=False
        )
        self.db.add(unapproved)
        self.db.commit()
        
        response = await handle_verify_deeplink(
            user_id=555555,
            username="unapproved",
            token="VRF-TEST1234-ABCD5678"
        )
        
        assert 'Pending Approval' in response['message']
        assert 555555 not in verification_sessions
        
        # Cleanup
        self.db.query(UserIdentity).filter_by(telegram_user_id="555555").delete()
        self.db.commit()
        
    @pytest.mark.asyncio
    async def test_farmer_cannot_verify_own_batch(self):
        """Test farmer role cannot verify batches."""
        response = await handle_verify_deeplink(
            user_id=789012,  # Farmer user
            username="test_farmer",
            token="VRF-TEST1234-ABCD5678"
        )
        
        assert 'Insufficient Permissions' in response['message']
        assert 'FARMER' in response['message']
        assert 789012 not in verification_sessions
        
    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        """Test invalid token returns error."""
        response = await handle_verify_deeplink(
            user_id=123456,
            username="test_manager",
            token="VRF-INVALID-TOKEN"
        )
        
        assert 'Invalid Token' in response['message']
        assert 123456 not in verification_sessions
        
    @pytest.mark.asyncio
    async def test_already_verified_batch_rejected(self):
        """Test already verified batch shows already verified message."""
        # Mark batch as verified
        self.batch.verification_used = True
        self.batch.verified_at = datetime.utcnow()
        self.batch.verified_quantity = 50.0
        self.db.commit()
        
        response = await handle_verify_deeplink(
            user_id=123456,
            username="test_manager",
            token="VRF-TEST1234-ABCD5678"
        )
        
        assert 'Already Verified' in response['message']
        assert '50.0 kg' in response['message']
        
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self):
        """Test expired token returns error."""
        # Expire the token
        self.batch.verification_expires_at = datetime.utcnow() - timedelta(hours=1)
        self.db.commit()
        
        response = await handle_verify_deeplink(
            user_id=123456,
            username="test_manager",
            token="VRF-TEST1234-ABCD5678"
        )
        
        assert 'Token Expired' in response['message']


class TestVerificationCallbacks:
    """Test verification callback handling."""
    
    def setup_method(self):
        """Setup test data."""
        self.db = SessionLocal()
        
        # Create test data (similar to above)
        self.org = Organization(
            name="Test Cooperative",
            organization_type="COOPERATIVE",
            country="ET"
        )
        self.db.add(self.org)
        self.db.flush()
        
        self.manager = UserIdentity(
            telegram_user_id="123456",
            role="COOPERATIVE_MANAGER",
            did="did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            is_approved=True,
            organization_id=self.org.id
        )
        self.db.add(self.manager)
        self.db.flush()
        
        self.batch = CoffeeBatch(
            batch_id="TEST_BATCH_002",
            gtin="00123456789013",
            batch_number="002",
            quantity_kg=75.0,
            variety="Sidama",
            origin="Bensa",
            status="PENDING_VERIFICATION",
            verification_token="VRF-TEST5678-EFGH9012",
            verification_expires_at=datetime.utcnow() + timedelta(hours=48),
            verification_used=False
        )
        self.db.add(self.batch)
        self.db.commit()
        
        # Create verification session
        verification_sessions[123456] = {
            'token': 'VRF-TEST5678-EFGH9012',
            'batch_id': self.batch.id,
            'user_did': self.manager.did,
            'user_role': self.manager.role,
            'organization_id': self.org.id,
            'started_at': datetime.utcnow()
        }
        
    def teardown_method(self):
        """Cleanup."""
        self.db.query(CoffeeBatch).filter_by(batch_id="TEST_BATCH_002").delete()
        self.db.query(UserIdentity).filter_by(telegram_user_id="123456").delete()
        self.db.query(Organization).filter_by(name="Test Cooperative").delete()
        self.db.commit()
        self.db.close()
        verification_sessions.clear()
        
    @pytest.mark.asyncio
    async def test_verify_full_amount(self):
        """Test verifying with full claimed amount."""
        response = await handle_verification_callback(
            user_id=123456,
            callback_data="verify_full_VRF-TEST5678-EFGH9012"
        )
        
        # Should show success
        assert 'Verification Complete' in response['message']
        assert '75.0 kg' in response['message']
        
        # Refresh batch from database
        self.db.refresh(self.batch)
        
        # Check batch was updated
        assert self.batch.status == "VERIFIED"
        assert self.batch.verified_quantity == 75.0
        assert self.batch.verification_used == True
        assert self.batch.verified_by_did == self.manager.did
        assert self.batch.verifying_organization_id == self.org.id
        
        # Session should be cleaned up
        assert 123456 not in verification_sessions
        
    @pytest.mark.asyncio
    async def test_verify_custom_quantity(self):
        """Test requesting custom quantity input."""
        response = await handle_verification_callback(
            user_id=123456,
            callback_data="verify_custom_VRF-TEST5678-EFGH9012"
        )
        
        # Should request quantity input
        assert 'Enter Actual Quantity' in response['message']
        assert '75.0 kg' in response['message']  # Shows claimed amount
        
        # Session should be updated with awaiting flag
        session = verification_sessions[123456]
        assert session['awaiting_quantity'] == True
        
    @pytest.mark.asyncio
    async def test_verify_reject(self):
        """Test rejecting a batch."""
        response = await handle_verification_callback(
            user_id=123456,
            callback_data="verify_reject_VRF-TEST5678-EFGH9012"
        )
        
        # Should show rejection confirmation
        assert 'Batch Rejected' in response['message']
        assert 'REJECTED' in response['message']
        
        # Refresh batch
        self.db.refresh(self.batch)
        
        # Check batch was rejected
        assert self.batch.status == "REJECTED"
        assert self.batch.verification_used == True
        assert self.batch.verified_by_did == self.manager.did
        
    @pytest.mark.asyncio
    async def test_expired_session_rejected(self):
        """Test expired session returns error."""
        # Clear session
        verification_sessions.pop(123456, None)
        
        response = await handle_verification_callback(
            user_id=123456,
            callback_data="verify_full_VRF-TEST5678-EFGH9012"
        )
        
        assert 'Session Expired' in response['message']


class TestQuantityInput:
    """Test custom quantity input handling."""
    
    def setup_method(self):
        """Setup test data."""
        self.db = SessionLocal()
        
        self.batch = CoffeeBatch(
            batch_id="TEST_BATCH_003",
            gtin="00123456789014",
            batch_number="003",
            quantity_kg=100.0,
            variety="Harar",
            origin="Harar",
            status="PENDING_VERIFICATION",
            verification_token="VRF-TEST9012-IJKL3456",
            verification_expires_at=datetime.utcnow() + timedelta(hours=48),
            verification_used=False
        )
        self.db.add(self.batch)
        self.db.commit()
        
        # Create session awaiting quantity
        verification_sessions[123456] = {
            'token': 'VRF-TEST9012-IJKL3456',
            'batch_id': self.batch.id,
            'user_did': 'did:key:z6Mk...',
            'awaiting_quantity': True
        }
        
    def teardown_method(self):
        """Cleanup."""
        self.db.query(CoffeeBatch).filter_by(batch_id="TEST_BATCH_003").delete()
        self.db.commit()
        self.db.close()
        verification_sessions.clear()
        
    @pytest.mark.asyncio
    async def test_valid_quantity_input(self):
        """Test valid quantity input shows confirmation."""
        response = await handle_quantity_message(
            user_id=123456,
            text="95.5"
        )
        
        # Should show confirmation with difference
        assert 'Confirm Verification' in response['message']
        assert '95.5 kg' in response['message']
        assert '-4.5 kg' in response['message']  # Difference
        assert 'inline_keyboard' in response
        
        # Session should store quantity
        session = verification_sessions[123456]
        assert session['custom_quantity'] == 95.5
        assert session['awaiting_confirmation'] == True
        assert 'awaiting_quantity' not in session
        
    @pytest.mark.asyncio
    async def test_invalid_quantity_rejected(self):
        """Test invalid quantity returns error."""
        response = await handle_quantity_message(
            user_id=123456,
            text="not_a_number"
        )
        
        assert 'Invalid Quantity' in response['message']
        
        # Session should still be awaiting quantity
        session = verification_sessions[123456]
        assert session['awaiting_quantity'] == True
        assert 'custom_quantity' not in session
        
    @pytest.mark.asyncio
    async def test_negative_quantity_rejected(self):
        """Test negative quantity rejected."""
        response = await handle_quantity_message(
            user_id=123456,
            text="-50"
        )
        
        assert 'Invalid Quantity' in response['message']
        
    @pytest.mark.asyncio
    async def test_no_session_returns_none(self):
        """Test message without session returns None."""
        response = await handle_quantity_message(
            user_id=999999,  # No session
            text="50"
        )
        
        assert response is None


def test_did_automatic_attachment():
    """
    Test that DID is automatically attached from session, not user input.
    
    This is the KEY security feature - verifier never enters their DID.
    """
    db = SessionLocal()
    
    try:
        # Create minimal test data
        batch = CoffeeBatch(
            batch_id="DID_TEST_BATCH",
            gtin="00999999999999",
            batch_number="DID001",
            quantity_kg=50.0,
            status="PENDING_VERIFICATION",
            verification_token="VRF-DID-TEST",
            verification_used=False
        )
        db.add(batch)
        db.commit()
        
        # Create session with DID (no organization to avoid FK constraint)
        manager_did = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
        session = {
            'user_did': manager_did,
            'organization_id': None  # ← Set to None to avoid FK constraint
        }
        
        # Process verification (synchronous version for testing)
        import asyncio
        asyncio.run(_process_verification(
            db=db,
            batch=batch,
            user_id=123456,
            session=session,
            verified_quantity=50.0,
            notes="Test verification"
        ))
        
        # Verify DID was attached from session
        db.refresh(batch)
        assert batch.verified_by_did == manager_did, "DID should be from session, not user input!"
        assert batch.status == "VERIFIED"
        assert batch.verification_used == True
        
        print("✅ DID automatically attached from authenticated session!")
        print(f"   Verified By DID: {batch.verified_by_did}")
        print(f"   Status: {batch.status}")
        print(f"   Verified Quantity: {batch.verified_quantity} kg")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Test failed: {e}")
        raise
    finally:
        db.rollback()  # Rollback first to clear any pending state
        db.query(CoffeeBatch).filter_by(batch_id="DID_TEST_BATCH").delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    print("Running Telegram Verification Tests...\n")
    
    # Run DID attachment test (synchronous)
    print("Test 1: DID Automatic Attachment")
    test_did_automatic_attachment()
    
    print("\n" + "="*60)
    print("✅ All synchronous tests passed!")
    print("\nTo run async tests, use: pytest tests/test_telegram_verification.py")
    print("="*60)
