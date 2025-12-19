"""
EPCIS 2.0 Commission Event Builder

Creates ObjectEvent with action="ADD" and bizStep="commissioning"
when a farmer creates a new coffee batch.

Commission events record the entry of a batch into the supply chain,
capturing harvest/production data with GS1-compliant identifiers.

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


def create_commission_event(
    db: Session,
    batch_id: str,
    gtin: str,
    gln: str,
    quantity_kg: float,
    variety: str,
    origin: str,
    farmer_did: str,
    processing_method: str = "Washed",
    quality_grade: str = "A",
    batch_db_id: Optional[int] = None,
    submitter_db_id: Optional[int] = None
) -> Optional[dict]:
    """
    Create EPCIS 2.0 ObjectEvent for batch commissioning.
    
    Commissioning represents the creation of a new coffee batch
    and its entry into the supply chain. This is the foundational
    event that establishes provenance.
    
    Args:
        db: Database session
        batch_id: Unique batch identifier (e.g., "BATCH-2025-001")
        gtin: 14-digit Global Trade Item Number
        gln: 13-digit Global Location Number
        quantity_kg: Batch quantity in kilograms
        variety: Coffee variety (e.g., "Arabica Heirloom")
        origin: Origin location (e.g., "Yirgacheffe, Ethiopia")
        farmer_did: Farmer's DID (e.g., "did:key:z6Mk...")
        processing_method: Processing method (e.g., "Washed", "Natural")
        quality_grade: Initial quality grade (e.g., "A", "B", "C")
        batch_db_id: Database ID of the batch (for foreign key)
        submitter_db_id: Database ID of the submitter (for foreign key)
    
    Returns:
        Dict containing:
        - event_hash: SHA-256 hash of canonicalized event
        - ipfs_cid: IPFS Content Identifier
        - blockchain_tx_hash: Ethereum transaction hash
        - event: Full EPCIS event JSON
        
        Returns None if creation fails.
    
    Example:
        >>> with get_db() as db:
        ...     event = create_commission_event(
        ...         db=db,
        ...         batch_id="BATCH-2025-001",
        ...         gtin="06141418123450",
        ...         gln="0614141000010",
        ...         quantity_kg=500.0,
        ...         variety="Arabica Heirloom",
        ...         origin="Yirgacheffe, Ethiopia",
        ...         farmer_did="did:key:z6MkTestFarmer",
        ...         processing_method="Washed"
        ...     )
        ...     print(f"Event: {event['event_hash']}")
    """
    try:
        from gs1.identifiers import gtin_to_sgtin_urn
        
        # Build GS1 URN identifiers (EPCIS 2.0 compliant)
        # SGTIN: Serialized Global Trade Item Number
        sgtin = gtin_to_sgtin_urn(gtin, batch_id)
        
        # LGTIN: Lot/Global Trade Item Number (for quantity)
        lgtin = f"urn:epc:class:lgtin:{gtin}"
        
        # SGLN: Serialized Global Location Number
        # Clean origin for use as location extension (alphanumeric + hyphens only)
        location_extension = origin.lower().replace(' ', '-').replace(',', '')
        sgln = f"urn:epc:id:sgln:{gln}.{location_extension}"
        
        # Build EPCIS 2.0 ObjectEvent
        event = {
            "@context": "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld",
            "type": "ObjectEvent",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "eventTimeZoneOffset": "+03:00",  # East Africa Time (Ethiopia)
            "action": "ADD",  # Batch is being added to supply chain
            "bizStep": "urn:epcglobal:cbv:bizstep:commissioning",  # GS1 CBV vocabulary
            "disposition": "urn:epcglobal:cbv:disp:active",  # Batch is active/available
            
            # Serialized item identifier
            "epcList": [sgtin],
            
            # Lot/batch quantity
            "quantityList": [
                {
                    "epcClass": lgtin,
                    "quantity": quantity_kg,
                    "uom": "KGM"  # Kilograms
                }
            ],
            
            # Location where event occurred
            "readPoint": {
                "id": sgln
            },
            
            # Business location (typically same as readPoint for harvest)
            "bizLocation": {
                "id": sgln
            },
            
            # Custom extension fields
            "extension": {
                "farmer_did": farmer_did,
                "variety": variety,
                "origin": origin,
                "processing_method": processing_method,
                "quality_grade": quality_grade,
                "event_type": "harvest_commission"
            }
        }
        
        # Canonicalize event for hashing
        # Note: Full JSON-LD canonicalization (RDF Dataset Canonicalization)
        # would be more robust, but simple JSON stringify is acceptable
        # for internal use and provides deterministic hashing
        canonical = json.dumps(event, sort_keys=True, separators=(',', ':'))
        event_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        
        print(f"Creating commission event for batch {batch_id}...")
        print(f"  Event hash: {event_hash[:16]}...")
        
        # Import here to avoid circular dependencies
        from database.crud import create_event
        from database.models import EPCISEvent
        
        # Prepare event data for database
        event_data = {
            'event_hash': event_hash,
            'event_type': 'ObjectEvent',
            'canonical_nquads': canonical,  # Store canonical form
            'event_json': event,  # Store full event
            'event_time': datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00')),
            'biz_step': 'commissioning',
            'biz_location': sgln,
            'batch_id': batch_db_id,
            'submitter_id': submitter_db_id
        }
        
        # Create event in database (automatically handles IPFS + blockchain)
        db_event = create_event(
            db,
            event_data,
            pin_to_ipfs=True,  # Pin full event to IPFS via Pinata
            anchor_to_blockchain=True  # Anchor hash to Base Sepolia
        )
        
        if db_event:
            print(f"✓ Commission event created successfully")
            print(f"  IPFS CID: {db_event.ipfs_cid}")
            print(f"  Blockchain TX: {db_event.blockchain_tx_hash[:16] + '...' if db_event.blockchain_tx_hash else 'pending'}")
            
            return {
                'event_hash': event_hash,
                'ipfs_cid': db_event.ipfs_cid,
                'blockchain_tx_hash': db_event.blockchain_tx_hash,
                'blockchain_confirmed': db_event.blockchain_confirmed,
                'event': event,
                'db_event': db_event  # Return database object for further use
            }
        
        print("✗ Failed to store commission event in database")
        return None
        
    except Exception as e:
        print(f"✗ Failed to create commission event: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_commission_events_for_batch(db: Session, batch_id: str) -> list:
    """
    Retrieve all commission events for a specific batch.
    
    Args:
        db: Database session
        batch_id: Batch identifier
    
    Returns:
        List of EPCISEvent objects with biz_step='commissioning'
    """
    from database.models import EPCISEvent, CoffeeBatch
    
    # Find batch database ID
    batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
    if not batch:
        return []
    
    # Query commission events for this batch
    events = db.query(EPCISEvent).filter(
        EPCISEvent.batch_id == batch.id,
        EPCISEvent.biz_step == 'commissioning'
    ).order_by(EPCISEvent.event_time.desc()).all()
    
    return events
