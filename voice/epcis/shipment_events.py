"""
EPCIS 2.0 Shipment Event Builder

Creates ObjectEvent with action="OBSERVE" and bizStep="shipping"
when a batch is dispatched from one location to another.

Shipment events record the movement of coffee batches through the supply chain,
capturing origin, destination, carrier information, and maintaining traceability.

Flow:
1. Build EPCIS 2.0 ObjectEvent with GS1 identifiers (SGTIN, LGTIN, SGLN)
2. Canonicalize and hash event (SHA-256)
3. Pin to IPFS via Pinata
4. Anchor to blockchain via EPCISEventAnchor contract
5. Store in database with full metadata

Created: December 18, 2025
"""

from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import hashlib
import json


def create_shipment_event(
    db: Session,
    batch_id: str,
    gtin: str,
    source_gln: str,
    destination_gln: str,
    quantity_kg: float,
    variety: str,
    origin: str,
    shipper_did: str,
    carrier: Optional[str] = None,
    tracking_number: Optional[str] = None,
    expected_delivery_date: Optional[str] = None,
    batch_db_id: Optional[int] = None,
    submitter_db_id: Optional[int] = None
) -> Optional[dict]:
    """
    Create EPCIS 2.0 ObjectEvent for batch shipment.
    
    Shipment represents the dispatch of a coffee batch from a source
    location to a destination, recording the change in custody and
    physical location within the supply chain.
    
    Args:
        db: Database session
        batch_id: Unique batch identifier (e.g., "BATCH-2025-001")
        gtin: 14-digit Global Trade Item Number
        source_gln: 13-digit GLN of shipping location
        destination_gln: 13-digit GLN of receiving location
        quantity_kg: Batch quantity in kilograms
        variety: Coffee variety (e.g., "Arabica Heirloom")
        origin: Origin location (e.g., "Yirgacheffe, Ethiopia")
        shipper_did: Shipper's DID (e.g., "did:key:z6Mk...")
        carrier: Optional carrier name (e.g., "DHL", "FedEx")
        tracking_number: Optional shipment tracking number
        expected_delivery_date: Optional ISO date string
        batch_db_id: Database ID of the batch (for foreign key)
        submitter_db_id: Database ID of the submitter (for foreign key)
    
    Returns:
        Dict containing:
        - event_hash: SHA-256 hash of canonicalized event
        - ipfs_cid: IPFS Content Identifier
        - blockchain_tx_hash: Ethereum transaction hash
        - blockchain_confirmed: Boolean indicating if TX was mined
        - event: Full EPCIS event JSON
        
        Returns None if creation fails.
    
    Example:
        >>> with get_db() as db:
        ...     event = create_shipment_event(
        ...         db=db,
        ...         batch_id="BATCH-2025-001",
        ...         gtin="06141418123450",
        ...         source_gln="0614141000010",
        ...         destination_gln="0614141000027",
        ...         quantity_kg=500.0,
        ...         variety="Arabica Heirloom",
        ...         origin="Yirgacheffe, Ethiopia",
        ...         shipper_did="did:key:z6Mk..."
        ...     )
    """
    
    from database.crud import create_event
    from gs1.identifiers import gtin_to_sgtin_urn
    
    # Generate GS1 URN identifiers following EPCIS 2.0 spec
    # SGTIN: Serialized Global Trade Item Number (individual batch)
    sgtin = gtin_to_sgtin_urn(gtin, batch_id)
    
    # LGTIN: Lot/Batch Global Trade Item Number (for quantity)
    lgtin = f"urn:epc:class:lgtin:{gtin[:13]}.{gtin[13]}.{batch_id}"
    
    # SGLN: Source and destination locations
    source_sgln = f"urn:epc:id:sgln:{source_gln}.0"
    destination_sgln = f"urn:epc:id:sgln:{destination_gln}.0"
    
    # Build EPCIS 2.0 ObjectEvent
    event_time = datetime.now(timezone.utc).isoformat()
    
    epcis_event = {
        "@context": [
            "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
        ],
        "type": "ObjectEvent",
        "eventTime": event_time,
        "eventTimeZoneOffset": "+00:00",
        "action": "OBSERVE",
        "bizStep": "urn:epcglobal:cbv:bizstep:shipping",
        "disposition": "urn:epcglobal:cbv:disp:in_transit",
        
        # What: Items being shipped
        "epcList": [sgtin],
        "quantityList": [
            {
                "epcClass": lgtin,
                "quantity": quantity_kg,
                "uom": "KGM"  # UN/CEFACT kilogram code
            }
        ],
        
        # Where: Source and destination
        "bizLocation": {
            "id": source_sgln
        },
        "readPoint": {
            "id": source_sgln
        },
        
        # Source/Destination in structured format
        "sourceList": [
            {
                "type": "urn:epcglobal:cbv:sdt:location",
                "source": source_sgln
            }
        ],
        "destinationList": [
            {
                "type": "urn:epcglobal:cbv:sdt:location",
                "destination": destination_sgln
            }
        ],
        
        # Custom attributes
        "ilmd": {
            "variety": variety,
            "origin": origin,
            "batch_id": batch_id
        },
        
        # Extension fields for additional context
        "gdst:productOwner": shipper_did
    }
    
    # Add optional fields if provided
    if carrier:
        epcis_event["gdst:vesselName"] = carrier  # Reusing GDST field for carrier
    
    if tracking_number:
        epcis_event["gdst:vesselID"] = tracking_number
    
    if expected_delivery_date:
        epcis_event["gdst:expectedDeliveryDate"] = expected_delivery_date
    
    # Canonicalize (sort keys recursively) and generate event hash
    def sort_dict(d):
        """Recursively sort dictionary keys for canonical representation."""
        if isinstance(d, dict):
            return {k: sort_dict(v) for k, v in sorted(d.items())}
        elif isinstance(d, list):
            return [sort_dict(item) for item in d]
        return d
    
    canonical_event = sort_dict(epcis_event)
    event_json = json.dumps(canonical_event, separators=(',', ':'))
    event_hash = hashlib.sha256(event_json.encode()).hexdigest()
    
    # Store event in database with IPFS pinning and blockchain anchoring
    # The create_event function handles IPFS and blockchain automatically
    result = create_event(
        db=db,
        event_data={
            "event_type": "ObjectEvent",
            "event_json": epcis_event,
            "event_hash": event_hash,
            "event_time": datetime.fromisoformat(event_time.replace('Z', '+00:00')),
            "canonical_nquads": event_json,
            "biz_step": "shipping",
            "batch_id": batch_db_id,
            "submitter_id": submitter_db_id
        },
        pin_to_ipfs=True,
        anchor_to_blockchain=True
    )
    
    if not result:
        return None
    
    return {
        "event_hash": event_hash,
        "ipfs_cid": result.ipfs_cid if hasattr(result, 'ipfs_cid') else None,
        "blockchain_tx_hash": result.blockchain_tx_hash if hasattr(result, 'blockchain_tx_hash') else None,
        "blockchain_confirmed": result.blockchain_confirmed if hasattr(result, 'blockchain_confirmed') else False,
        "event": epcis_event
    }


def get_batch_shipment_events(batch_id: str) -> list:
    """
    Retrieve all shipment events for a batch.
    
    Args:
        batch_id: Batch identifier
    
    Returns:
        List of shipment events ordered by event time
    """
    from database.database import get_db
    from database.models import EPCISEvent, CoffeeBatch
    
    with get_db() as db:
        # Find batch's database ID
        batch = db.query(CoffeeBatch).filter(
            CoffeeBatch.batch_id == batch_id
        ).first()
        
        if not batch:
            return []
        
        # Query shipment events
        events = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id == batch.id,
            EPCISEvent.biz_step == "shipping"
        ).order_by(EPCISEvent.created_at).all()
        
        return [
            {
                "event_hash": e.event_hash,
                "event_time": e.created_at.isoformat(),
                "ipfs_cid": e.ipfs_cid,
                "blockchain_tx_hash": e.blockchain_tx_hash,
                "event_data": e.event_json
            }
            for e in events
        ]
