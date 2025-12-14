"""
Digital Twin Synchronization Module

Maintains a unified digital twin representation that combines:
- On-chain data (event anchors, tokens, settlement)
- Off-chain data (EPCIS events, credentials, metadata)

Updated to use Neon PostgreSQL database instead of JSON files.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from database import get_db, get_all_batches

TWIN_PATH = Path("twin/digital_twin.json")  # Legacy path for backward compatibility


def load_twin() -> dict:
    """
    Load the digital twin state from Neon database.
    
    Returns:
        Dictionary with structure: {"batches": {batch_id: {...}}}
    """
    with get_db() as db:
        batches = get_all_batches(db)
        
        twin = {"batches": {}}
        for batch in batches:
            twin["batches"][batch.batch_id] = {
                "batchId": batch.batch_id,
                "gtin": batch.gtin,
                "tokenId": batch.token_id,
                "quantity": batch.quantity_kg,
                "metadata": {
                    "origin": batch.origin_region,
                    "cooperative": batch.farm_name,
                    "variety": batch.variety,
                    "processing": batch.process_method,
                    "grade": batch.grade,
                    "cuppingScore": batch.cupping_score
                },
                "farmer": {
                    "farmerId": batch.farmer.farmer_id,
                    "name": batch.farmer.name,
                    "did": batch.farmer.did,
                    "region": batch.farmer.region
                },
                "anchors": [
                    {
                        "eventHash": event.event_hash,
                        "eventType": event.event_type,
                        "txHash": event.blockchain_tx_hash,
                        "timestamp": event.event_time.isoformat() if event.event_time else None
                    }
                    for event in batch.events
                ],
                "credentials": [],  # TODO: Load from farmer.credentials
                "settlement": None  # TODO: Add settlement tracking
            }
        
        return twin


def save_twin(data: dict):
    """
    Save the digital twin state (legacy function for backward compatibility).
    
    Note: With database integration, this function is deprecated.
    Data is automatically saved to database via CRUD operations.
    
    Args:
        data: Complete twin state dictionary (ignored)
    """
    # Database operations are atomic, no need for explicit save
    # This function kept for backward compatibility only
    print("ℹ️  save_twin() is deprecated with database integration. Data already persisted.")


def record_anchor(batch_id: str, event_hash: str, event_type: str, tx_hash: Optional[str] = None):
    """
    Record an on-chain anchor by updating event in database.
    
    Args:
        batch_id: Batch identifier
        event_hash: SHA-256 hash of the EPCIS event
        event_type: Type of event (commissioning, shipment, etc.)
        tx_hash: Optional blockchain transaction hash
    """
    from database import update_event_blockchain_tx, get_event_by_hash
    
    with get_db() as db:
        if tx_hash:
            # Look up event by hash first to get database ID
            event = get_event_by_hash(db, event_hash)
            if event:
                # Update event with blockchain transaction hash
                event = update_event_blockchain_tx(db, event.id, tx_hash)
                print(f"✅ Recorded anchor for {batch_id}: {event_type} (TX: {tx_hash[:16]}...)")
            else:
                print(f"⚠️  Event {event_hash[:16]}... not found in database")
        else:
            print(f"✅ Event {event_hash[:16]}... created for {batch_id}: {event_type}")


def record_token(batch_id: str, token_id: int, quantity: int, metadata: str):
    """
    Record an ERC-1155 token minting by updating batch in database.
    
    Args:
        batch_id: Batch identifier
        token_id: On-chain token ID
        quantity: Number of units minted
        metadata: Batch metadata JSON string (ignored - metadata from batch record)
    """
    from database import get_batch_by_batch_id
    from sqlalchemy import update
    from database.models import CoffeeBatch
    
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if batch:
            # Update token_id in database
            db.execute(
                update(CoffeeBatch)
                .where(CoffeeBatch.batch_id == batch_id)
                .values(token_id=token_id)
            )
            db.commit()
            print(f"✅ Recorded token for {batch_id}: Token ID {token_id}")
        else:
            print(f"❌ Batch {batch_id} not found in database")


def record_settlement(batch_id: str, amount: int, recipient: str, tx_hash: Optional[str] = None):
    """
    Record a settlement (placeholder - settlement tracking not yet in database schema).
    
    Args:
        batch_id: Batch identifier
        amount: Settlement amount
        recipient: Recipient address
        tx_hash: Optional blockchain transaction hash
    """
    # TODO: Add settlement tracking to database schema
    # For now, just log the settlement
    print(f"✅ Settlement recorded for {batch_id}: {amount} to {recipient[:10]}... (TX: {tx_hash[:16] if tx_hash else 'pending'}...)")
    print(f"ℹ️  Note: Settlement tracking not yet implemented in database schema")


def record_credential(batch_id: str, credential: Dict[str, Any]):
    """
    Attach a verifiable credential by storing in database.
    
    Args:
        batch_id: Batch identifier
        credential: Verifiable credential dictionary
    """
    from database import store_credential, get_batch_by_batch_id
    from datetime import datetime
    
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if not batch:
            print(f"❌ Batch {batch_id} not found in database")
            return
        
        # Extract credential data
        credential_data = {
            "credential_id": credential.get("id", f"VC-{batch_id}-{datetime.utcnow().timestamp()}"),
            "subject_did": batch.farmer.did,
            "issuer_did": credential.get("issuer", "did:key:system"),
            "credential_type": credential.get("type", ["VerifiableCredential"])[1] if len(credential.get("type", [])) > 1 else "VerifiableCredential",
            "credential_json": json.dumps(credential),
            "proof": json.dumps(credential.get("proof", {})),
            "issued_at": datetime.fromisoformat(credential.get("issuanceDate", datetime.utcnow().isoformat())),
            "expires_at": datetime.fromisoformat(credential["expirationDate"]) if "expirationDate" in credential else None
        }
        
        vc = store_credential(db, credential_data)
        print(f"✅ Attached credential to {batch_id}: {vc.credential_type}")


def get_batch_twin(batch_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the complete digital twin for a batch from database.
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        Batch twin dictionary or None if not found
    """
    twin = load_twin()
    return twin["batches"].get(batch_id)


def list_all_batches() -> list:
    """
    List all batch IDs from database.
    
    Returns:
        List of batch ID strings
    """
    with get_db() as db:
        batches = get_all_batches(db)
        return [batch.batch_id for batch in batches]


if __name__ == "__main__":
    print("=== Testing Digital Twin Module ===\n")
    
    # Test: Record anchor
    record_anchor("BATCH-2025-001", "bc16581a015e8d239723f41734f0847b8615dcae996f182491ddffc67017b3fc", "commissioning")
    
    # Test: Record token
    record_token("BATCH-2025-001", 1, 50, '{"origin": "Ethiopia", "cooperative": "Guzo"}')
    
    # Test: Record settlement
    record_settlement("BATCH-2025-001", 1000000, "0x1234567890abcdef1234567890abcdef12345678")
    
    # Test: Retrieve twin
    print("\nRetrieving digital twin:")
    twin = get_batch_twin("BATCH-2025-001")
    print(json.dumps(twin, indent=2))
