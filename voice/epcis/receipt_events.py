"""
EPCIS 2.0 Receipt Event Builder

Creates ObjectEvent with action="OBSERVE" and bizStep="receiving"
when a batch is received at a destination location.

Receipt events record the acceptance and verification of coffee batches
at destination facilities, completing the shipment cycle and maintaining
chain of custody.

Flow:
1. Build EPCIS 2.0 ObjectEvent with GS1 identifiers (SGTIN, SGLN)
2. Canonicalize and hash event (SHA-256)
3. Pin to IPFS via Pinata
4. Anchor to blockchain via EPCISEventAnchor contract
5. Store in database with full metadata
6. Update batch status to "RECEIVED"

Created: December 19, 2025
"""

from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import hashlib
import json


def create_receipt_event(
    db: Session,
    batch_id: str,
    gtin: str,
    receiving_gln: str,
    quantity_kg: float,
    variety: str,
    origin: str,
    receiver_did: str,
    condition: Optional[str] = "good",
    notes: Optional[str] = None,
    batch_db_id: Optional[int] = None,
    submitter_db_id: Optional[int] = None
) -> Optional[dict]:
    """
    Create EPCIS 2.0 ObjectEvent for batch receipt.
    
    Receipt represents the acceptance of a coffee batch at its destination,
    recording the change in custody and confirming the physical arrival
    of goods within the supply chain.
    
    Args:
        db: Database session
        batch_id: Unique batch identifier (e.g., "BATCH-2025-001")
        gtin: GTIN-14 identifier for the product
        receiving_gln: GLN of the receiving facility
        quantity_kg: Quantity received in kilograms
        variety: Coffee variety (e.g., "Arabica", "Robusta")
        origin: Origin location/farm name
        receiver_did: DID of the receiving party
        condition: Condition of received goods ("good", "damaged", "acceptable")
        notes: Optional notes about the receipt
        batch_db_id: Optional batch database ID for linking
        submitter_db_id: Optional user database ID who submitted
        
    Returns:
        dict: {
            event_hash: SHA-256 hash of canonicalized event
            ipfs_cid: IPFS CID where event is pinned
            blockchain_tx_hash: Transaction hash of blockchain anchor
            blockchain_confirmed: Boolean confirmation status
            event: Full EPCIS 2.0 event dict
            db_event: EPCISEvent database object
        }
        None if creation fails
    """
    from database.crud import create_event
    from database.models import CoffeeBatch
    from ipfs.ipfs_storage import pin_epcis_event
    from blockchain.blockchain_anchor import anchor_event_to_blockchain
    from gs1.identifiers import gtin_to_sgtin_urn
    
    print(f"Creating receipt event for batch {batch_id}...")
    
    try:
        # Build GS1 identifiers
        sgtin = gtin_to_sgtin_urn(gtin, batch_id)
        sgln = f"urn:epc:id:sgln:{receiving_gln}.0"
        
        # Build EPCIS 2.0 ObjectEvent
        event_time = datetime.now(timezone.utc).isoformat()
        
        event = {
            "@context": [
                "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
            ],
            "type": "ObjectEvent",
            "eventTime": event_time,
            "eventTimeZoneOffset": "+00:00",
            "action": "OBSERVE",
            
            # Business step: receiving goods at destination
            "bizStep": "receiving",
            
            # Disposition: in_progress (under inspection/verification)
            "disposition": "in_progress",
            
            # EPC list - batches being received
            "epcList": [sgtin],
            
            # Quantity information
            "quantityList": [
                {
                    "epcClass": sgtin,
                    "quantity": quantity_kg,
                    "uom": "KGM"  # Kilogram
                }
            ],
            
            # Location where event occurred (receiving facility)
            "readPoint": {
                "id": sgln
            },
            
            # Business location (same as readPoint for receipt)
            "bizLocation": {
                "id": sgln
            },
            
            # Custom extension fields
            "extension": {
                "receiver_did": receiver_did,
                "variety": variety,
                "origin": origin,
                "condition": condition,
                "notes": notes,
                "event_type": "receipt"
            }
        }
        
        # Canonicalize event for hashing
        canonical = json.dumps(event, sort_keys=True, separators=(',', ':'))
        event_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        
        print(f"Event hash: {event_hash[:16]}...")
        
        # Pin to IPFS
        ipfs_cid = pin_epcis_event(event, event_hash)
        if not ipfs_cid:
            print("✗ Failed to pin to IPFS")
            return None
        
        # Anchor to blockchain
        blockchain_tx_hash = anchor_event_to_blockchain(
            batch_id=batch_id,
            event_hash=event_hash,
            ipfs_cid=ipfs_cid,
            event_type="ObjectEvent",
            location=origin or "",
            submitter=receiver_did or ""
        )
        
        blockchain_confirmed = bool(blockchain_tx_hash)
        
        # Store in database (let create_event handle IPFS/blockchain)
        event_data = {
            'event_type': 'ObjectEvent',
            'biz_step': 'receiving',
            'event_time': datetime.fromisoformat(event_time.replace('Z', '+00:00')),
            'event_hash': event_hash,
            'event_json': event,
            'canonical_nquads': canonical,
            'batch_id': batch_db_id,
            'submitter_id': submitter_db_id
        }
        
        # Note: create_event() will handle IPFS pinning and blockchain anchoring
        # But we already did it above, so disable re-pinning
        db_event = create_event(db, event_data, pin_to_ipfs=False, anchor_to_blockchain=False)
        
        if db_event:
            # Update batch status to RECEIVED
            if batch_db_id:
                batch = db.query(CoffeeBatch).filter(CoffeeBatch.id == batch_db_id).first()
                if batch:
                    batch.status = "RECEIVED"
                    db.commit()
                    print(f"✓ Updated batch status to RECEIVED")
            
            print(f"✓ Receipt event created successfully")
            print(f"  IPFS CID: {db_event.ipfs_cid}")
            print(f"  Blockchain TX: {db_event.blockchain_tx_hash[:16] + '...' if db_event.blockchain_tx_hash else 'pending'}")
            
            return {
                'event_hash': event_hash,
                'ipfs_cid': db_event.ipfs_cid,
                'blockchain_tx_hash': db_event.blockchain_tx_hash,
                'blockchain_confirmed': db_event.blockchain_confirmed,
                'event': event,
                'db_event': db_event
            }
        
        print("✗ Failed to store receipt event in database")
        return None
        
    except Exception as e:
        print(f"✗ Failed to create receipt event: {e}")
        import traceback
        traceback.print_exc()
        return None
