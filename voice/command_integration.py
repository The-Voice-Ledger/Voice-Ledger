"""
Voice Command to Database Integration

This module maps voice command intents to database operations.
It handles entity validation, required field generation, and CRUD execution.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.crud import create_batch, create_event, get_farmer_by_farmer_id, get_batch_by_batch_id, get_batch_by_id_or_gtin, get_batch_by_id_or_gtin
from sqlalchemy.orm import Session

# Import GS1 and EPCIS utilities
from gs1.identifiers import gtin as generate_gtin, sscc as generate_sscc
import hashlib
import json


class VoiceCommandError(Exception):
    """Raised when voice command cannot be executed."""
    pass


# Required entities for each intent
REQUIRED_ENTITIES = {
    "record_commission": {
        "required": ["quantity", "origin"],
        "optional": ["product", "unit"],
        "description": "Create a new coffee batch",
        "example": "Record commission of 50 bags from Abebe farm"
    },
    "record_shipment": {
        "required": ["batch_id", "destination"],
        "optional": ["quantity_kg", "carrier", "transport_mode"],
        "description": "Ship an existing batch",
        "example": "Ship batch ABC-123 to Addis Ababa warehouse"
    },
    "record_receipt": {
        "required": ["batch_id"],
        "optional": ["source_location", "condition"],
        "description": "Receive a shipped batch",
        "example": "Received batch ABC-123 from Jimma"
    },
    "record_transformation": {
        "required": ["batch_id", "process_type"],
        "optional": ["output_quantity", "output_product"],
        "description": "Process coffee (washing, drying, etc.)",
        "example": "Washed batch ABC-123 at processing facility"
    },
    "pack_batches": {
        "required": ["batch_ids"],
        "optional": ["container_type"],
        "description": "Pack multiple batches into container",
        "example": "Pack batches ABC-123 and DEF-456 into shipping container"
    },
    "aggregate_batches": {  # Alias
        "required": ["batch_ids"],
        "optional": ["container_type"],
        "description": "Pack multiple batches into container",
        "example": "Pack batches ABC-123 and DEF-456 into shipping container"
    },
    "unpack_batches": {
        "required": ["container_id"],
        "optional": [],
        "description": "Unpack container to release batches",
        "example": "Unpack container SSCC-789"
    },
    "disaggregate_batches": {  # Alias
        "required": ["container_id"],
        "optional": [],
        "description": "Unpack container to release batches",
        "example": "Unpack container SSCC-789"
    },
    "split_batch": {
        "required": ["parent_batch_id", "splits"],
        "optional": [],
        "description": "Split one batch into multiple smaller batches",
        "example": "Split batch ABC-123 into 6000kg and 4000kg"
    }
}


def validate_entities(intent: str, entities: Dict[str, Any]) -> Tuple[bool, list]:
    """
    Validate if all required entities are present for the given intent.
    
    Args:
        intent: The intent to validate entities for
        entities: Dictionary of extracted entities
        
    Returns:
        Tuple of (is_valid, missing_entities)
        - is_valid: True if all required entities present, False otherwise
        - missing_entities: List of missing required entity names
        
    Example:
        >>> is_valid, missing = validate_entities("record_commission", {"quantity": 50})
        >>> print(is_valid, missing)
        False ['origin']
    """
    if intent not in REQUIRED_ENTITIES:
        # Unknown intent - let execute_voice_command handle it
        return True, []
    
    intent_spec = REQUIRED_ENTITIES[intent]
    required_fields = intent_spec["required"]
    
    # Check for missing required entities
    missing = []
    for field in required_fields:
        value = entities.get(field)
        # Consider empty strings, empty lists, and None as missing
        if value is None or (isinstance(value, (str, list)) and not value):
            missing.append(field)
    
    is_valid = len(missing) == 0
    return is_valid, missing


def generate_clarification_question(intent: str, missing_entities: list) -> str:
    """
    Generate a natural, helpful clarification question for missing entities.
    
    Args:
        intent: The intent being executed
        missing_entities: List of missing required entity names
        
    Returns:
        A natural language question asking for the missing information
        
    Example:
        >>> q = generate_clarification_question("record_commission", ["origin"])
        >>> print(q)
        "I need more information to create a new batch. Where is the coffee from?"
    """
    if intent not in REQUIRED_ENTITIES:
        return "I need more information to complete this action. Could you provide more details?"
    
    intent_spec = REQUIRED_ENTITIES[intent]
    description = intent_spec["description"]
    example = intent_spec["example"]
    
    # Map entity names to natural language questions
    entity_questions = {
        "quantity": "How much coffee (quantity and unit)?",
        "origin": "Where is the coffee from (farm or location)?",
        "batch_id": "Which batch (use batch ID or GTIN)?",
        "destination": "Where is it being shipped to?",
        "process_type": "What type of processing (washing, drying, roasting)?",
        "batch_ids": "Which batches should be packed (provide batch IDs)?",
        "container_id": "Which container (SSCC or container ID)?",
        "parent_batch_id": "Which batch should be split?",
        "splits": "How should it be split (quantities for each part)?",
        "product": "What type of coffee?",
        "unit": "What unit (bags, kg)?",
        "carrier": "Who is the carrier?",
        "transport_mode": "How is it being transported (truck, ship, air)?",
        "source_location": "Where was it shipped from?",
        "condition": "What is the condition of the batch?",
        "output_quantity": "What is the output quantity after processing?",
        "output_product": "What is the product after processing?",
        "container_type": "What type of container?"
    }
    
    # Build clarification message
    questions = [entity_questions.get(entity, f"What is the {entity}?") 
                 for entity in missing_entities]
    
    if len(missing_entities) == 1:
        question_text = questions[0]
    elif len(missing_entities) == 2:
        question_text = f"{questions[0]} Also, {questions[1].lower()}"
    else:
        question_text = ", ".join(questions[:-1]) + f", and {questions[-1].lower()}"
    
    clarification = (
        f"I need more information to {description.lower()}. {question_text}\n\n"
        f"For example: '{example}'"
    )
    
    return clarification


def generate_batch_id_from_entities(entities: dict) -> str:
    """
    Generate a unique batch_id from voice command entities.
    
    Format: FARMER_PRODUCT_TIMESTAMP (max 50 chars for DB)
    Example: ABEBE_ARABICA_20251214_143025
    
    Args:
        entities: Extracted entities from NLU
        
    Returns:
        Generated batch_id (unique per second, max 50 characters)
    """
    origin = entities.get("origin")
    if not origin or origin.upper() == "UNKNOWN":
        origin = entities.get("farmer_origin", "UNKNOWN")
    
    origin = origin.upper().replace(" ", "_")[:16]
    product = entities.get("product", "COFFEE").upper().replace(" ", "_")[:17]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
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
    # 1. Resolve Farmer Identity first for smart defaults
    from database.models import FarmerIdentity, UserIdentity
    farmer = None
    if user_did:
        farmer = db.query(FarmerIdentity).filter_by(did=user_did).first()
    if not farmer and user_id:
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if user and user.did:
            farmer = db.query(FarmerIdentity).filter_by(did=user.did).first()
    
    # Extract entities
    quantity = entities.get("quantity")
    origin = entities.get("origin")
    
    # Smart Default: Auto-populate origin from farmer registration if missing
    if (not origin or origin.lower() == "unknown") and farmer:
        origin = f"{farmer.region}, {farmer.country_code}"
        entities["farmer_origin"] = farmer.region # For batch_id generation
        entities["origin"] = origin
    
    if not origin:
        origin = "Unknown"

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
        "farmer_id": farmer.id if farmer else None, # SMART LINK: Associate with farmer profile
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
        
        # Find farmer identity for EPCIS events (submitter_id must reference farmer_identities.id)
        submitter_farmer_id = farmer.id if farmer else None
        
        if not submitter_farmer_id:
            # Fallback for backward compatibility or missing profiles
            from database.models import FarmerIdentity
            farmer_identity = db.query(FarmerIdentity).filter_by(farmer_id=f"FARMER-{user_id}").first()
            submitter_farmer_id = farmer_identity.id if farmer_identity else None
        
        if not submitter_farmer_id:
            raise VoiceCommandError(f"Farmer identity not found for user {user_id}. Please register your farm first.")
        
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
            submitter_db_id=submitter_farmer_id
        )
        
        # NOTE: Token minting happens AFTER cooperative verification
        # See voice/telegram/verification_handler.py::_process_verification()
        # This prevents unverified batches from getting on-chain representation
        
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
        # Explicit batch_id or GTIN provided
        batch = get_batch_by_id_or_gtin(db, batch_id)
        if not batch:
            raise VoiceCommandError(
                f"Batch '{batch_id}' not found. Use GTIN (e.g., 00614141852251) or batch_id."
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
    
    # Get batch from database using GTIN or batch_id
    batch = get_batch_by_id_or_gtin(db, batch_id)
    if not batch:
        raise VoiceCommandError(f"Batch {batch_id} not found. Use GTIN (e.g., 00614141852251) or batch_id.")
    
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
    
    # Get input batch (accepts GTIN or batch_id)
    from database.crud import get_batch_by_id_or_gtin
    input_batch = get_batch_by_id_or_gtin(db, input_batch_id)
    
    if not input_batch:
        raise VoiceCommandError(
            f"Batch '{input_batch_id}' not found. "
            f"Use GTIN (e.g., 00614141852251) or batch_id"
        )
    
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
        
        # ========== PHASE 2: Mint Container Token ==========
        # Get child token IDs and holders from database
        from database.crud import get_batch_by_batch_id
        from blockchain.token_manager import mint_container_token
        
        child_token_ids = []
        child_holders = []
        total_quantity_kg = 0.0
        
        for batch_id in batch_ids:
            batch = get_batch_by_batch_id(db, batch_id)
            if not batch:
                print(f"⚠️ Warning: Batch {batch_id} not found in database")
                continue
            
            if not batch.token_id:
                print(f"⚠️ Warning: Batch {batch_id} has no token_id (not minted yet)")
                continue
            
            # Get holder address (use cooperative master wallet)
            # All tokens are minted to the cooperative master wallet
            from blockchain.token_manager import get_token_manager
            manager = get_token_manager()
            holder_address = manager.account.address
            
            child_token_ids.append(batch.token_id)
            child_holders.append(holder_address)
            total_quantity_kg += batch.quantity_kg or 0.0
        
        # Mint container token on blockchain
        container_token_id = None
        if len(child_token_ids) >= 2:
            # Get recipient (use cooperative master wallet)
            from blockchain.token_manager import get_token_manager
            manager = get_token_manager()
            recipient_address = manager.account.address
            
            # Build metadata
            metadata = {
                "container_id": container_id,
                "container_type": container_type,
                "child_batch_ids": batch_ids,
                "total_quantity_kg": total_quantity_kg,
                "packed_at": event_result.get("event_time"),
                "location_gln": location_gln,
                "operator_did": user_did or "did:key:unknown"
            }
            
            # Mint container token
            try:
                container_token_id = mint_container_token(
                    recipient=recipient_address,
                    quantity_kg=total_quantity_kg,
                    container_id=container_id,
                    metadata=metadata,
                    ipfs_cid=event_result.get("ipfs_cid", ""),
                    child_token_ids=child_token_ids,
                    child_holders=child_holders
                )
                
                if container_token_id:
                    print(f"✅ Container token minted: Token ID {container_token_id}")
                    
                    # Store container token ID in aggregation_relationships table
                    from database.models import AggregationRelationship
                    agg_rel = db.query(AggregationRelationship).filter_by(
                        parent_sscc=container_id
                    ).first()
                    
                    if agg_rel:
                        agg_rel.container_token_id = container_token_id
                        db.commit()
                        print(f"✅ Stored container token ID in database")
                else:
                    print("⚠️ Container token minting returned None")
                    
            except Exception as e:
                print(f"⚠️ Container token minting failed: {e}")
                # Don't fail the entire operation if blockchain fails
        else:
            print(f"⚠️ Only {len(child_token_ids)} child tokens found, need at least 2 for container minting")
        # ===================================================
        
        message = f"✅ Packed {len(batch_ids)} batches into container {container_id}"
        result_data = {
            "container_id": container_id,
            "batch_ids": batch_ids,
            "event_hash": event_result.get("event_hash"),
            "ipfs_cid": event_result.get("ipfs_cid"),
            "blockchain_tx": event_result.get("blockchain_tx_hash")
        }
        
        if container_token_id:
            result_data["container_token_id"] = container_token_id
            message += f" (Token ID: {container_token_id})"
        
        return (message, result_data)
        
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
    
    # Get parent batch using GTIN or batch_id
    parent_batch = get_batch_by_id_or_gtin(db, parent_batch_id)
    
    if not parent_batch:
        raise VoiceCommandError(f"Batch {parent_batch_id} not found. Use GTIN (e.g., 00614141852251) or batch_id.")
    
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
    "aggregate_batches": handle_pack_batches,  # Alias for conversational AI
    "unpack_batches": handle_unpack_batches,
    "disaggregate_batches": handle_unpack_batches,  # Alias for conversational AI
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
    
    # Validate entities before executing handler
    is_valid, missing_entities = validate_entities(intent, entities)
    if not is_valid:
        clarification = generate_clarification_question(intent, missing_entities)
        raise VoiceCommandError(clarification)
    
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
