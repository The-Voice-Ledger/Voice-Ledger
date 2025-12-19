"""
Voice Command to Database Integration

This module maps voice command intents to database operations.
It handles entity validation, required field generation, and CRUD execution.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.crud import create_batch, create_event, get_farmer_by_farmer_id, get_batch_by_batch_id
from sqlalchemy.orm import Session

# Import GS1 and EPCIS utilities
from gs1.identifiers import gtin as generate_gtin, sscc as generate_sscc
import hashlib
import json


class VoiceCommandError(Exception):
    """Raised when voice command cannot be executed."""
    pass


def generate_batch_id_from_entities(entities: dict) -> str:
    """
    Generate a unique batch_id from voice command entities.
    
    Format: FARMER_PRODUCT_TIMESTAMP
    Example: ABEBE_ARABICA_20251214_143025
    
    Args:
        entities: Extracted entities from NLU
        
    Returns:
        Generated batch_id (unique per second)
    """
    origin = entities.get("origin", "UNKNOWN").upper().replace(" ", "_")[:20]
    product = entities.get("product", "COFFEE").upper().replace(" ", "_")[:15]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")  # Include time for uniqueness
    
    return f"{origin}_{product}_{timestamp}"


def handle_record_commission(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_commission' intent - create new coffee batch.
    
    Voice example: "Record commission of 50 bags from Abebe farm"
    
    Args:
        db: Database session
        entities: {quantity, unit, product, origin}
        user_id: Optional user database ID (for VC issuance)
        user_did: Optional user DID (for batch ownership)
        
    Returns:
        Tuple of (success_message, created_batch_dict)
        
    Raises:
        VoiceCommandError: If required entities missing or operation fails
    """
    # Validate required entities
    required = ["quantity", "origin"]
    missing = [field for field in required if not entities.get(field)]
    if missing:
        raise VoiceCommandError(f"Missing required information: {', '.join(missing)}")
    
    # Extract entities
    quantity = entities.get("quantity")
    origin = entities.get("origin", "Unknown")
    product = entities.get("product", "Arabica Coffee")
    unit = entities.get("unit", "bags")
    
    # Generate required IDs
    batch_id = generate_batch_id_from_entities(entities)
    # GTIN-14 format: indicator(1) + company_prefix(7) + product_code(5) + check_digit(1) = 14 total
    # Use seconds since midnight as unique 5-digit code (00000-86399)
    now = datetime.utcnow()
    seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    product_code = str(seconds_today).zfill(5)  # Zero-pad to exactly 5 digits
    gtin = generate_gtin(product_code, "GTIN-14")  # 14-digit GTIN
    batch_number = f"BATCH-{now.strftime('%Y%m%d-%H%M%S')}"
    
    # Generate or retrieve GLN for user's location
    gln = None
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            gln = get_or_create_user_gln(user_id, db)
        except Exception as e:
            print(f"Warning: Failed to generate GLN: {e}")
    
    # Convert quantity to kg (assuming 60kg per bag if unit is "bags")
    if unit.lower() in ["bag", "bags"]:
        quantity_kg = float(quantity) * 60.0
    else:
        quantity_kg = float(quantity)
    
    # Generate verification token and expiration
    from voice.verification.verification_tokens import generate_verification_token, get_verification_expiration
    verification_token = generate_verification_token(batch_id)
    verification_expires_at = get_verification_expiration(hours=48)  # 48-hour expiration
    
    # Prepare batch data with correct field names from CoffeeBatch model
    batch_data = {
        "batch_id": batch_id,
        "gtin": gtin,
        "gln": gln,  # Global Location Number (may be None for backward compatibility)
        "batch_number": batch_number,
        "quantity_kg": quantity_kg,
        "origin": origin,
        "variety": product,
        "processing_method": "Washed",  # Default processing method
        "quality_grade": "A",  # Default quality grade (A, B, C, etc.)
        "created_at": datetime.utcnow(),
        "created_by_user_id": user_id,  # Track user ownership
        "created_by_did": user_did,  # Denormalized for fast queries
        # Verification workflow fields
        "status": "PENDING_VERIFICATION",  # Batch awaits verification
        "verification_token": verification_token,
        "verification_expires_at": verification_expires_at,
        "verification_used": False
    }
    
    # Create batch in database
    try:
        batch = create_batch(db, batch_data)
        
        # Note: Credentials are NOT issued at batch creation
        # They will be issued by the cooperative after verification
        # This ensures third-party attestation rather than self-issued claims
        
        # Create commission EPCIS event (IPFS + blockchain anchored)
        from voice.epcis.commission_events import create_commission_event
        
        event_result = create_commission_event(
            db=db,
            batch_id=batch.batch_id,
            gtin=batch.gtin,
            gln=batch.gln,
            quantity_kg=batch.quantity_kg,
            variety=batch.variety,
            origin=batch.origin,
            farmer_did=user_did,
            processing_method=batch.processing_method,
            quality_grade=batch.quality_grade,
            batch_db_id=batch.id,
            submitter_db_id=user_id
        )
        
        # Convert to dict for JSON response
        result = {
            "id": batch.id,
            "batch_id": batch.batch_id,
            "gtin": batch.gtin,
            "gln": batch.gln,  # Include GLN for notification display
            "quantity_kg": batch.quantity_kg,
            "origin": batch.origin,
            "variety": batch.variety,
            "status": batch.status,  # NEW: Include verification status
            "verification_token": batch.verification_token,  # NEW: For QR code generation
            "verification_expires_at": batch.verification_expires_at.isoformat() if batch.verification_expires_at else None,  # NEW
            "credential_issued": False,  # Will be True after cooperative verification
            "message": f"Successfully commissioned {quantity} {unit} of {product} from {origin}",
            # Include EPCIS event details
            "epcis_event": {
                "event_hash": event_result['event_hash'][:16] + "..." if event_result else None,
                "ipfs_cid": event_result['ipfs_cid'] if event_result else None,
                "blockchain_tx": event_result['blockchain_tx_hash'][:16] + "..." if event_result and event_result.get('blockchain_tx_hash') else None,
                "blockchain_confirmed": event_result.get('blockchain_confirmed', False) if event_result else False
            } if event_result else None
        }
        
        return ("Batch created successfully", result)
        
    except Exception as e:
        raise VoiceCommandError(f"Failed to create batch: {str(e)}")


def handle_record_shipment(db: Session, entities: dict, user_id: int = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_shipment' intent - create GS1 EPCIS 2.0 shipping event.
    
    Voice example: "Ship 50 bags to Addis warehouse"
    
    Args:
        db: Database session
        entities: {batch_id?, quantity?, destination, origin?}
        user_id: Optional user database ID (to find their batches)
        
    Returns:
        Tuple of (success_message, created_event_dict)
        
    Raises:
        VoiceCommandError: If required entities missing or batch not found
    """
    from database.models import CoffeeBatch
    # from database.crud import get_user  # Not needed - can use user_did directly
    from voice.epcis.shipment_events import create_shipment_event
    from sqlalchemy import desc
    
    # Required: destination
    destination = entities.get("destination")
    if not destination:
        raise VoiceCommandError(
            "Please specify where you're shipping to. "
            "Example: 'Ship to Addis warehouse'"
        )
    
    # Try to find the batch
    batch = None
    batch_id = entities.get("batch_id")
    
    if batch_id:
        # Explicit batch_id provided
        batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
        if not batch:
            raise VoiceCommandError(
                f"Batch '{batch_id}' not found. Please check the batch ID."
            )
    else:
        # No batch_id - try to find user's most recent PENDING_VERIFICATION batch
        if user_id:
            batch = db.query(CoffeeBatch).filter(
                CoffeeBatch.created_by_user_id == user_id,
                CoffeeBatch.status == "PENDING_VERIFICATION"
            ).order_by(desc(CoffeeBatch.created_at)).first()
            
            if not batch:
                # No pending batch - try any recent batch (within last 24 hours)
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(hours=24)
                batch = db.query(CoffeeBatch).filter(
                    CoffeeBatch.created_by_user_id == user_id,
                    CoffeeBatch.created_at >= cutoff
                ).order_by(desc(CoffeeBatch.created_at)).first()
                
        if not batch:
            raise VoiceCommandError(
                "No recent batch found to ship. Please create a batch first with: "
                "'Record 50 bags from my farm', then ship it."
            )
    
    # Get quantity from entities or use batch quantity
    quantity_kg = entities.get("quantity")
    if quantity_kg:
        # Convert bags to kg if needed
        unit = entities.get("unit", "kg")
        if unit.lower() in ["bag", "bags"]:
            quantity_kg = float(quantity_kg) * 60.0
        else:
            quantity_kg = float(quantity_kg)
    else:
        quantity_kg = batch.quantity_kg
    
    # Get user's DID for shipper identification (passed as parameter)
    shipper_did = "did:example:shipper"  # Default if no user context
    
    # Generate destination GLN (simplified for now)
    # In production, you'd look up actual GLN from a location registry
    destination_gln = "0614141000027"  # Default warehouse GLN
    
    # Create GS1 EPCIS 2.0 shipment event using dedicated module
    event_result = create_shipment_event(
        db=db,
        batch_id=batch.batch_id,
        gtin=batch.gtin,
        source_gln=batch.gln,
        destination_gln=destination_gln,
        quantity_kg=quantity_kg,
        variety=batch.variety,
        origin=batch.origin,
        shipper_did=shipper_did,
        batch_db_id=batch.id,
        submitter_db_id=user_id
    )
    
    if not event_result:
        raise VoiceCommandError(
            "Failed to create shipment event. Please try again."
        )
    
    # Prepare response
    result = {
        "batch_id": batch.batch_id,
        "destination": destination,
        "quantity_kg": quantity_kg,
        "event_hash": event_result["event_hash"][:16] + "...",
        "ipfs_cid": event_result["ipfs_cid"],
        "blockchain_tx": event_result["blockchain_tx_hash"][:16] + "..." if event_result["blockchain_tx_hash"] else None,
        "message": f"Shipment recorded: {quantity_kg}kg to {destination}"
    }
    
    return (f"Shipment to {destination} recorded successfully", result)


def handle_record_receipt(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_receipt' intent - create receiving event.
    
    Voice examples:
    - "Received batch BATCH-001 at warehouse"
    - "Confirm receipt of 500kg at Addis facility"
    
    Args:
        db: Database session
        entities: {batch_id: str, location: str, condition: str, quantity_kg: float}
        user_id: User database ID
        user_did: User DID (receiver)
        
    Returns:
        Tuple of (success_message, event_dict)
        
    Raises:
        VoiceCommandError: If validation fails
    """
    from voice.epcis.receipt_events import create_receipt_event
    from database.models import CoffeeBatch
    
    # Extract entities
    batch_id = entities.get("batch_id")
    location = entities.get("location", "warehouse")
    condition = entities.get("condition", "good")
    quantity_kg = entities.get("quantity_kg")
    
    # Validate
    if not batch_id:
        raise VoiceCommandError("No batch ID specified. Please specify which batch was received.")
    
    # Get batch from database
    batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
    if not batch:
        raise VoiceCommandError(f"Batch {batch_id} not found")
    
    # Use batch quantity if not specified
    if not quantity_kg:
        quantity_kg = batch.quantity_kg
    
    # Get receiving GLN
    receiving_gln = "0614141000027"  # Default warehouse GLN
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            receiving_gln = get_or_create_user_gln(user_id, db)
        except Exception:
            pass
    
    # Create receipt event
    try:
        event_result = create_receipt_event(
            db=db,
            batch_id=batch.batch_id,
            gtin=batch.gtin,
            receiving_gln=receiving_gln,
            quantity_kg=quantity_kg,
            variety=batch.variety,
            origin=batch.origin,
            receiver_did=user_did or "did:key:unknown",
            condition=condition,
            notes=f"Received at {location}",
            batch_db_id=batch.id,
            submitter_db_id=user_id
        )
        
        if not event_result:
            raise VoiceCommandError("Failed to create receipt event")
        
        message = f"✅ Receipt confirmed for batch {batch_id} ({quantity_kg}kg) - Condition: {condition}"
        return (message, {
            "batch_id": batch_id,
            "quantity_kg": quantity_kg,
            "condition": condition,
            "location": location,
            "status": "RECEIVED",
            "event_hash": event_result.get("event_hash"),
            "ipfs_cid": event_result.get("ipfs_cid"),
            "blockchain_tx": event_result.get("blockchain_tx_hash")
        })
        
    except Exception as e:
        raise VoiceCommandError(f"Receipt failed: {str(e)}")


def handle_record_transformation(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_transformation' intent - process transformation (roasting, milling, etc).
    
    Voice examples:
    - "Roast batch BATCH-001 to produce 850kg roasted coffee"
    - "Mill 1000kg parchment to produce 800kg green coffee"
    
    Note: This is for PROCESSING transformations (roasting, milling).
    For SPLITTING batches, use 'split_batch' intent instead.
    
    Args:
        db: Database session
        entities: {
            input_batch_id: str,
            output_quantity_kg: float,
            output_variety: str,
            transformation_type: str
        }
        user_id: User database ID
        user_did: User DID
        
    Returns:
        Tuple of (success_message, result_dict)
        
    Raises:
        VoiceCommandError: If validation fails
    """
    from voice.epcis.transformation_events import create_transformation_event
    from database.models import CoffeeBatch
    
    # Extract entities
    input_batch_id = entities.get("input_batch_id") or entities.get("batch_id")
    output_quantity = entities.get("output_quantity_kg") or entities.get("quantity_kg")
    output_variety = entities.get("output_variety") or entities.get("product")
    transformation_type = entities.get("transformation_type", "processing")
    
    # Validate
    if not input_batch_id:
        raise VoiceCommandError("No input batch specified. Please specify which batch to transform.")
    
    if not output_quantity:
        raise VoiceCommandError("No output quantity specified. Example: '850kg roasted coffee'")
    
    # Get input batch
    input_batch = db.query(CoffeeBatch).filter(
        CoffeeBatch.batch_id == input_batch_id
    ).first()
    
    if not input_batch:
        raise VoiceCommandError(f"Input batch {input_batch_id} not found")
    
    # Validate transformation is reasonable (allow 10-30% mass loss for roasting/milling)
    mass_loss_pct = ((input_batch.quantity_kg - output_quantity) / input_batch.quantity_kg) * 100
    if mass_loss_pct < 0:
        raise VoiceCommandError(
            f"Output quantity ({output_quantity}kg) cannot exceed input ({input_batch.quantity_kg}kg)"
        )
    if mass_loss_pct > 40:
        raise VoiceCommandError(
            f"Mass loss of {mass_loss_pct:.1f}% seems too high. "
            f"Typical processing losses are 10-30%. Please verify quantities."
        )
    
    # Generate output batch ID
    # Generate shorter output batch ID to fit 50-char database limit
    # Trim parent ID if too long to ensure final ID < 50 chars
    # Format: PARENT-TYPE-TIME (e.g., YRG_2025_001-RST-074111)
    timestamp = datetime.utcnow().strftime("%H%M%S")
    type_abbr = transformation_type[:3].upper()  # RST, MIL, DRY, etc.
    
    # Reserve 11 chars for suffix: "-RST-074111" = 11 chars
    # Parent ID max: 50 - 11 = 39 chars
    max_parent_len = 39
    parent_id = input_batch_id[:max_parent_len] if len(input_batch_id) > max_parent_len else input_batch_id
    output_batch_id = f"{parent_id}-{type_abbr}-{timestamp}"
    
    # Determine output variety based on transformation
    if not output_variety:
        if "roast" in transformation_type.lower():
            output_variety = f"{input_batch.variety} Roasted"
        elif "mill" in transformation_type.lower():
            output_variety = f"{input_batch.variety} Milled"
        else:
            output_variety = f"{input_batch.variety} Processed"
    
    # Get user's GLN
    location_gln = input_batch.gln or "0614141000010"
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            location_gln = get_or_create_user_gln(user_id, db)
        except Exception:
            pass
    
    # Create transformation event
    try:
        result = create_transformation_event(
            db=db,
            input_batch_id=input_batch_id,
            output_batches=[{
                "batch_id": output_batch_id,
                "quantity_kg": output_quantity,
                "variety": output_variety
            }],
            transformation_type=transformation_type,
            location_gln=location_gln,
            operator_did=user_did or input_batch.created_by_did or "did:key:unknown",
            notes=f"Processing transformation: {input_batch.quantity_kg}kg {input_batch.variety} → "
                  f"{output_quantity}kg {output_variety} (mass loss: {mass_loss_pct:.1f}%)"
        )
        
        if not result:
            raise VoiceCommandError("Failed to create transformation event")
        
        message = (f"✅ Transformation complete: {input_batch.quantity_kg}kg → {output_quantity}kg "
                   f"({transformation_type}, {mass_loss_pct:.1f}% loss)")
        return (message, {
            "input_batch_id": input_batch_id,
            "output_batch_ids": result["output_batch_ids"],
            "transformation_type": transformation_type,
            "mass_loss_percent": round(mass_loss_pct, 1),
            "transformation_id": result["transformation_id"],
            "event_hash": result["event_hash"],
            "ipfs_cid": result["ipfs_cid"],
            "blockchain_tx": result["blockchain_tx_hash"]
        })
        
    except Exception as e:
        raise VoiceCommandError(f"Transformation failed: {str(e)}")


def handle_pack_batches(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'pack_batches' intent - aggregate batches into container.
    
    Voice examples:
    - "Pack batches 001, 002, 003 into container C100"
    - "Load batches A, B, C onto pallet P50"
    
    Args:
        db: Database session
        entities: {batch_ids: list, container_id: str, container_type: str}
        user_id: User database ID
        user_did: User DID
        
    Returns:
        Tuple of (success_message, event_dict)
        
    Raises:
        VoiceCommandError: If validation fails
    """
    from voice.epcis.aggregation_events import create_aggregation_event
    from gs1.sscc import generate_sscc
    
    # Extract entities
    batch_ids = entities.get("batch_ids", [])
    container_id = entities.get("container_id")
    container_type = entities.get("container_type", "pallet")
    
    # Validate
    if not batch_ids:
        raise VoiceCommandError("No batch IDs specified. Please specify which batches to pack.")
    
    if len(batch_ids) < 2:
        raise VoiceCommandError("Need at least 2 batches to pack. For single batch, use shipment instead.")
    
    # Generate SSCC if not provided
    if not container_id:
        extension = "3" if container_type == "pallet" else "9"
        container_id = generate_sscc(extension=extension)
    
    # Get user's GLN for location
    location_gln = "0614141000010"  # Default
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            location_gln = get_or_create_user_gln(user_id, db)
        except Exception:
            pass
    
    # Create aggregation event
    try:
        event_result = create_aggregation_event(
            db=db,
            parent_sscc=container_id,
            child_batch_ids=batch_ids,
            action="ADD",
            biz_step="packing",
            location_gln=location_gln,
            operator_did=user_did or "did:key:unknown"
        )
        
        if not event_result:
            raise VoiceCommandError("Failed to create aggregation event")
        
        message = f"✅ Packed {len(batch_ids)} batches into container {container_id}"
        return (message, {
            "container_id": container_id,
            "batch_ids": batch_ids,
            "event_hash": event_result.get("event_hash"),
            "ipfs_cid": event_result.get("ipfs_cid"),
            "blockchain_tx": event_result.get("blockchain_tx_hash")
        })
        
    except Exception as e:
        raise VoiceCommandError(f"Packing failed: {str(e)}")


def handle_unpack_batches(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'unpack_batches' intent - disaggregate container.
    
    Voice examples:
    - "Unpack container C100"
    - "Unload pallet P50"
    
    Args:
        db: Database session
        entities: {container_id: str}
        user_id: User database ID
        user_did: User DID
        
    Returns:
        Tuple of (success_message, event_dict)
        
    Raises:
        VoiceCommandError: If validation fails
    """
    from voice.epcis.aggregation_events import create_aggregation_event
    from database.models import AggregationRelationship
    
    # Extract entities
    container_id = entities.get("container_id")
    
    # Validate
    if not container_id:
        raise VoiceCommandError("No container ID specified. Please specify which container to unpack.")
    
    # Get batches in container
    relationships = db.query(AggregationRelationship).filter(
        AggregationRelationship.parent_sscc == container_id,
        AggregationRelationship.is_active == True
    ).all()
    
    if not relationships:
        raise VoiceCommandError(f"Container {container_id} is empty or not found")
    
    batch_ids = [rel.child_identifier for rel in relationships]
    
    # Get user's GLN
    location_gln = "0614141000010"
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            location_gln = get_or_create_user_gln(user_id, db)
        except Exception:
            pass
    
    # Create disaggregation event
    try:
        event_result = create_aggregation_event(
            db=db,
            parent_sscc=container_id,
            child_batch_ids=batch_ids,
            action="DELETE",
            biz_step="unpacking",
            location_gln=location_gln,
            operator_did=user_did or "did:key:unknown"
        )
        
        if not event_result:
            raise VoiceCommandError("Failed to create disaggregation event")
        
        message = f"✅ Unpacked {len(batch_ids)} batches from container {container_id}"
        return (message, {
            "container_id": container_id,
            "batch_ids": batch_ids,
            "event_hash": event_result.get("event_hash"),
            "ipfs_cid": event_result.get("ipfs_cid"),
            "blockchain_tx": event_result.get("blockchain_tx_hash")
        })
        
    except Exception as e:
        raise VoiceCommandError(f"Unpacking failed: {str(e)}")


def handle_split_batch(db: Session, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'split_batch' intent - split batch into multiple child batches.
    
    Voice examples:
    - "Split batch BATCH-001 into 6000kg for EU and 4000kg for US"
    - "Divide batch ABC into 60 percent and 40 percent"
    
    Args:
        db: Database session
        entities: {batch_id: str, splits: [{quantity_kg: float, destination: str}]}
        user_id: User database ID
        user_did: User DID
        
    Returns:
        Tuple of (success_message, result_dict)
        
    Raises:
        VoiceCommandError: If validation fails
    """
    from voice.epcis.transformation_events import create_transformation_event
    from database.models import CoffeeBatch
    
    # Extract entities
    parent_batch_id = entities.get("batch_id")
    splits = entities.get("splits", [])
    
    # Validate
    if not parent_batch_id:
        raise VoiceCommandError("No batch ID specified. Please specify which batch to split.")
    
    if not splits or len(splits) < 2:
        raise VoiceCommandError("Need at least 2 split quantities. Example: '6000kg and 4000kg'")
    
    # Get parent batch
    parent_batch = db.query(CoffeeBatch).filter(
        CoffeeBatch.batch_id == parent_batch_id
    ).first()
    
    if not parent_batch:
        raise VoiceCommandError(f"Batch {parent_batch_id} not found")
    
    # Generate child batch IDs
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    output_batches = []
    
    for idx, split in enumerate(splits):
        quantity = split.get("quantity_kg")
        destination = split.get("destination", chr(65 + idx))  # A, B, C...
        
        child_id = f"{parent_batch_id}-{destination}-{timestamp}"
        output_batches.append({
            "batch_id": child_id,
            "quantity_kg": quantity
        })
    
    # Get user's GLN
    location_gln = parent_batch.gln or "0614141000010"
    if user_id:
        try:
            from ssi.user_identity import get_or_create_user_gln
            location_gln = get_or_create_user_gln(user_id, db)
        except Exception:
            pass
    
    # Create transformation event
    try:
        result = create_transformation_event(
            db=db,
            input_batch_id=parent_batch_id,
            output_batches=output_batches,
            transformation_type="split",
            location_gln=location_gln,
            operator_did=user_did or parent_batch.created_by_did or "did:key:unknown",
            notes=f"Split via voice command: {parent_batch.quantity_kg}kg → " + 
                  " + ".join([f"{b['quantity_kg']}kg" for b in output_batches])
        )
        
        if not result:
            raise VoiceCommandError("Failed to create split transformation")
        
        message = f"✅ Split {parent_batch_id} ({parent_batch.quantity_kg}kg) into {len(output_batches)} batches"
        return (message, {
            "parent_batch_id": parent_batch_id,
            "child_batch_ids": result["output_batch_ids"],
            "transformation_id": result["transformation_id"],
            "event_hash": result["event_hash"],
            "ipfs_cid": result["ipfs_cid"],
            "blockchain_tx": result["blockchain_tx_hash"]
        })
        
    except Exception as e:
        raise VoiceCommandError(f"Split failed: {str(e)}")


# Intent to handler mapping
INTENT_HANDLERS = {
    "record_commission": handle_record_commission,
    "record_shipment": handle_record_shipment,
    "record_receipt": handle_record_receipt,
    "record_transformation": handle_record_transformation,
    "pack_batches": handle_pack_batches,
    "unpack_batches": handle_unpack_batches,
    "split_batch": handle_split_batch,
}


def execute_voice_command(db: Session, intent: str, entities: dict, user_id: int = None, user_did: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Execute voice command by mapping intent to database operation.
    
    Args:
        db: Database session
        intent: Intent extracted from NLU
        entities: Entities extracted from NLU
        user_id: Optional user database ID (for VC issuance)
        user_did: Optional user DID (for batch ownership)
        
    Returns:
        Tuple of (success_message, result_dict)
        
    Raises:
        VoiceCommandError: If intent unknown or execution fails
        
    Example:
        >>> message, result = execute_voice_command(
        ...     db,
        ...     "record_commission",
        ...     {"quantity": 50, "origin": "Abebe", "product": "Arabica"}
        ... )
        >>> print(message)
        "Batch created successfully"
        >>> print(result["batch_id"])
        "ABEBE_ARABICA_20251214"
    """
    # Validate intent
    if not intent or intent not in INTENT_HANDLERS:
        raise VoiceCommandError(
            f"Could not understand your command (intent: {intent}).\n\n"
            f"Please describe what you want to do:\n"
            f"• 'New batch of 50 kg...' - Create new batch\n"
            f"• 'Shipped batch ABC...' - Send existing batch\n"
            f"• 'Received batch XYZ...' - Receive batch\n"
            f"• 'Washed batch DEF...' - Process coffee"
        )
    
    # Get handler for this intent
    handler = INTENT_HANDLERS[intent]
    
    # Execute handler
    try:
        # Pass user context to handlers that support it
        if intent == "record_commission":
            message, result = handler(db, entities, user_id=user_id, user_did=user_did)
        elif intent == "record_shipment":
            message, result = handler(db, entities, user_id=user_id)
        else:
            message, result = handler(db, entities)
        return (message, result)
    except VoiceCommandError:
        # Re-raise voice command errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        raise VoiceCommandError(f"Command execution failed: {str(e)}")


if __name__ == "__main__":
    """Test voice command integration."""
    print("Voice Command Integration Module")
    print("=" * 50)
    print("\nSupported Intents:")
    for intent in INTENT_HANDLERS.keys():
        print(f"  - {intent}")
    print("\nThis module maps voice commands to database operations.")
    print("Use via /voice/process-command API endpoint.")
