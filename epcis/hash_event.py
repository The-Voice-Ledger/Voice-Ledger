"""
EPCIS Event Hashing Module

This module creates SHA-256 cryptographic hashes of canonicalized EPCIS events.
These hashes serve as blockchain anchors - proving an event existed at a specific
time without revealing the full event data on-chain.
"""

import hashlib
from pathlib import Path
from epcis.canonicalise import canonicalise_event


def hash_event(path: Path) -> str:
    """
    Generate a SHA-256 hash of a canonicalized EPCIS event.
    
    Process:
    1. Canonicalize the event (deterministic JSON string)
    2. Encode to UTF-8 bytes
    3. Compute SHA-256 hash
    4. Return hexadecimal digest
    
    Args:
        path: Path to the EPCIS event JSON file
    
    Returns:
        64-character hexadecimal SHA-256 hash
    
    Example:
        >>> from pathlib import Path
        >>> hash_event(Path("epcis/events/BATCH-2025-001_commission.json"))
        'a1b2c3d4e5f6...'  # 64-character hex string
    """
    canonical = canonicalise_event(path)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m epcis.hash_event <path-to-event.json>")
        sys.exit(1)
    
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"Error: File not found: {p}")
        sys.exit(1)
    
    event_hash = hash_event(p)
    print(f"Event hash: {event_hash}")
