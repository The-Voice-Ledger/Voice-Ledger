"""
Batch Data Hasher for Voice Ledger
Provides deterministic hashing of batch data for merkle tree construction
"""

from typing import Optional
from eth_utils import keccak
from datetime import datetime


def hash_batch_data(
    batch_id: str,
    quantity_kg: float,
    variety: str,
    process_method: str,
    farmer_id: Optional[int] = None,
    created_at: Optional[datetime] = None,
    additional_fields: Optional[dict] = None
) -> bytes:
    """
    Generate deterministic hash of batch data.
    
    This hash is used as a leaf in the merkle tree and must be computed
    identically both when creating the tree and when verifying inclusion.
    
    Args:
        batch_id: Unique batch identifier (e.g., "FARM-001")
        quantity_kg: Quantity in kilograms
        variety: Coffee variety (e.g., "Yirgacheffe")
        process_method: Processing method (e.g., "Washed", "Natural")
        farmer_id: Optional farmer ID for database reference
        created_at: Optional creation timestamp
        additional_fields: Optional dict of extra fields to include
        
    Returns:
        32-byte keccak256 hash
        
    Example:
        >>> hash_batch_data("FARM-001", 500, "Yirgacheffe", "Washed")
        b'\\x12\\x34...'  # 32 bytes
    """
    # Build deterministic data string
    # Order matters! Must match verification expectations
    parts = [
        batch_id,
        str(quantity_kg),
        variety,
        process_method
    ]
    
    if farmer_id is not None:
        parts.append(str(farmer_id))
    
    if created_at is not None:
        # Use ISO format for deterministic timestamp
        parts.append(created_at.isoformat())
    
    if additional_fields:
        # Sort keys for deterministic ordering
        for key in sorted(additional_fields.keys()):
            parts.append(f"{key}:{additional_fields[key]}")
    
    # Join with pipe separator
    data_string = "|".join(parts)
    
    # Hash with keccak256 (matches Solidity)
    return keccak(text=data_string)


def hash_batch_from_db_model(batch) -> bytes:
    """
    Hash a CoffeeBatch database model.
    
    Args:
        batch: CoffeeBatch SQLAlchemy model instance
        
    Returns:
        32-byte keccak256 hash
        
    Example:
        >>> from database.models import CoffeeBatch
        >>> batch = db.query(CoffeeBatch).filter_by(batch_id="FARM-001").first()
        >>> batch_hash = hash_batch_from_db_model(batch)
    """
    return hash_batch_data(
        batch_id=batch.batch_id,
        quantity_kg=batch.quantity_kg,
        variety=batch.variety,
        process_method=batch.process_method,
        farmer_id=batch.farmer_id,
        created_at=batch.created_at
    )


def hash_epcis_event(event_data: dict) -> bytes:
    """
    Hash an EPCIS event for blockchain anchoring.
    
    Args:
        event_data: EPCIS event dictionary
        
    Returns:
        32-byte keccak256 hash
        
    Example:
        >>> event = {
        ...     "type": "ObjectEvent",
        ...     "action": "OBSERVE",
        ...     "bizStep": "commissioning",
        ...     "epc": "FARM-001"
        ... }
        >>> event_hash = hash_epcis_event(event)
    """
    # Serialize event to deterministic JSON string
    import json
    
    # Sort keys for deterministic ordering
    event_string = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
    
    return keccak(text=event_string)


def verify_batch_hash_integrity(
    batch,
    expected_hash: bytes
) -> bool:
    """
    Verify that a batch's current data matches an expected hash.
    Used to detect tampering or data changes.
    
    Args:
        batch: CoffeeBatch database model
        expected_hash: Expected hash value (e.g., from merkle tree)
        
    Returns:
        True if hash matches, False if data has been modified
        
    Example:
        >>> # When container was created
        >>> original_hash = hash_batch_from_db_model(batch)
        >>> 
        >>> # Later, verify data hasn't changed
        >>> if not verify_batch_hash_integrity(batch, original_hash):
        ...     print("WARNING: Batch data has been modified!")
    """
    current_hash = hash_batch_from_db_model(batch)
    return current_hash == expected_hash


# Example usage and testing
if __name__ == "__main__":
    from datetime import datetime
    
    print("Batch Data Hasher Test")
    print("=" * 50)
    
    # Test 1: Basic batch hashing
    print("\n1. Basic Batch Hash")
    hash1 = hash_batch_data("FARM-001", 500, "Yirgacheffe", "Washed")
    print(f"Hash: {hash1.hex()}")
    print(f"Length: {len(hash1)} bytes")
    
    # Test 2: Same data = same hash (deterministic)
    print("\n2. Deterministic Test")
    hash2 = hash_batch_data("FARM-001", 500, "Yirgacheffe", "Washed")
    print(f"Hash match: {'✓ Yes' if hash1 == hash2 else '✗ No'}")
    
    # Test 3: Different data = different hash
    print("\n3. Different Data Test")
    hash3 = hash_batch_data("FARM-001", 501, "Yirgacheffe", "Washed")  # Different quantity
    print(f"Different hash: {'✓ Yes' if hash1 != hash3 else '✗ No'}")
    
    # Test 4: With optional fields
    print("\n4. With Optional Fields")
    hash4 = hash_batch_data(
        "FARM-002",
        600,
        "Sidamo",
        "Natural",
        farmer_id=123,
        created_at=datetime(2025, 12, 18, 10, 30, 0),
        additional_fields={"altitude": "1800m", "region": "Yirgacheffe"}
    )
    print(f"Hash: {hash4.hex()}")
    
    # Test 5: EPCIS event hashing
    print("\n5. EPCIS Event Hash")
    event = {
        "type": "ObjectEvent",
        "action": "OBSERVE",
        "bizStep": "commissioning",
        "epc": "FARM-001",
        "eventTime": "2025-12-18T10:00:00Z"
    }
    event_hash = hash_epcis_event(event)
    print(f"Event hash: {event_hash.hex()}")
    
    # Test 6: Simulated DB model
    print("\n6. Simulated Database Model")
    
    class MockBatch:
        def __init__(self):
            self.batch_id = "FARM-003"
            self.quantity_kg = 700
            self.variety = "Guji"
            self.process_method = "Washed"
            self.farmer_id = 456
            self.created_at = datetime(2025, 12, 18, 12, 0, 0)
    
    mock_batch = MockBatch()
    hash5 = hash_batch_from_db_model(mock_batch)
    print(f"DB model hash: {hash5.hex()}")
    
    # Test 7: Integrity verification
    print("\n7. Integrity Verification")
    original_hash = hash_batch_from_db_model(mock_batch)
    print(f"Original hash: {original_hash.hex()}")
    
    # Simulate data modification
    mock_batch.quantity_kg = 705  # Changed!
    is_valid = verify_batch_hash_integrity(mock_batch, original_hash)
    print(f"After modification: {'✓ Valid' if is_valid else '✗ Invalid (expected - data changed)'}")
    
    print("\n" + "=" * 50)
    print("All tests complete!")
