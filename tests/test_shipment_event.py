"""
Unit tests for EPCIS 2.0 Shipment Event creation.

Tests the shipment_events.py module to ensure proper:
- GS1 identifier formatting (SGTIN, LGTIN, SGLN)
- EPCIS 2.0 ObjectEvent structure
- IPFS pinning integration
- Blockchain anchoring integration
- Database storage

Run with: python -m pytest tests/test_shipment_event.py -v
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import CoffeeBatch, EPCISEvent, User
from voice.epcis.shipment_events import create_shipment_event, get_batch_shipment_events


@pytest.fixture
def test_batch(db_session: Session):
    """Create a test batch for shipment testing."""
    # Create test user
    user = User(
        telegram_user_id=12345,
        username="test_farmer",
        did="did:key:z6MkTest123"
    )
    db_session.add(user)
    db_session.flush()
    
    # Create test batch
    batch = CoffeeBatch(
        batch_id="TEST-SHIP-001",
        gtin="06141418123450",
        gln="0614141000010",
        quantity_kg=500.0,
        origin="Yirgacheffe, Ethiopia",
        variety="Arabica Heirloom",
        status="PENDING_VERIFICATION",
        created_by_user_id=user.id
    )
    db_session.add(batch)
    db_session.commit()
    
    yield batch
    
    # Cleanup
    db_session.query(EPCISEvent).filter(EPCISEvent.batch_id == batch.id).delete()
    db_session.query(CoffeeBatch).filter(CoffeeBatch.id == batch.id).delete()
    db_session.query(User).filter(User.id == user.id).delete()
    db_session.commit()


def test_create_shipment_event_basic(db_session: Session, test_batch: CoffeeBatch):
    """Test basic shipment event creation."""
    result = create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln=test_batch.gln,
        destination_gln="0614141000027",
        quantity_kg=test_batch.quantity_kg,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    assert result is not None
    assert "event_hash" in result
    assert "ipfs_cid" in result
    assert "blockchain_tx_hash" in result
    assert "event" in result
    
    # Verify event structure
    event = result["event"]
    assert event["type"] == "ObjectEvent"
    assert event["action"] == "OBSERVE"
    assert event["bizStep"] == "urn:epcglobal:cbv:bizstep:shipping"
    assert event["disposition"] == "urn:epcglobal:cbv:disp:in_transit"
    
    # Verify GS1 identifiers
    assert f"urn:epc:id:sgtin:{test_batch.gtin[:13]}.{test_batch.gtin[13]}.{test_batch.batch_id}" in event["epcList"]
    
    # Verify quantity
    assert len(event["quantityList"]) == 1
    assert event["quantityList"][0]["quantity"] == test_batch.quantity_kg
    assert event["quantityList"][0]["uom"] == "KGM"
    
    # Verify source/destination
    assert len(event["sourceList"]) == 1
    assert event["sourceList"][0]["source"] == f"urn:epc:id:sgln:{test_batch.gln}.0"
    assert len(event["destinationList"]) == 1
    assert event["destinationList"][0]["destination"] == "urn:epc:id:sgln:0614141000027.0"


def test_shipment_event_with_carrier_info(db_session: Session, test_batch: CoffeeBatch):
    """Test shipment event with optional carrier and tracking info."""
    result = create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln=test_batch.gln,
        destination_gln="0614141000027",
        quantity_kg=test_batch.quantity_kg,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper",
        carrier="DHL Express",
        tracking_number="DHL123456789",
        expected_delivery_date="2025-12-25",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    assert result is not None
    event = result["event"]
    
    # Verify optional fields are included
    assert event.get("gdst:vesselName") == "DHL Express"
    assert event.get("gdst:vesselID") == "DHL123456789"
    assert event.get("gdst:expectedDeliveryDate") == "2025-12-25"


def test_shipment_event_stored_in_db(db_session: Session, test_batch: CoffeeBatch):
    """Test that shipment event is properly stored in database."""
    result = create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln=test_batch.gln,
        destination_gln="0614141000027",
        quantity_kg=test_batch.quantity_kg,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    # Query database
    event = db_session.query(EPCISEvent).filter(
        EPCISEvent.event_hash == result["event_hash"]
    ).first()
    
    assert event is not None
    assert event.event_type == "ObjectEvent"
    assert event.biz_step == "shipping"
    assert event.batch_id == test_batch.id
    assert event.ipfs_cid is not None  # Should have IPFS CID
    assert event.blockchain_tx_hash is not None  # Should have blockchain TX


def test_get_batch_shipment_events(db_session: Session, test_batch: CoffeeBatch):
    """Test retrieving shipment events for a batch."""
    # Create two shipment events
    create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln=test_batch.gln,
        destination_gln="0614141000027",
        quantity_kg=250.0,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper1",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln="0614141000027",
        destination_gln="0614141000034",
        quantity_kg=250.0,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper2",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    # Get all shipment events
    events = get_batch_shipment_events(test_batch.batch_id)
    
    assert len(events) == 2
    assert all("event_hash" in e for e in events)
    assert all("ipfs_cid" in e for e in events)
    assert all("blockchain_tx_hash" in e for e in events)


def test_shipment_event_hash_no_prefix(db_session: Session, test_batch: CoffeeBatch):
    """Test that event hash is 64 chars without 0x prefix."""
    result = create_shipment_event(
        db=db_session,
        batch_id=test_batch.batch_id,
        gtin=test_batch.gtin,
        source_gln=test_batch.gln,
        destination_gln="0614141000027",
        quantity_kg=test_batch.quantity_kg,
        variety=test_batch.variety,
        origin=test_batch.origin,
        shipper_did="did:key:z6MkShipper",
        batch_db_id=test_batch.id,
        submitter_db_id=test_batch.created_by_user_id
    )
    
    event_hash = result["event_hash"]
    
    # Verify hash format: 64 hex chars, no 0x prefix
    assert len(event_hash) == 64
    assert not event_hash.startswith("0x")
    assert all(c in "0123456789abcdef" for c in event_hash.lower())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
