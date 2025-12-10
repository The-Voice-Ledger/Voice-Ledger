"""
EPCIS Event Canonicalization Module

This module ensures that EPCIS events produce deterministic hashes regardless
of JSON field ordering. This is critical for blockchain anchoring where the
same event must always produce the same hash.
"""

import json
from pathlib import Path


def canonicalise_event(path: Path) -> str:
    """
    Canonicalize an EPCIS event to ensure deterministic hashing.
    
    Canonicalization process:
    1. Load the JSON event
    2. Sort all keys alphabetically
    3. Remove all whitespace (compact JSON)
    4. Return normalized string
    
    Args:
        path: Path to the EPCIS event JSON file
    
    Returns:
        Canonicalized JSON string (sorted keys, no whitespace)
    
    Example:
        >>> from pathlib import Path
        >>> canonicalise_event(Path("epcis/events/BATCH-2025-001_commission.json"))
        '{"action":"ADD","batchId":"BATCH-2025-001",...}'
    """
    data = json.loads(path.read_text())
    # sort_keys=True ensures alphabetical ordering
    # separators=(",", ":") removes all whitespace
    normalised = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return normalised
