"""
EPCIS 2.0 Event Builder

This module constructs EPCIS 2.0 JSON-LD events that capture supply chain activities.
Events are saved to the epcis/events/ directory for later canonicalization and hashing.
"""

import json
from pathlib import Path
from gs1.identifiers import gln, gtin, sscc

EVENT_DIR = Path("epcis/events")
EVENT_DIR.mkdir(parents=True, exist_ok=True)


def create_commission_event(batch_id: str) -> Path:
    """
    Create an EPCIS 2.0 ObjectEvent for batch commissioning.
    
    Commissioning represents the creation/registration of a new coffee batch
    in the supply chain system.
    
    Args:
        batch_id: Unique identifier for the coffee batch (e.g., "BATCH-2025-001")
    
    Returns:
        Path to the created JSON event file
    
    Example:
        >>> create_commission_event("BATCH-2025-001")
        PosixPath('epcis/events/BATCH-2025-001_commission.json')
    """
    event = {
        "type": "ObjectEvent",
        "eventTime": "2025-01-01T00:00:00Z",
        "eventTimeZoneOffset": "+00:00",
        "epcList": [f"urn:epc:id:sscc:{sscc(batch_id)}"],
        "action": "ADD",
        "bizStep": "commissioning",
        "readPoint": {"id": f"urn:epc:id:gln:{gln('100001')}"},
        "bizLocation": {"id": f"urn:epc:id:gln:{gln('100001')}"},
        "productClass": f"urn:epc:id:gtin:{gtin('200001')}",
        "batchId": batch_id,
    }

    out = EVENT_DIR / f"{batch_id}_commission.json"
    out.write_text(json.dumps(event, indent=2))
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m epcis.epcis_builder BATCH-ID")
        sys.exit(1)
    
    batch = sys.argv[1]
    output_path = create_commission_event(batch)
    print(f"Created: {output_path}")
