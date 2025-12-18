"""
Verification Event Creation

Creates EPCIS verification events that are:
1. Stored in database
2. Pinned to IPFS
3. Anchored to blockchain

This provides immutable audit trail of verification activities.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from database.models import SessionLocal, CoffeeBatch, EPCISEvent
from database.crud import create_event
import logging

logger = logging.getLogger(__name__)


def create_verification_event(
    batch_id: str,
    verifier_did: str,
    verifier_name: str,
    organization_did: str,
    organization_name: str,
    verified_quantity_kg: float,
    claimed_quantity_kg: float,
    quality_notes: Optional[str] = None,
    location: str = "",
    has_photo_evidence: bool = False
) -> Optional[EPCISEvent]:
    """
    Create EPCIS verification event and anchor to blockchain.
    
    This creates an industry-standard EPCIS ObjectEvent documenting
    the verification activity, providing:
    - Immutable timestamp
    - Cryptographic proof of verification
    - Audit trail for regulators/buyers
    - Supply chain traceability
    
    Args:
        batch_id: Batch identifier (e.g., "B001")
        verifier_did: DID of person who verified
        verifier_name: Name of verifier
        organization_did: DID of verifying organization
        organization_name: Name of organization
        verified_quantity_kg: Actual verified quantity
        claimed_quantity_kg: Originally claimed quantity
        quality_notes: Quality assessment notes
        location: Verification location
        has_photo_evidence: Whether photos were uploaded
        
    Returns:
        Created EPCISEvent with IPFS CID and blockchain tx hash
    """
    try:
        db = SessionLocal()
        
        # Get batch from database
        batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return None
        
        # Create EPCIS verification event with proper GS1 identifiers
        event_time = datetime.now(timezone.utc).isoformat()
        
        # Calculate verification accuracy
        accuracy = (verified_quantity_kg / claimed_quantity_kg * 100) if claimed_quantity_kg > 0 else 0
        
        # Extract GS1 identifiers from batch
        gtin = batch.gtin if batch.gtin else "0000000000000"
        gln = batch.gln if batch.gln else "0000000000000"
        
        # Format proper GS1 identifiers
        # SGTIN format: urn:epc:id:sgtin:CompanyPrefix.ItemRefAndIndicator.SerialNumber
        # Using batch_id as serial number
        sgtin = f"urn:epc:id:sgtin:{gtin}.{batch_id}"
        
        # LGTIN format for quantity list (no serial)
        lgtin = f"urn:epc:class:lgtin:{gtin}"
        
        # SGLN format: urn:epc:id:sgln:CompanyPrefix.LocationReference.Extension
        # Using GLN for location identification
        sgln_read_point = f"urn:epc:id:sgln:{gln}.{location.replace(' ', '_')}" if gln != "0000000000000" else f"urn:epc:id:sgln:unknown.{location.replace(' ', '_')}"
        sgln_biz_location = f"urn:epc:id:sgln:{gln}.{organization_name.replace(' ', '_')}"
        
        event_json = {
            "@context": [
                "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
            ],
            "type": "ObjectEvent",
            "eventTime": event_time,
            "eventTimeZoneOffset": "+00:00",
            "action": "OBSERVE",
            "bizStep": "urn:epcglobal:cbv:bizstep:inspecting",
            "disposition": "urn:epcglobal:cbv:disp:conformant",
            "readPoint": {
                "id": sgln_read_point
            },
            "bizLocation": {
                "id": sgln_biz_location
            },
            "epcList": [
                sgtin
            ],
            "quantityList": [
                {
                    "epcClass": lgtin,
                    "quantity": verified_quantity_kg,
                    "uom": "KGM"
                }
            ],
            "extension": {
                "verificationType": "cooperative_quality_inspection",
                "verifierDID": verifier_did,
                "verifierName": verifier_name,
                "verifyingOrganizationDID": organization_did,
                "verifyingOrganizationName": organization_name,
                "claimedQuantity": claimed_quantity_kg,
                "verifiedQuantity": verified_quantity_kg,
                "verificationAccuracy": round(accuracy, 2),
                "qualityNotes": quality_notes or "",
                "hasPhotoEvidence": has_photo_evidence,
                "batchId": batch_id,
                "variety": batch.variety,
                "origin": batch.origin
            }
        }
        
        # Generate event hash
        event_canonical = json.dumps(event_json, separators=(",", ":"), sort_keys=True)
        event_hash = hashlib.sha256(event_canonical.encode()).hexdigest()
        # Don't add 0x prefix - database column is VARCHAR(64)
        event_hash_hex = event_hash
        
        # Create canonical N-Quads representation (required by model)
        canonical_nquads = event_canonical  # Same as hash input
        
        # Create event data
        event_data = {
            "batch_id": batch.id,
            "event_type": "ObjectEvent",
            "biz_step": "inspecting",
            "biz_location": organization_name,
            "event_time": datetime.fromisoformat(event_time.replace("Z", "+00:00")),
            "event_json": event_json,
            "canonical_nquads": canonical_nquads,
            "event_hash": event_hash_hex,
            "submitter_id": None  # Verification is done by organization, not farmer
        }
        
        # Store event (will pin to IPFS and anchor to blockchain)
        event = create_event(
            db,
            event_data,
            pin_to_ipfs=True,
            anchor_to_blockchain=True
        )
        
        db.close()
        
        logger.info(
            f"Verification event created for batch {batch_id}: "
            f"IPFS={event.ipfs_cid}, Blockchain={event.blockchain_tx_hash}"
        )
        
        return event
        
    except Exception as e:
        logger.error(f"Failed to create verification event: {e}", exc_info=True)
        return None


def get_batch_verification_events(batch_id: str) -> list:
    """
    Get all verification events for a batch.
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        List of verification EPCISEvent records
    """
    db = SessionLocal()
    try:
        batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        
        if not batch:
            return []
        
        # Query events with inspecting biz_step
        events = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id == batch.id,
            EPCISEvent.biz_step == "inspecting"
        ).order_by(EPCISEvent.event_time.desc()).all()
        
        return events
        
    finally:
        db.close()


def get_verification_event_summary(batch_id: str) -> Dict[str, Any]:
    """
    Get summary of verification events for a batch.
    
    Returns:
        Dict with verification count, timestamps, verifiers
    """
    events = get_batch_verification_events(batch_id)
    
    if not events:
        return {
            "verified": False,
            "verification_count": 0
        }
    
    # Extract verifier DIDs from event extension
    verifiers = set()
    for event in events:
        if event.event_json and "extension" in event.event_json:
            verifier_did = event.event_json["extension"].get("verifierDID")
            if verifier_did:
                verifiers.add(verifier_did)
    
    return {
        "verified": True,
        "verification_count": len(events),
        "unique_verifiers": len(verifiers),
        "latest_verification": events[0].event_time.isoformat() if events else None,
        "first_verification": events[-1].event_time.isoformat() if events else None,
        "blockchain_anchored": all(e.blockchain_confirmed for e in events),
        "ipfs_stored": all(e.ipfs_cid is not None for e in events)
    }


if __name__ == "__main__":
    print("Verification Event Creation Module")
    print("\nThis module creates EPCIS verification events that are:")
    print("  1. Stored in database")
    print("  2. Pinned to IPFS (immutable storage)")
    print("  3. Anchored to blockchain (cryptographic timestamp)")
    print("\nProvides:")
    print("  ✓ Tamper-proof audit trail")
    print("  ✓ Independent verification by buyers")
    print("  ✓ EPCIS standard compliance")
    print("  ✓ Supply chain traceability")
