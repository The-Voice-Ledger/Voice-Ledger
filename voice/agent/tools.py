"""
Agent Tool Definitions

Each tool is an OpenAI function-calling schema that maps to an existing
handler in voice/command_integration.py. The agent decides which tool(s)
to call based on the user's natural language — no manual intent classification.

Adding a new supply chain action = adding a new dict to SUPPLY_CHAIN_TOOLS.
"""

from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Tool: record_commission
# ---------------------------------------------------------------------------
RECORD_COMMISSION = {
    "type": "function",
    "function": {
        "name": "record_commission",
        "description": (
            "Create a NEW coffee batch. Use when a farmer reports a harvest, "
            "a new lot, or says they have coffee to register. "
            "Do NOT use if they reference an existing batch ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quantity_kg": {
                    "type": "number",
                    "description": (
                        "Weight in kilograms. If user says bags, multiply by 60. "
                        "e.g. '50 bags' → 3000"
                    ),
                },
                "origin": {
                    "type": "string",
                    "description": "Farm name, region, or location where coffee was produced",
                },
                "variety": {
                    "type": "string",
                    "description": (
                        "Coffee variety or product type. "
                        "e.g. Sidama, Yirgacheffe, Arabica, Washed Arabica"
                    ),
                },
                "grade": {
                    "type": "string",
                    "description": "Quality grade if mentioned (A, B, C, Grade 1, Grade 2)",
                    "default": "A",
                },
            },
            "required": ["quantity_kg", "origin"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: record_shipment
# ---------------------------------------------------------------------------
RECORD_SHIPMENT = {
    "type": "function",
    "function": {
        "name": "record_shipment",
        "description": (
            "Ship an EXISTING batch to a destination. Use when user says "
            "'ship', 'send', 'deliver', 'dispatch' and references a batch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID or GTIN of the batch to ship",
                },
                "destination": {
                    "type": "string",
                    "description": "Where the batch is being shipped to",
                },
                "carrier": {
                    "type": "string",
                    "description": "Carrier or transport company name, if mentioned",
                },
                "transport_mode": {
                    "type": "string",
                    "description": "Transport mode: truck, ship, air, rail",
                },
            },
            "required": ["batch_id", "destination"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: record_receipt
# ---------------------------------------------------------------------------
RECORD_RECEIPT = {
    "type": "function",
    "function": {
        "name": "record_receipt",
        "description": (
            "Record receipt of an existing batch. Use when user says "
            "'received', 'got', 'accepted', 'arrived' and references a batch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID or GTIN of the received batch",
                },
                "condition": {
                    "type": "string",
                    "description": "Condition on arrival: good, damaged, partial",
                    "default": "good",
                },
                "location": {
                    "type": "string",
                    "description": "Receiving location or warehouse name",
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: record_transformation
# ---------------------------------------------------------------------------
RECORD_TRANSFORMATION = {
    "type": "function",
    "function": {
        "name": "record_transformation",
        "description": (
            "Process coffee — roasting, milling, drying, hulling. "
            "Changes the physical/chemical properties of the batch. "
            "Use when user describes a processing activity on an existing batch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID or GTIN of the input batch",
                },
                "transformation_type": {
                    "type": "string",
                    "description": "Type of processing: roasting, milling, drying, hulling, washing",
                },
                "output_quantity_kg": {
                    "type": "number",
                    "description": (
                        "Output quantity in kg after processing. "
                        "Typically 10-30% less than input due to mass loss."
                    ),
                },
                "output_variety": {
                    "type": "string",
                    "description": "Output product description, e.g. 'Roasted Sidama'",
                },
            },
            "required": ["batch_id", "transformation_type", "output_quantity_kg"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: pack_batches
# ---------------------------------------------------------------------------
PACK_BATCHES = {
    "type": "function",
    "function": {
        "name": "pack_batches",
        "description": (
            "Pack / aggregate multiple batches into a single container or pallet. "
            "Creates an EPCIS AggregationEvent. Use when user says 'pack', "
            "'combine', 'load into container', 'aggregate'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of batch IDs or GTINs to pack",
                },
                "container_id": {
                    "type": "string",
                    "description": "Container or pallet ID. Auto-generated if not provided.",
                },
                "container_type": {
                    "type": "string",
                    "description": "Container type: pallet, container, bag",
                    "default": "pallet",
                },
            },
            "required": ["batch_ids"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: unpack_batches
# ---------------------------------------------------------------------------
UNPACK_BATCHES = {
    "type": "function",
    "function": {
        "name": "unpack_batches",
        "description": (
            "Unpack / disaggregate a container to release its batches. "
            "Creates an EPCIS AggregationEvent with action=DELETE. "
            "Use when user says 'unpack', 'unload', 'open container'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container or pallet ID to unpack",
                },
            },
            "required": ["container_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: split_batch
# ---------------------------------------------------------------------------
SPLIT_BATCH = {
    "type": "function",
    "function": {
        "name": "split_batch",
        "description": (
            "Split one batch into multiple smaller portions. "
            "Use when user says 'split', 'divide', 'separate'. "
            "NOT for processing — use record_transformation for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Parent batch ID or GTIN to split",
                },
                "splits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quantity_kg": {
                                "type": "number",
                                "description": "Quantity for this split portion",
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination or label for this portion",
                            },
                        },
                        "required": ["quantity_kg"],
                    },
                    "description": "List of split portions with quantities",
                },
            },
            "required": ["batch_id", "splits"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: query_batches  (READ — no mutation)
# ---------------------------------------------------------------------------
QUERY_BATCHES = {
    "type": "function",
    "function": {
        "name": "query_batches",
        "description": (
            "Look up coffee batches in the database. Use when user asks "
            "'show my batches', 'find batch X', 'how many batches', 'what batches', "
            "'status of batch', etc. This is a READ-ONLY operation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Specific batch ID or GTIN to look up",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status: PENDING_VERIFICATION, VERIFIED, SHIPPED, RECEIVED",
                },
                "origin": {
                    "type": "string",
                    "description": "Filter by origin region",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of results (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: search_knowledge  (RAG — documentation search)
# ---------------------------------------------------------------------------
SEARCH_KNOWLEDGE = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "Search the Voice Ledger knowledge base for documentation, guides, "
            "standards, and how-to information. Use when user asks 'how to', "
            "'what is', 'explain', or questions about EUDR, EPCIS, GS1, blockchain."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in English",
                },
            },
            "required": ["query"],
        },
    },
}


# ---------------------------------------------------------------------------
# All tools grouped
# ---------------------------------------------------------------------------
SUPPLY_CHAIN_TOOLS: List[Dict[str, Any]] = [
    RECORD_COMMISSION,
    RECORD_SHIPMENT,
    RECORD_RECEIPT,
    RECORD_TRANSFORMATION,
    PACK_BATCHES,
    UNPACK_BATCHES,
    SPLIT_BATCH,
    QUERY_BATCHES,
    SEARCH_KNOWLEDGE,
]
