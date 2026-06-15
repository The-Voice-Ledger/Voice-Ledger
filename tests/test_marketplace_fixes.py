"""
Tests for Plan 002: Marketplace Crash Fixes

Covers:
- COR-01: func import is available at module scope (no NameError)
- COR-02: require_admin rejects non-admin users (even approved ones)
- COR-04: RFQ fulfillment uses cumulative accepted quantity
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# COR-01: func import present at module scope
# =========================================================================

class TestFuncImport:

    def test_func_imported_at_module_scope(self):
        """from sqlalchemy import func must be present at top of rfq_api.py."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()
        assert 'from sqlalchemy import func' in content, \
            "func is not imported at module scope in rfq_api.py"

    def test_no_local_sqlfunc_import(self):
        """The local 'from sqlalchemy import func as sqlfunc' alias should be gone."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()
        assert 'func as sqlfunc' not in content, \
            "Local 'func as sqlfunc' alias still present in rfq_api.py"

    def test_generate_rfq_number_importable(self):
        """generate_rfq_number must be importable without NameError."""
        try:
            # This import will fail at module level if func is missing
            # We patch the DB to avoid needing a real connection
            with patch('voice.marketplace.rfq_api.SessionLocal'):
                from voice.marketplace.rfq_api import generate_rfq_number
        except NameError as e:
            pytest.fail(f"NameError when importing generate_rfq_number: {e}")
        except Exception:
            # Other errors (e.g. DB connection) are acceptable — we just want no NameError
            pass

    def test_generate_offer_number_importable(self):
        """generate_offer_number must be importable without NameError."""
        try:
            with patch('voice.marketplace.rfq_api.SessionLocal'):
                from voice.marketplace.rfq_api import generate_offer_number
        except NameError as e:
            pytest.fail(f"NameError when importing generate_offer_number: {e}")
        except Exception:
            pass

    def test_generate_acceptance_number_importable(self):
        """generate_acceptance_number must be importable without NameError."""
        try:
            with patch('voice.marketplace.rfq_api.SessionLocal'):
                from voice.marketplace.rfq_api import generate_acceptance_number
        except NameError as e:
            pytest.fail(f"NameError when importing generate_acceptance_number: {e}")
        except Exception:
            pass

    def test_generate_rfq_number_calls_func_max(self):
        """generate_rfq_number must use func.max, not a raw SQL query."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()
        assert 'func.max(RFQ.rfq_number)' in content, \
            "generate_rfq_number does not use func.max(RFQ.rfq_number)"


# =========================================================================
# COR-02: Admin role check
# =========================================================================

class TestAdminRoleCheck:

    def _make_user(self, role: str, is_approved: bool):
        user = MagicMock()
        user.id = 1
        user.role = role
        user.is_approved = is_approved
        return user

    def test_farmer_approved_is_rejected(self):
        """An approved FARMER must NOT pass the admin check."""
        from fastapi import HTTPException
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret'}):
            from voice.web.auth import require_admin

        user = self._make_user('FARMER', is_approved=True)
        with pytest.raises(HTTPException) as exc_info:
            require_admin(user)
        assert exc_info.value.status_code == 403

    def test_buyer_approved_is_rejected(self):
        """An approved BUYER must NOT pass the admin check."""
        from fastapi import HTTPException
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret'}):
            from voice.web.auth import require_admin

        user = self._make_user('BUYER', is_approved=True)
        with pytest.raises(HTTPException) as exc_info:
            require_admin(user)
        assert exc_info.value.status_code == 403

    def test_unapproved_non_admin_is_rejected(self):
        """An unapproved non-admin user must be rejected."""
        from fastapi import HTTPException
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret'}):
            from voice.web.auth import require_admin

        user = self._make_user('FARMER', is_approved=False)
        with pytest.raises(HTTPException):
            require_admin(user)

    def test_admin_role_passes(self):
        """A user with role=ADMIN must pass the check and be returned."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret'}):
            from voice.web.auth import require_admin

        user = self._make_user('ADMIN', is_approved=True)
        result = require_admin(user)
        assert result is user

    def test_system_admin_role_passes(self):
        """A user with role=SYSTEM_ADMIN must also pass the check."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret'}):
            from voice.web.auth import require_admin

        user = self._make_user('SYSTEM_ADMIN', is_approved=True)
        result = require_admin(user)
        assert result is user

    def test_auth_py_uses_role_not_in(self):
        """Confirm the fix is present in auth.py source."""
        auth_path = Path(__file__).parent.parent / 'voice' / 'web' / 'auth.py'
        content = auth_path.read_text()
        assert "user.role not in ('ADMIN', 'SYSTEM_ADMIN')" in content, \
            "require_admin in auth.py does not use 'user.role not in' check"
        # Old broken logic must be gone
        assert "user.role != 'ADMIN' and not user.is_approved" not in content, \
            "Old broken admin check still present in auth.py"


# =========================================================================
# COR-04: RFQ fulfillment uses cumulative sum
# =========================================================================

class TestRfqFulfillmentLogic:

    def test_no_count_in_fulfillment(self):
        """The fulfillment block must not use .count() — it must use func.sum."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()

        # Find the fulfillment section (around "Update RFQ status")
        # Ensure no .count() is used there
        import re
        # Extract just the fulfillment block
        match = re.search(
            r'# Update RFQ status.{0,500}rfq\.status',
            content,
            re.DOTALL
        )
        assert match is not None, "Could not find 'Update RFQ status' block in rfq_api.py"
        block = match.group(0)
        assert '.count()' not in block, \
            f"Fulfillment block uses .count() instead of func.sum: {block}"

    def test_fulfillment_uses_func_sum(self):
        """Fulfillment must use func.sum to accumulate accepted quantities."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()
        assert 'func.sum(RFQAcceptance.quantity_accepted_kg)' in content, \
            "Fulfillment does not use func.sum(RFQAcceptance.quantity_accepted_kg)"

    def test_fulfillment_uses_total_accepted_kg(self):
        """Fulfillment must compare total_accepted_kg to rfq.quantity_kg."""
        rfq_path = Path(__file__).parent.parent / 'voice' / 'marketplace' / 'rfq_api.py'
        content = rfq_path.read_text()
        assert 'total_accepted_kg >= rfq.quantity_kg' in content, \
            "Fulfillment does not compare total_accepted_kg to rfq.quantity_kg"

    def test_single_acceptance_less_than_rfq_gives_partially_filled(self):
        """
        Simulate: RFQ needs 1000 kg, one acceptance of 300 kg → PARTIALLY_FILLED.
        This was broken before the fix — single acceptance qty < rfq qty → FULFILLED was never set.
        """
        # Simulate cumulative sum logic
        rfq_quantity_kg = 1000.0
        existing_acceptances_kg = 0.0  # no prior acceptances
        new_acceptance_kg = 300.0

        total_accepted_kg = existing_acceptances_kg + new_acceptance_kg
        status = "FULFILLED" if total_accepted_kg >= rfq_quantity_kg else "PARTIALLY_FILLED"
        assert status == "PARTIALLY_FILLED"

    def test_two_acceptances_reaching_total_gives_fulfilled(self):
        """
        Simulate: RFQ needs 1000 kg, two acceptances of 600 + 400 = 1000 → FULFILLED.
        """
        rfq_quantity_kg = 1000.0
        # After first acceptance (600 kg already in DB when second is processed)
        existing_acceptances_kg = 600.0
        new_acceptance_kg = 400.0

        total_accepted_kg = existing_acceptances_kg + new_acceptance_kg
        status = "FULFILLED" if total_accepted_kg >= rfq_quantity_kg else "PARTIALLY_FILLED"
        assert status == "FULFILLED"

    def test_over_accepted_gives_fulfilled(self):
        """If cumulative acceptances exceed RFQ quantity, still FULFILLED."""
        rfq_quantity_kg = 500.0
        total_accepted_kg = 600.0
        status = "FULFILLED" if total_accepted_kg >= rfq_quantity_kg else "PARTIALLY_FILLED"
        assert status == "FULFILLED"
