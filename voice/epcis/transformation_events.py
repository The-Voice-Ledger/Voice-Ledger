"""
EPCIS 2.0 Transformation Event Builder

Creates TransformationEvents for batch splits where one input batch
is divided into multiple output batches with mass balance validation.

Use Case: Exporter receives 10,000kg lot, splits into:
- 6,000kg → EU buyer (EUDR compliant DPP)
- 4,000kg → US buyer (different certification)

Each output batch inherits farmer data from parent, maintains traceability.

Flow:
1. Validate mass balance (input = sum of outputs)
2. Create TransformationEvent (EPCIS 2.0)
3. Update parent batch (mark as split)
4. Create child batches (inherit farmer IDs)
5. Generate DPPs for each child

Created: December 19, 2025
Part of Aggregation Roadmap - Section 1.1.3
"""

from typing import Optional, List, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import hashlib
import json


def create_transformation_event(
    db: Session,
    input_batch_id: str,
    output_batches: List[Dict[str, any]],  # [{"batch_id": "...", "quantity_kg": 6000.0}, ...]
    transformation_type: str,  # "split", "blend", "repack"
    location_gln: str,
    operator_did: str,
    notes: Optional[str] = None
) -> Optional[dict]:
    """
    Create EPCIS 2.0 TransformationEvent for batch splits.
    
    TransformationEvent represents the transformation of input products
    into output products with different identities. Unlike aggregation
    (containment), transformation creates NEW batches with inherited lineage.
    
    Args:
        db: Database session
        input_batch_id: Parent batch being split
        output_batches: List of dicts with batch_id and quantity_kg
        transformation_type: Type of transformation (split, blend, repack)
        location_gln: 13-digit Global Location Number where split occurs
        operator_did: Operator's DID
        notes: Optional notes about transformation
    
    Returns:
        Dict containing:
        - event_hash: SHA-256 hash of canonicalized event
        - ipfs_cid: IPFS Content Identifier
        - blockchain_tx_hash: Ethereum transaction hash
        - event: Full EPCIS event JSON
        - output_batch_ids: List of child batch IDs created
        
        Returns None if creation fails.
    
    Example:
        >>> with get_db() as db:
        ...     event = create_transformation_event(
        ...         db=db,
        ...         input_batch_id="BATCH-2025-001",
        ...         output_batches=[
        ...             {"batch_id": "BATCH-2025-001-A", "quantity_kg": 6000.0},
        ...             {"batch_id": "BATCH-2025-001-B", "quantity_kg": 4000.0}
        ...         ],
        ...         transformation_type="split",
        ...         location_gln="0614141000010",
        ...         operator_did="did:key:z6MkTestOperator"
        ...     )
    """
    try:
        from database.models import CoffeeBatch
        from database.crud import create_event
        from gs1.identifiers import gtin_to_sgtin_urn
        from .validators import validate_transformation_event
        
        # Fetch input batch
        input_batch = db.query(CoffeeBatch).filter(
            CoffeeBatch.batch_id == input_batch_id
        ).first()
        
        if not input_batch:
            raise ValueError(f"Input batch not found: {input_batch_id}")
        
        # Prepare validation data
        input_quantities = [{"quantity": input_batch.quantity_kg, "uom": "KGM"}]
        output_quantities = [{"quantity": b["quantity_kg"], "uom": "KGM"} for b in output_batches]
        output_batch_ids = [b["batch_id"] for b in output_batches]
        
        # ===== VALIDATION LAYER =====
        # Determine if this is a split (exact balance) or processing (mass loss allowed)
        # Processing transformations: roasting, milling, drying
        allow_loss = transformation_type.lower() in ['roasting', 'milling', 'drying', 'processing']
        
        # EUDR compliance is mandatory for all transformations (no exceptions)
        # EU Regulation 2023/1115 requires full traceability from farm to consumer
        is_valid, error_msg = validate_transformation_event(
            input_quantities=input_quantities,
            output_quantities=output_quantities,
            input_batch_ids=[input_batch_id],
            output_batch_ids=output_batch_ids,
            db=db,
            allow_loss=allow_loss
        )
        
        if not is_valid:
            print(f"❌ Validation failed: {error_msg}")
            raise ValueError(f"Validation failed: {error_msg}")
        
        # Build GS1 URN identifiers
        # Input SGTIN
        input_sgtin = gtin_to_sgtin_urn(input_batch.gtin, input_batch.batch_id)
        
        # SGLN for location
        location_extension = location_gln[-5:]  # Last 5 digits as extension
        sgln = f"urn:epc:id:sgln:{location_gln}.{location_extension}"
        
        # Build EPCIS 2.0 TransformationEvent
        event = {
            "@context": [
                "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
            ],
            "type": "TransformationEvent",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "eventTimeZoneOffset": "+00:00",
            
            # Input batch being split
            "inputEPCList": [input_sgtin],
            "inputQuantityList": [
                {
                    "epcClass": f"urn:epc:class:lgtin:{input_batch.gtin[1:8]}.{input_batch.gtin[8:14]}",
                    "quantity": input_batch.quantity_kg,
                    "uom": "KGM"
                }
            ],
            
            # Output batches (will be populated after batch creation)
            "outputEPCList": [],  # Will add after creating batches
            "outputQuantityList": [],
            
            # Business context
            "transformationID": f"urn:uuid:{hashlib.sha256(f'{input_batch_id}-{datetime.now().isoformat()}'.encode()).hexdigest()[:36]}",
            "bizStep": f"urn:epcglobal:cbv:bizstep:commissioning",
            "disposition": "active",
            
            # Location
            "bizLocation": {
                "id": sgln
            },
            
            # Operator
            "gdst:productOwner": operator_did,
            
            # Extension data
            "ilmd": {
                "transformationType": transformation_type,
                "parentBatch": input_batch_id,
                "notes": notes or f"Split {input_batch.quantity_kg}kg batch into {len(output_batches)} child batches"
            }
        }
        
        # Create child batches inheriting from parent
        created_batches = []
        from gs1.identifiers import gtin as generate_gtin
        
        for idx, output_spec in enumerate(output_batches):
            # Generate unique GTIN for each child (use batch_id for uniqueness)
            # Create unique numeric product code from batch_id hash (digits only)
            hash_val = int(hashlib.md5(output_spec["batch_id"].encode()).hexdigest()[:8], 16)
            hash_suffix = str(hash_val)[:5].zfill(5)  # Ensure 5 digits
            child_gtin = generate_gtin(hash_suffix, "GTIN-14")
            
            # Create child batch
            child_batch = CoffeeBatch(
                batch_id=output_spec["batch_id"],
                gtin=child_gtin,
                gln=input_batch.gln,
                batch_number=output_spec["batch_id"],
                quantity_kg=output_spec["quantity_kg"],
                
                # Inherit from parent
                origin=input_batch.origin,
                origin_country=input_batch.origin_country,
                origin_region=input_batch.origin_region,
                farm_name=input_batch.farm_name,
                variety=input_batch.variety,
                harvest_date=input_batch.harvest_date,
                processing_method=input_batch.processing_method,
                process_method=input_batch.process_method,
                quality_grade=input_batch.quality_grade,
                farmer_id=input_batch.farmer_id,  # KEY: Inherit farmer for EUDR compliance
                
                created_by_user_id=input_batch.created_by_user_id,
                created_by_did=input_batch.created_by_did,
                status="VERIFIED",  # Inherit verified status from parent
            )
            
            db.add(child_batch)
            created_batches.append(child_batch)
        
        db.flush()  # Get IDs for child batches
        
        # Update event with child batch SGTINs
        for child_batch in created_batches:
            child_sgtin = gtin_to_sgtin_urn(child_batch.gtin, child_batch.batch_id)
            event["outputEPCList"].append(child_sgtin)
            event["outputQuantityList"].append({
                "epcClass": f"urn:epc:class:lgtin:{child_batch.gtin[1:8]}.{child_batch.gtin[8:14]}",
                "quantity": child_batch.quantity_kg,
                "uom": "KGM"
            })
        
        # Canonicalize and hash
        canonical_event = json.dumps(event, sort_keys=True, separators=(',', ':'))
        event_hash = hashlib.sha256(canonical_event.encode('utf-8')).hexdigest()
        
        # Use same N-Quads as JSON for now (simplified)
        canonical_nquads = canonical_event
        
        # Prepare event_data dict for create_event
        event_data = {
            "event_type": "TransformationEvent",
            "event_json": event,
            "event_hash": event_hash,
            "canonical_nquads": canonical_nquads,  # Required by database schema
            "event_time": datetime.now(timezone.utc),
            "biz_step": "commissioning",
            "biz_location": sgln,
            "submitter_id": input_batch.created_by_user_id,
            "batch_id": input_batch.id  # Database ID for blockchain anchoring
        }
        
        # Create event in database with IPFS and blockchain
        result = create_event(
            db=db,
            event_data=event_data,
            pin_to_ipfs=True,
            anchor_to_blockchain=True
        )
        
        # Mark parent batch as split
        input_batch.status = "SPLIT"
        
        db.commit()
        
        print(f"✅ TransformationEvent created: {event_hash[:16]}...")
        print(f"   Input: {input_batch_id} ({input_batch.quantity_kg}kg)")
        print(f"   Outputs: {len(created_batches)} batches")
        for child in created_batches:
            print(f"      - {child.batch_id} ({child.quantity_kg}kg)")
        print(f"   IPFS: {result.ipfs_cid}")
        print(f"   Blockchain: {result.blockchain_tx_hash or 'pending'}")
        
        return {
            "event_hash": event_hash,
            "ipfs_cid": result.ipfs_cid,
            "blockchain_tx_hash": result.blockchain_tx_hash,
            "event": event,
            "output_batch_ids": [b.batch_id for b in created_batches],
            "transformation_id": event["transformationID"]
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating transformation event: {e}")
        import traceback
        traceback.print_exc()
        return None
