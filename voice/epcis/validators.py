"""
EPCIS Event Validators

Validation logic for aggregation and transformation events to ensure:
1. Mass balance compliance (transformations)
2. Batch existence verification
3. No duplicate aggregations
4. EUDR compliance (geolocation requirements)

Part of Aggregation Implementation Roadmap - Section 1.3
"""

from typing import Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import CoffeeBatch, AggregationRelationship, FarmerIdentity
from database.connection import get_db


def validate_mass_balance(
    input_quantities: List[Dict[str, Any]],
    output_quantities: List[Dict[str, Any]],
    tolerance_percent: float = 0.1,
    allow_loss: bool = False
) -> Tuple[bool, str]:
    """
    Validate mass balance for TransformationEvents.
    
    EUDR and supply chain integrity require that mass is conserved during
    batch splits/transformations. Input quantities must equal output quantities
    within a small tolerance (0.1% to account for rounding).
    
    For processing transformations (roasting, milling), set allow_loss=True
    to permit output < input (but not output > input).
    
    Example valid split:
      Input: 10,000.0 kg
      Output: 6,000.0 kg + 4,000.0 kg = 10,000.0 kg ✅
    
    Example invalid split:
      Input: 10,000.0 kg
      Output: 6,000.0 kg + 5,000.0 kg = 11,000.0 kg ❌
    
    Example valid processing (allow_loss=True):
      Input: 1,000.0 kg green coffee
      Output: 850.0 kg roasted coffee ✅ (15% loss)
    
    Args:
        input_quantities: List of dicts with 'quantity' and 'uom' keys
        output_quantities: List of dicts with 'quantity' and 'uom' keys
        tolerance_percent: Acceptable variance (default 0.1% = 10kg for 10,000kg)
        allow_loss: If True, allow output < input (for processing transformations)
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    # Sum input quantities
    total_input = sum(float(q.get('quantity', 0)) for q in input_quantities)
    
    # Sum output quantities
    total_output = sum(float(q.get('quantity', 0)) for q in output_quantities)
    
    # Check if all UOMs are the same
    input_uoms = {q.get('uom', 'KGM') for q in input_quantities}
    output_uoms = {q.get('uom', 'KGM') for q in output_quantities}
    
    if len(input_uoms) > 1 or len(output_uoms) > 1:
        return False, "Mixed units of measure - all quantities must use same UOM"
    
    if input_uoms != output_uoms:
        return False, f"Input UOM {input_uoms} does not match output UOM {output_uoms}"
    
    # Calculate tolerance
    tolerance = total_input * (tolerance_percent / 100)
    difference = total_input - total_output
    
    if allow_loss:
        # For processing transformations, output can be less than input (mass loss)
        # but output should never exceed input
        if difference < -tolerance:  # output > input (accounting for tolerance)
            return False, (
                f"Mass balance violation: Output {total_output} exceeds input {total_input} "
                f"(difference: {abs(difference)}, tolerance: {tolerance})"
            )
        # Output less than input is OK (natural mass loss during processing)
        return True, ""
    else:
        # For splits, require exact balance
        if abs(difference) > tolerance:
            return False, (
                f"Mass balance violation: Input {total_input} != Output {total_output} "
                f"(difference: {abs(difference)}, tolerance: {tolerance})"
            )
        return True, ""


def validate_batch_existence(
    batch_ids: List[str],
    db: Session
) -> Tuple[bool, str]:
    """
    Verify all child batches exist in database before aggregation.
    
    Prevents aggregating non-existent batches which would create invalid
    supply chain records and break EUDR traceability requirements.
    
    Args:
        batch_ids: List of batch identifiers to validate
        db: Database session
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not batch_ids:
        return False, "No batch IDs provided"
    
    # Query database for all batch IDs
    existing_batches = db.query(CoffeeBatch.batch_id).filter(
        CoffeeBatch.batch_id.in_(batch_ids)
    ).all()
    
    existing_ids = {batch.batch_id for batch in existing_batches}
    missing_ids = set(batch_ids) - existing_ids
    
    if missing_ids:
        return False, f"Batches do not exist: {', '.join(sorted(missing_ids))}"
    
    return True, ""


def validate_no_duplicate_aggregation(
    batch_id: str,
    db: Session
) -> Tuple[bool, str]:
    """
    Prevent same batch from being in multiple active containers simultaneously.
    
    A batch can only be in one container at a time (no quantum coffee). This
    enforces physical reality and prevents double-counting in supply chain.
    
    A batch can be:
    - Not aggregated (available for packing)
    - In one active container (aggregated)
    - Previously aggregated but now disaggregated (available again)
    
    Args:
        batch_id: Batch identifier to check
        db: Database session
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    # Check if batch is currently in an active aggregation
    active_aggregation = db.query(AggregationRelationship).filter(
        AggregationRelationship.child_identifier == batch_id,
        AggregationRelationship.is_active == True
    ).first()
    
    if active_aggregation:
        return False, (
            f"Batch {batch_id} is already in active container "
            f"{active_aggregation.parent_sscc}. Disaggregate first before re-aggregating."
        )
    
    return True, ""


def validate_eudr_compliance(
    batch_ids: List[str],
    db: Session
) -> Tuple[bool, str]:
    """
    Full EUDR compliance check for batches (Articles 9 + 10).

    Validates:
      1. Article 9 – GPS coordinates exist for every farmer
      2. Article 9 – GPS is photo-verified (not just self-reported)
      3. Article 10 – Deforestation check has been run AND passed

    Args:
        batch_ids: List of batch identifiers to validate
        db: Database session

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not batch_ids:
        return False, "No batch IDs provided"

    # Query batches with farmer relationships
    batches = db.query(CoffeeBatch).filter(
        CoffeeBatch.batch_id.in_(batch_ids)
    ).all()

    missing_gps = []
    unverified_gps = []
    deforestation_fail = []

    for batch in batches:
        farmer = batch.farmer
        if not farmer:
            missing_gps.append(f"{batch.batch_id} (no farmer linked)")
            continue

        # 1. Must have ANY coordinates
        if farmer.latitude is None or farmer.longitude is None:
            missing_gps.append(f"{farmer.name} (batch {batch.batch_id})")
            continue

        # 2. Prefer photo-verified GPS; flag if only self-reported
        if farmer.photo_latitude is None or farmer.photo_longitude is None or farmer.gps_verified_at is None:
            unverified_gps.append(f"{farmer.name} (batch {batch.batch_id})")

        # 3. Deforestation check must have run AND returned compliant=True
        if farmer.deforestation_compliant is not True:
            risk = farmer.deforestation_risk or 'NOT_CHECKED'
            deforestation_fail.append(
                f"{farmer.name} (batch {batch.batch_id}, risk={risk})"
            )

    # Build combined error message
    issues = []
    if missing_gps:
        issues.append(
            f"Missing geolocation: {', '.join(missing_gps)}"
        )
    if unverified_gps:
        issues.append(
            f"GPS not photo-verified (self-reported only): {', '.join(unverified_gps)}"
        )
    if deforestation_fail:
        issues.append(
            f"Deforestation check failed or not run: {', '.join(deforestation_fail)}"
        )

    if issues:
        return False, (
            "EUDR compliance issues found - "
            + "; ".join(issues)
            + ". (EU Regulation 2023/1115 Articles 9 & 10)"
        )

    return True, ""


def validate_aggregation_event(
    action: str,
    parent_sscc: str,
    child_batch_ids: List[str],
    db: Session
) -> Tuple[bool, str]:
    """
    Master validator for aggregation events.
    
    Runs all applicable validators and returns first failure encountered.
    Use this as the entry point before creating aggregation events.
    
    Args:
        action: 'ADD' or 'DELETE'
        parent_sscc: Container SSCC identifier
        child_batch_ids: List of batch IDs being aggregated
        db: Database session
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    # Validate batch existence
    is_valid, error_msg = validate_batch_existence(child_batch_ids, db)
    if not is_valid:
        return False, f"Batch existence validation failed: {error_msg}"
    
    # For ADD actions, check for duplicate aggregations and EUDR compliance
    if action == "ADD":
        # Check each batch isn't already aggregated
        for batch_id in child_batch_ids:
            is_valid, error_msg = validate_no_duplicate_aggregation(batch_id, db)
            if not is_valid:
                return False, f"Duplicate aggregation validation failed: {error_msg}"
        
        # Check EUDR compliance
        is_valid, error_msg = validate_eudr_compliance(child_batch_ids, db)
        if not is_valid:
            return False, f"EUDR compliance validation failed: {error_msg}"
    
    return True, ""


def validate_transformation_event(
    input_quantities: List[Dict[str, Any]],
    output_quantities: List[Dict[str, Any]],
    input_batch_ids: List[str],
    output_batch_ids: List[str],
    db: Session,
    allow_loss: bool = False
) -> Tuple[bool, str]:
    """
    Master validator for transformation events (batch splits and processing).
    
    Validates:
    1. Mass balance (input = output, or input > output if allow_loss=True)
    2. Input batches exist
    3. Output batch IDs are unique (not duplicates)
    4. EUDR compliance inherited from parent (ALWAYS validated)
    
    Args:
        input_quantities: List of input quantity dicts
        output_quantities: List of output quantity dicts
        input_batch_ids: List of input batch IDs
        output_batch_ids: List of output batch IDs being created
        db: Database session
        allow_loss: If True, allow output < input (for processing transformations)
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    # Validate mass balance
    is_valid, error_msg = validate_mass_balance(
        input_quantities, 
        output_quantities,
        allow_loss=allow_loss
    )
    if not is_valid:
        return False, f"Mass balance validation failed: {error_msg}"
    
    # Validate input batches exist
    is_valid, error_msg = validate_batch_existence(input_batch_ids, db)
    if not is_valid:
        return False, f"Input batch validation failed: {error_msg}"
    
    # Validate output batch IDs don't already exist
    existing_outputs = db.query(CoffeeBatch.batch_id).filter(
        CoffeeBatch.batch_id.in_(output_batch_ids)
    ).all()
    
    if existing_outputs:
        existing_ids = [b.batch_id for b in existing_outputs]
        return False, f"Output batch IDs already exist: {', '.join(existing_ids)}"
    
    # Validate parent EUDR compliance
    # EUDR compliance is MANDATORY for all transformations (EU Regulation 2023/1115)
    # Both splits and processing transformations maintain supply chain traceability
    is_valid, error_msg = validate_eudr_compliance(input_batch_ids, db)
    if not is_valid:
        return False, f"Parent EUDR compliance validation failed: {error_msg}"
    
    return True, ""
