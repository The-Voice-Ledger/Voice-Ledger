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


def test_gs1_identifiers():
    """Test GS1 identifier generation"""
    # Test GLN - 13 digits
    gln_value = gln("001")
    assert len(gln_value) >= 13  # May have padding
    assert gln_value.startswith("0614141")
    
    # Test GTIN - 14 digits
    gtin_value = gtin("002")
    assert len(gtin_value) >= 13  # May have padding
    assert gtin_value.startswith("0614141")
    
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
    batch_id = "BATCH-TEST-003"
    event_hash = "a" * 64  # Dummy hash
    
    # Record anchor
    record_anchor(
        batch_id=batch_id,
        event_hash=event_hash,
        event_type="commissioning",
        tx_hash="0xtest123"
    )
    
    # Record token
    record_token(
        batch_id=batch_id,
        token_id=99,
        quantity=75,
        metadata={"origin": "Ethiopia", "cooperative": "Test"}
    )
    
    # Record settlement
    record_settlement(
        batch_id=batch_id,
        amount=5000000,
        recipient="0xTestRecipient"
    )
    
    # Verify twin exists
    twin = get_batch_twin(batch_id)
    assert twin is not None
    assert twin["batchId"] == batch_id
    assert twin["tokenId"] == 99
    assert twin["quantity"] == 75
    assert len(twin["anchors"]) >= 1
    assert twin["settlement"]["amount"] == 5000000


def test_digital_twin_persistence():
    """Test that digital twin data persists across operations"""
    batch_id = "BATCH-TEST-004"
    
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
    assert len(twin_2["anchors"]) >= 1
    assert twin_2["tokenId"] == 100


def test_complete_anchor_flow():
    """Test complete flow from event creation to twin recording"""
    batch_id = "BATCH-TEST-005"
    
    # Step 1: Create EPCIS event
    event_file = create_commission_event(batch_id)
    assert event_file.exists()
    
    # Step 2: Hash event
    event_hash = hash_event(event_file)
    assert len(event_hash) == 64
    
    # Step 3: Record in digital twin
    record_anchor(
        batch_id=batch_id,
        event_hash=event_hash,
        event_type="commissioning"
    )
    
    # Step 4: Verify
    twin = get_batch_twin(batch_id)
    assert twin is not None
    
    # Find our anchor
    anchor = next(
        (a for a in twin["anchors"] if a["eventHash"] == event_hash),
        None
    )
    assert anchor is not None
    assert anchor["eventType"] == "commissioning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
