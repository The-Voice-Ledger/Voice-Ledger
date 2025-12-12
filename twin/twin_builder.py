"""
Digital Twin Synchronization Module

Maintains a unified digital twin representation that combines:
- On-chain data (event anchors, tokens, settlement)
- Off-chain data (EPCIS events, credentials, metadata)
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

TWIN_PATH = Path("twin/digital_twin.json")


def load_twin() -> dict:
    """
    Load the digital twin state from disk.
    
    Returns:
        Dictionary with structure: {"batches": {batch_id: {...}}}
    """
    if TWIN_PATH.exists():
        return json.loads(TWIN_PATH.read_text())
    return {"batches": {}}


def save_twin(data: dict):
    """
    Save the digital twin state to disk.
    
    Args:
        data: Complete twin state dictionary
    """
    TWIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TWIN_PATH.write_text(json.dumps(data, indent=2))


def record_anchor(batch_id: str, event_hash: str, event_type: str, tx_hash: Optional[str] = None):
    """
    Record an on-chain anchor in the digital twin.
    
    Args:
        batch_id: Batch identifier
        event_hash: SHA-256 hash of the EPCIS event
        event_type: Type of event (commissioning, shipment, etc.)
        tx_hash: Optional blockchain transaction hash
    """
    twin = load_twin()
    
    # Initialize batch if not exists
    if batch_id not in twin["batches"]:
        twin["batches"][batch_id] = {
            "batchId": batch_id,
            "anchors": [],
            "tokenId": None,
            "metadata": {},
            "settlement": None,
            "credentials": []
        }
    
    # Add anchor
    twin["batches"][batch_id]["anchors"].append({
        "eventHash": event_hash,
        "eventType": event_type,
        "txHash": tx_hash,
        "timestamp": None  # Would come from blockchain
    })
    
    save_twin(twin)
    print(f"✅ Recorded anchor for {batch_id}: {event_type}")


def record_token(batch_id: str, token_id: int, quantity: int, metadata: str):
    """
    Record an ERC-1155 token minting in the digital twin.
    
    Args:
        batch_id: Batch identifier
        token_id: On-chain token ID
        quantity: Number of units minted
        metadata: Batch metadata JSON string
    """
    twin = load_twin()
    
    if batch_id not in twin["batches"]:
        twin["batches"][batch_id] = {
            "batchId": batch_id,
            "anchors": [],
            "tokenId": None,
            "metadata": {},
            "settlement": None,
            "credentials": []
        }
    
    twin["batches"][batch_id]["tokenId"] = token_id
    twin["batches"][batch_id]["quantity"] = quantity
    twin["batches"][batch_id]["metadata"] = json.loads(metadata) if isinstance(metadata, str) else metadata
    
    save_twin(twin)
    print(f"✅ Recorded token for {batch_id}: Token ID {token_id}")


def record_settlement(batch_id: str, amount: int, recipient: str, tx_hash: Optional[str] = None):
    """
    Record a settlement in the digital twin.
    
    Args:
        batch_id: Batch identifier
        amount: Settlement amount
        recipient: Recipient address
        tx_hash: Optional blockchain transaction hash
    """
    twin = load_twin()
    
    if batch_id not in twin["batches"]:
        twin["batches"][batch_id] = {
            "batchId": batch_id,
            "anchors": [],
            "tokenId": None,
            "metadata": {},
            "settlement": None,
            "credentials": []
        }
    
    twin["batches"][batch_id]["settlement"] = {
        "amount": amount,
        "recipient": recipient,
        "txHash": tx_hash,
        "settled": True
    }
    
    save_twin(twin)
    print(f"✅ Recorded settlement for {batch_id}: {amount} to {recipient[:10]}...")


def record_credential(batch_id: str, credential: Dict[str, Any]):
    """
    Attach a verifiable credential to a batch's digital twin.
    
    Args:
        batch_id: Batch identifier
        credential: Verifiable credential dictionary
    """
    twin = load_twin()
    
    if batch_id not in twin["batches"]:
        twin["batches"][batch_id] = {
            "batchId": batch_id,
            "anchors": [],
            "tokenId": None,
            "metadata": {},
            "settlement": None,
            "credentials": []
        }
    
    twin["batches"][batch_id]["credentials"].append(credential)
    
    save_twin(twin)
    print(f"✅ Attached credential to {batch_id}: {credential.get('type', ['Unknown'])[1]}")


def get_batch_twin(batch_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the complete digital twin for a batch.
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        Batch twin dictionary or None if not found
    """
    twin = load_twin()
    return twin["batches"].get(batch_id)


def list_all_batches() -> list:
    """
    List all batch IDs in the digital twin.
    
    Returns:
        List of batch ID strings
    """
    twin = load_twin()
    return list(twin["batches"].keys())


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
