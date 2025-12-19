"""
EPCIS 2.0 Aggregation Event Builder

Creates AggregationEvent with action="ADD" or "DELETE" and bizStep="packing" or "unpacking"
when batches are packed into or unpacked from containers (pallets, shipping containers).

Aggregation events record containment relationships in the supply chain,
enabling efficient tracking of multiple batches as a single logistic unit.

Flow:
1. Build EPCIS 2.0 AggregationEvent with GS1 identifiers (SSCC for parent, SGTINs for children)
2. Canonicalize and hash event (SHA-256)
3. Pin to IPFS via Pinata
4. Anchor to blockchain via EPCISEventAnchor contract
5. Store in database with full metadata
6. Update aggregation_relationships table

Created: December 19, 2025
"""

from typing import Optional, List, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import hashlib
import json


def create_aggregation_event(
    db: Session,
    parent_sscc: str,
    child_batch_ids: List[str],
    action: str,  # "ADD" or "DELETE"
    biz_step: str,  # "packing" or "unpacking"
    location_gln: str,
    operator_did: str,
    batch_db_ids: Optional[List[int]] = None,
    submitter_db_id: Optional[int] = None
) -> Optional[dict]:
    """
    Create EPCIS 2.0 AggregationEvent for packing/unpacking batches.
    
    Aggregation represents the containment of multiple child items
    (coffee batches) within a parent container (pallet, shipping container).
    This enables efficient logistics and bulk tracking.
    
    Args:
        db: Database session
        parent_sscc: 18-digit Serial Shipping Container Code (e.g., "306141411234567892")
        child_batch_ids: List of batch identifiers to pack/unpack
        action: "ADD" (pack) or "DELETE" (unpack)
        biz_step: "packing", "unpacking", "loading", or "unloading"
        location_gln: 13-digit Global Location Number where operation occurs
        operator_did: Operator's DID (e.g., "did:key:z6Mk...")
        batch_db_ids: Optional list of batch database IDs (for foreign keys)
        submitter_db_id: Database ID of submitter (for foreign key)
    
    Returns:
        Dict containing:
        - event_hash: SHA-256 hash of canonicalized event
        - ipfs_cid: IPFS Content Identifier
        - blockchain_tx_hash: Ethereum transaction hash
        - event: Full EPCIS event JSON
        - aggregation_ids: List of aggregation_relationship IDs created
        
        Returns None if creation fails.
    
    Example:
        >>> with get_db() as db:
        ...     event = create_aggregation_event(
        ...         db=db,
        ...         parent_sscc="306141411234567892",
        ...         child_batch_ids=["BATCH-2025-001", "BATCH-2025-002"],
        ...         action="ADD",
        ...         biz_step="packing",
        ...         location_gln="0614141000010",
        ...         operator_did="did:key:z6MkTestOperator"
        ...     )
        ...     print(f"Packed {event['child_count']} batches")
    """
    try:
        from database.models import CoffeeBatch, AggregationRelationship
        from database.crud import create_event
        from gs1.sscc import sscc_to_urn
        from gs1.identifiers import gtin_to_sgtin_urn
        from .validators import validate_aggregation_event
        
        # ===== VALIDATION LAYER (Section 1.3) =====
        # Run all validators before creating event
        is_valid, error_msg = validate_aggregation_event(
            action=action,
            parent_sscc=parent_sscc,
            child_batch_ids=child_batch_ids,
            db=db
        )
        
        if not is_valid:
            print(f"❌ Validation failed: {error_msg}")
            raise ValueError(f"Validation failed: {error_msg}")
        
        # Validate action
        if action not in ["ADD", "DELETE"]:
            raise ValueError(f"action must be 'ADD' or 'DELETE', got '{action}'")
        
        # Validate biz_step
        valid_biz_steps = ["packing", "unpacking", "loading", "unloading"]
        if biz_step not in valid_biz_steps:
            raise ValueError(f"biz_step must be one of {valid_biz_steps}, got '{biz_step}'")
        
        # Validate parent SSCC (18 digits)
        if len(parent_sscc) != 18 or not parent_sscc.isdigit():
            raise ValueError(f"parent_sscc must be 18 digits, got '{parent_sscc}'")
        
        # Fetch batches from database
        batches = db.query(CoffeeBatch).filter(
            CoffeeBatch.batch_id.in_(child_batch_ids)
        ).all()
        
        if len(batches) != len(child_batch_ids):
            found_ids = [b.batch_id for b in batches]
            missing = set(child_batch_ids) - set(found_ids)
            raise ValueError(f"Batches not found: {missing}")
        
        # Build GS1 URN identifiers (EPCIS 2.0 compliant)
        # Parent SSCC URN
        parent_urn = sscc_to_urn(parent_sscc)
        
        # Child SGTINs (Serialized Global Trade Item Numbers)
        # GS1 format: urn:epc:id:sgtin:CompanyPrefix.ItemRef.Serial
        child_epcs = [gtin_to_sgtin_urn(batch.gtin, batch.batch_id) for batch in batches]
        
        # SGLN for location
        location_extension = location_gln[-5:]  # Last 5 digits as extension
        sgln = f"urn:epc:id:sgln:{location_gln}.{location_extension}"
        
        # Build EPCIS 2.0 AggregationEvent
        event = {
            "@context": [
                "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
            ],
            "type": "AggregationEvent",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "eventTimeZoneOffset": "+00:00",
            "action": action,
            
            # Parent-child relationship
            "parentID": parent_urn,
            "childEPCs": child_epcs,
            
            # Business context
            "bizStep": f"urn:epcglobal:cbv:bizstep:{biz_step}",
            "disposition": "in_progress" if action == "ADD" else "completed",
            
            # Location
            "bizLocation": {
                "id": sgln
            },
            
            # Operator/Actor
            "gdst:productOwner": operator_did
        }
        
        # Canonicalize JSON (sort keys for deterministic hashing)
        canonical_event = json.dumps(event, sort_keys=True, separators=(',', ':'))
        event_hash = hashlib.sha256(canonical_event.encode('utf-8')).hexdigest()
        
        # Generate canonical N-Quads for RDF representation
        # Using JSON-LD context for semantic web compatibility
        canonical_nquads = canonical_event  # Simplified: use JSON as N-Quads for now
        
        print(f"Creating aggregation event: {action} {len(child_batch_ids)} batches")
        print(f"  Parent SSCC: {parent_sscc}")
        print(f"  Event hash: {event_hash[:16]}...")
        
        # Prepare event data for database
        event_data = {
            'event_hash': event_hash,
            'event_type': 'AggregationEvent',
            'canonical_nquads': canonical_nquads,  # Required by database schema
            'event_json': event,
            'event_time': datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00')),
            'biz_step': biz_step,
            'biz_location': sgln,
            'batch_id': None,  # AggregationEvent doesn't link to single batch
            'submitter_id': submitter_db_id
        }
        
        # Create event in database (automatically handles IPFS + blockchain)
        db_event = create_event(
            db,
            event_data,
            pin_to_ipfs=True,  # Pin full event to IPFS via Pinata
            anchor_to_blockchain=True  # Anchor hash to blockchain
        )
        
        if not db_event:
            print("✗ Failed to store aggregation event in database")
            return None
        
        print(f"✓ Aggregation event created successfully")
        print(f"  IPFS CID: {db_event.ipfs_cid}")
        print(f"  Blockchain TX: {db_event.blockchain_tx_hash[:16] + '...' if db_event.blockchain_tx_hash else 'pending'}")
        
        # Update aggregation_relationships table
        aggregation_ids = []
        
        if action == "ADD":
            # Create new relationships for each child
            print(f"  Creating {len(child_batch_ids)} aggregation relationships...")
            for i, batch_id in enumerate(child_batch_ids):
                # Get batch quantity for contribution tracking
                batch = batches[i]
                
                agg_rel = AggregationRelationship(
                    parent_sscc=parent_sscc,
                    child_identifier=batch_id,
                    child_type='batch',
                    contribution_kg=batch.quantity_kg,  # Store contribution quantity
                    aggregation_event_id=db_event.id,
                    is_active=True,
                    aggregated_at=datetime.now(timezone.utc)
                )
                db.add(agg_rel)
                db.flush()
                aggregation_ids.append(agg_rel.id)
            print(f"  ✓ Created {len(aggregation_ids)} aggregation relationships")
        
        elif action == "DELETE":
            # Mark relationships as inactive
            print(f"  Marking aggregation relationships as inactive...")
            relationships = db.query(AggregationRelationship).filter(
                AggregationRelationship.parent_sscc == parent_sscc,
                AggregationRelationship.child_identifier.in_(child_batch_ids),
                AggregationRelationship.is_active == True
            ).all()
            
            for rel in relationships:
                rel.is_active = False
                rel.disaggregated_at = datetime.utcnow()
                rel.disaggregation_event_id = db_event.id
                aggregation_ids.append(rel.id)
            print(f"  ✓ Marked {len(aggregation_ids)} relationships as inactive")
        
        db.commit()
        
        return {
            'event_hash': event_hash,
            'ipfs_cid': db_event.ipfs_cid,
            'blockchain_tx_hash': db_event.blockchain_tx_hash,
            'blockchain_confirmed': db_event.blockchain_confirmed,
            'event': event,
            'db_event': db_event,
            'parent_sscc': parent_sscc,
            'child_count': len(child_batch_ids),
            'action': action,
            'aggregation_ids': aggregation_ids
        }
        
    except Exception as e:
        print(f"✗ Failed to create aggregation event: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_container_contents(
    db: Session,
    parent_sscc: str
) -> List[Dict]:
    """
    Get all items currently packed in a container.
    
    Args:
        db: Database session
        parent_sscc: 18-digit SSCC of container
        
    Returns:
        List of child items with details
        
    Example:
        >>> with get_db() as db:
        ...     contents = get_container_contents(db, "306141411234567892")
        ...     print(f"Container has {len(contents)} batches")
    """
    from database.models import CoffeeBatch, AggregationRelationship
    
    relationships = db.query(AggregationRelationship).filter(
        AggregationRelationship.parent_sscc == parent_sscc,
        AggregationRelationship.is_active == True
    ).all()
    
    result = []
    for rel in relationships:
        if rel.child_type == "batch":
            # Get batch details
            batch = db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id == rel.child_identifier
            ).first()
            
            if batch:
                result.append({
                    "batch_id": batch.batch_id,
                    "gtin": batch.gtin,
                    "variety": batch.variety,
                    "quantity_kg": batch.quantity_kg,
                    "packed_at": rel.aggregated_at.isoformat()
                })
    
    return result


def get_batch_container(
    db: Session,
    batch_id: str
) -> Optional[Dict]:
    """
    Find which container (if any) a batch is currently in.
    
    Args:
        db: Database session
        batch_id: Batch identifier
        
    Returns:
        Container details or None if not packed
        
    Example:
        >>> with get_db() as db:
        ...     container = get_batch_container(db, "BATCH-2025-001")
        ...     if container:
        ...         print(f"Batch is in {container['parent_sscc']}")
    """
    from database.models import AggregationRelationship
    from gs1.sscc import sscc_to_urn
    
    rel = db.query(AggregationRelationship).filter(
        AggregationRelationship.child_identifier == batch_id,
        AggregationRelationship.is_active == True
    ).first()
    
    if not rel:
        return None
    
    return {
        "parent_sscc": rel.parent_sscc,
        "packed_at": rel.aggregated_at.isoformat(),
        "parent_urn": sscc_to_urn(rel.parent_sscc)
    }


# Self-test
if __name__ == "__main__":
    from database.connection import get_db
    from database.models import CoffeeBatch
    
    print("Testing aggregation events module...")
    
    with get_db() as session:
        # Check if we have any batches
        batch_count = session.query(CoffeeBatch).count()
        print(f"Found {batch_count} batches in database")
        
        if batch_count >= 2:
            # Get first 2 batches
            batches = session.query(CoffeeBatch).limit(2).all()
            batch_ids = [b.batch_id for b in batches]
            
            print(f"\nTesting with batches: {batch_ids}")
            
            # Generate SSCC for test pallet
            from gs1.sscc import generate_sscc
            test_sscc = generate_sscc(extension="3")
            print(f"Generated test SSCC: {test_sscc}")
            
            print("\n✓ Module loaded successfully")
            print("✓ Database connection working")
            print("✓ Ready to create aggregation events")
        else:
            print("\n⚠️ Need at least 2 batches in database to test")
            print("Run commission events first to create batches")
