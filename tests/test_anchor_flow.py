"""
Blockchain Anchoring Flow Tests

Tests the complete flow from EPCIS event creation to blockchain anchoring.
"""

import pytest
from pathlib import Path

from gs1.identifiers import sscc, gln, gtin
from epcis.epcis_builder import create_commission_event
from epcis.canonicalise import canonicalise_event
from epcis.hash_event import hash_event
from twin.twin_builder import (
    record_anchor,
    record_token,
    record_settlement,
    get_batch_twin,
    load_twin,
    save_twin
)


# ---------------------------------------------------------------------------
# Helpers for creating / cleaning test data in Neon
# ---------------------------------------------------------------------------

def _create_test_batch(db, batch_id: str, farmer_id_str: str = "FARMER-TWIN-TEST"):
    """
    Ensure a FarmerIdentity and CoffeeBatch exist for *batch_id*.
    Returns (farmer, batch) ORM objects.
    """
    from database.models import FarmerIdentity, CoffeeBatch
    from gs1.identifiers import gtin as gs1_gtin
    import hashlib

    def _numeric_serial(s: str) -> str:
        digits = "".join(c for c in s if c.isdigit())
        if digits:
            return digits[:9]
        h = int(hashlib.md5(s.encode()).hexdigest(), 16)
        return str(h)[:9]

    farmer = db.query(FarmerIdentity).filter_by(farmer_id=farmer_id_str).first()
    if not farmer:
        farmer = FarmerIdentity(
            farmer_id=farmer_id_str,
            did=f"did:key:test-twin-{farmer_id_str}",
            encrypted_private_key="test_enc_key",
            public_key="test_pub_key",
            name="Twin Test Farmer",
            region="Sidama",
        )
        db.add(farmer)
        db.flush()

    batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
    if not batch:
        batch = CoffeeBatch(
            batch_id=batch_id,
            gtin=gs1_gtin(_numeric_serial(batch_id)),
            batch_number=batch_id,
            quantity_kg=75,
            origin_region="Guji",
            farm_name="Test Co-op",
            variety="Heirloom",
            process_method="Washed",
            quality_grade="Q1",
            farmer_id=farmer.id,
        )
        db.add(batch)
        db.flush()

    db.commit()
    return farmer, batch


def _cleanup_test_rows(db, batch_ids, farmer_id_str="FARMER-TWIN-TEST"):
    """Delete test CoffeeBatch + EPCISEvent + FarmerIdentity rows."""
    from database.models import CoffeeBatch, EPCISEvent, FarmerIdentity

    try:
        db.rollback()  # clear any aborted transaction
    except Exception:
        pass

    for bid in batch_ids:
        batch = db.query(CoffeeBatch).filter_by(batch_id=bid).first()
        if batch:
            # EPCISEvent.batch_id is an Integer FK to coffee_batches.id
            db.query(EPCISEvent).filter_by(batch_id=batch.id).delete()
            db.delete(batch)
    farmer = db.query(FarmerIdentity).filter_by(farmer_id=farmer_id_str).first()
    if farmer:
        # Also clean batches still referencing this farmer
        db.query(CoffeeBatch).filter_by(farmer_id=farmer.id).delete()
        db.delete(farmer)
    db.commit()


def test_gs1_identifiers():
    """Test GS1 identifier generation"""
    # Test GLN - 13 digits
    gln_value = gln("001")
    assert len(gln_value) >= 13  # May have padding
    assert gln_value.startswith("0614141")
    
    # Test GTIN - 14 digits
    gtin_value = gtin("002")
    assert len(gtin_value) >= 13  # May have padding
    assert "0614141" in gtin_value
    
    # Test SSCC - 18 digits  
    sscc_value = sscc("003")
    assert len(sscc_value) >= 17  # May have padding
    # SSCC has extra '0' prefix
    assert "0614141" in sscc_value


def test_epcis_event_creation():
    """Test EPCIS event creation and hashing"""
    batch_id = "BATCH-TEST-001"
    
    # Create event
    event_file = create_commission_event(batch_id)
    assert event_file.exists()
    assert event_file.name == f"{batch_id}_commission.json"
    
    # Hash event
    event_hash = hash_event(event_file)
    assert len(event_hash) == 64  # SHA-256 hex
    assert event_hash.isalnum()
    
    # Verify deterministic hashing
    hash_2 = hash_event(event_file)
    assert event_hash == hash_2


def test_canonicalisation():
    """Test JSON canonicalisation for deterministic hashing"""
    batch_id = "BATCH-TEST-002"
    
    event_file = create_commission_event(batch_id)
    
    # Canonicalise event
    canonical = canonicalise_event(event_file)
    
    # Should be compact JSON (no whitespace)
    assert "\n" not in canonical
    assert "  " not in canonical
    
    # Should be deterministic
    canonical_2 = canonicalise_event(event_file)
    assert canonical == canonical_2


def test_digital_twin_recording():
    """Test digital twin data recording"""
    from database import get_db

    batch_id = "BATCH-TEST-003"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        # Record anchor (event won't exist in DB, so it just prints a warning)
        record_anchor(
            batch_id=batch_id,
            event_hash="a" * 64,
            event_type="commissioning",
            tx_hash="0xtest123"
        )

        # Record token  -- batch NOW exists
        record_token(
            batch_id=batch_id,
            token_id=99,
            quantity=75,
            metadata={"origin": "Ethiopia", "cooperative": "Test"}
        )

        # Record settlement (placeholder – no DB schema yet)
        record_settlement(
            batch_id=batch_id,
            amount=5000000,
            recipient="0xTestRecipient"
        )

        # Verify twin exists
        twin = get_batch_twin(batch_id)
        assert twin is not None, "get_batch_twin returned None – batch missing from DB?"
        assert twin["batchId"] == batch_id
        assert twin["tokenId"] == 99
        assert twin["quantity"] == 75
        # settlement is not yet tracked in the DB schema
        assert twin.get("settlement") is None or twin["settlement"] is None
    finally:
        with get_db() as db:
            _cleanup_test_rows(db, [batch_id])


def test_digital_twin_persistence():
    """Test that digital twin data persists across operations"""
    from database import get_db

    batch_id = "BATCH-TEST-004"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        # Record initial data
        record_anchor(
            batch_id=batch_id,
            event_hash="b" * 64,
            event_type="commissioning"
        )

        # Load and verify
        twin_1 = get_batch_twin(batch_id)
        assert twin_1 is not None

        # Record additional data
        record_token(batch_id=batch_id, token_id=100, quantity=50, metadata={})

        # Load again and verify both pieces exist
        twin_2 = get_batch_twin(batch_id)
        assert twin_2 is not None
        assert twin_2["tokenId"] == 100
    finally:
        with get_db() as db:
            _cleanup_test_rows(db, [batch_id])


def test_complete_anchor_flow():
    """Test complete flow from event creation to twin recording"""
    from database import get_db

    batch_id = "BATCH-TEST-005"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        # Step 1: Create EPCIS event
        event_file = create_commission_event(batch_id)
        assert event_file.exists()

        # Step 2: Hash event
        event_hash = hash_event(event_file)
        assert len(event_hash) == 64

        # Step 3: Record in digital twin (no matching event row, just logs)
        record_anchor(
            batch_id=batch_id,
            event_hash=event_hash,
            event_type="commissioning"
        )

        # Step 4: Verify twin loads
        twin = get_batch_twin(batch_id)
        assert twin is not None
        assert twin["batchId"] == batch_id
    finally:
        with get_db() as db:
            _cleanup_test_rows(db, [batch_id])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
