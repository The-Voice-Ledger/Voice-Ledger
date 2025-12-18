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
    from database.crud import get_user
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
    
    # Get user's DID for shipper identification
    user = get_user(db, user_id) if user_id else None
    shipper_did = user.did if user and hasattr(user, 'did') else "did:example:shipper"
    
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


def handle_record_receipt(db: Session, entities: dict) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_receipt' intent - create receiving event.
    
    Voice example: "Received 50 bags at Addis warehouse"
    
    Args:
        db: Database session
        entities: {batch_id, quantity, destination}
        
    Returns:
        Tuple of (success_message, created_event_dict)
        
    Raises:
        VoiceCommandError: If required entities missing or batch not found
    """
    raise VoiceCommandError(
        "Receipt events require an existing batch. "
        "Please commission a batch first, then record receipt."
    )


def handle_record_transformation(db: Session, entities: dict) -> Tuple[str, Dict[str, Any]]:
    """
    Handle 'record_transformation' intent - create transformation event.
    
    Voice example: "Transform 100kg green coffee to 85kg roasted"
    
    Args:
        db: Database session
        entities: {batch_id, quantity, product}
        
    Returns:
        Tuple of (success_message, created_event_dict)
        
    Raises:
        VoiceCommandError: If required entities missing
    """
    raise VoiceCommandError(
        "Transformation events require existing input batches. "
        "Not yet implemented in Phase 1b."
    )


# Intent to handler mapping
INTENT_HANDLERS = {
    "record_commission": handle_record_commission,
    "record_shipment": handle_record_shipment,
    "record_receipt": handle_record_receipt,
    "record_transformation": handle_record_transformation,
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
