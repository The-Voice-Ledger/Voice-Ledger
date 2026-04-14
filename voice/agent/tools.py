"""
Agent Tool Definitions

Each tool is an OpenAI function-calling schema that maps to an existing
handler in voice/command_integration.py. The agent decides which tool(s)
to call based on the user's natural language - no manual intent classification.

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
            "Process coffee - roasting, milling, drying, hulling. "
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
            "NOT for processing - use record_transformation for that."
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
# Tool: query_batches  (READ - no mutation)
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
# Tool: search_knowledge  (RAG - documentation search)
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


# ===========================================================================
# MARKETPLACE TOOLS (Agent #3 - RFQ system for buyers & cooperatives)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: create_rfq  (WRITE - buyer creates request for quote)
# ---------------------------------------------------------------------------
CREATE_RFQ = {
    "type": "function",
    "function": {
        "name": "create_rfq",
        "description": (
            "Create a new Request for Quote (RFQ) on the marketplace. "
            "Only BUYER role users can create RFQs. Use when a buyer says "
            "'I need coffee', 'looking for', 'request quote', 'buy', 'purchase'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quantity_kg": {
                    "type": "number",
                    "description": (
                        "Quantity needed in kilograms. "
                        "If user says bags, multiply by 60."
                    ),
                },
                "variety": {
                    "type": "string",
                    "description": "Coffee variety requested, e.g. Yirgacheffe, Sidama, Guji",
                },
                "processing_method": {
                    "type": "string",
                    "description": "Processing method: Washed, Natural, Honey",
                },
                "grade": {
                    "type": "string",
                    "description": "Quality grade: Grade 1, Grade 2, Specialty",
                },
                "delivery_location": {
                    "type": "string",
                    "description": "Where the coffee should be delivered",
                },
            },
            "required": ["quantity_kg"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: browse_rfqs  (READ - cooperative browses open requests)
# ---------------------------------------------------------------------------
BROWSE_RFQS = {
    "type": "function",
    "function": {
        "name": "browse_rfqs",
        "description": (
            "Browse open RFQs on the marketplace. Use when a cooperative "
            "manager asks 'what do buyers need', 'show me requests', "
            "'any open orders', 'marketplace', 'available RFQs'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variety": {
                    "type": "string",
                    "description": "Filter by coffee variety",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status: OPEN, PARTIALLY_FILLED, FULFILLED",
                    "default": "OPEN",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: submit_offer  (WRITE - cooperative offers on an RFQ)
# ---------------------------------------------------------------------------
SUBMIT_OFFER = {
    "type": "function",
    "function": {
        "name": "submit_offer",
        "description": (
            "Submit an offer for an open RFQ. Only COOPERATIVE_MANAGER role "
            "users can submit offers. Use when user says 'I can supply', "
            "'make offer', 'bid on', 'I have coffee for that request'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rfq_id": {
                    "type": "integer",
                    "description": "RFQ ID to make an offer on",
                },
                "rfq_number": {
                    "type": "string",
                    "description": "RFQ number (e.g. RFQ-000001) - alternative to rfq_id",
                },
                "quantity_offered_kg": {
                    "type": "number",
                    "description": "Quantity offered in kilograms",
                },
                "price_per_kg": {
                    "type": "number",
                    "description": "Price per kg in USD",
                },
                "delivery_timeline": {
                    "type": "string",
                    "description": "Delivery timeline, e.g. '2 weeks', '30 days'",
                },
            },
            "required": ["quantity_offered_kg", "price_per_kg"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: accept_offer  (WRITE - buyer accepts a cooperative's offer)
# ---------------------------------------------------------------------------
ACCEPT_OFFER = {
    "type": "function",
    "function": {
        "name": "accept_offer",
        "description": (
            "Accept an offer from a cooperative on one of your RFQs. "
            "Only the BUYER who created the RFQ can accept. "
            "Use when buyer says 'accept offer', 'go with that one', 'approve'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "offer_id": {
                    "type": "integer",
                    "description": "The offer ID to accept",
                },
                "rfq_id": {
                    "type": "integer",
                    "description": "RFQ ID the offer belongs to",
                },
                "quantity_accepted_kg": {
                    "type": "number",
                    "description": (
                        "Quantity to accept in kg. "
                        "If not specified, accepts the full offered quantity."
                    ),
                },
                "payment_terms": {
                    "type": "string",
                    "description": "Payment terms: NET_30, NET_60, CASH_ON_DELIVERY",
                },
            },
            "required": ["offer_id", "rfq_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: list_my_offers  (READ - cooperative views their offers)
# ---------------------------------------------------------------------------
LIST_MY_OFFERS = {
    "type": "function",
    "function": {
        "name": "list_my_offers",
        "description": (
            "List offers that the current cooperative has submitted. "
            "Use when cooperative manager asks 'my offers', 'what did I bid on', "
            "'offer status', 'pending offers'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by offer status: PENDING, ACCEPTED, REJECTED",
                },
            },
            "required": [],
        },
    },
}


# ===========================================================================
# COMPLIANCE TOOLS (Agent #4 - EUDR & supply chain validation)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: check_eudr_compliance  (READ - validate EUDR requirements)
# ---------------------------------------------------------------------------
CHECK_EUDR_COMPLIANCE = {
    "type": "function",
    "function": {
        "name": "check_eudr_compliance",
        "description": (
            "Check EUDR (EU Deforestation Regulation 2023/1115) compliance "
            "for one or more batches. Validates that all farmers have GPS "
            "coordinates (Article 9 requirement). Use when user asks "
            "'is this batch compliant', 'EUDR check', 'can I export to EU', "
            "'compliance status', 'deforestation check'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of batch IDs to check for EUDR compliance",
                },
            },
            "required": ["batch_ids"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: check_mass_balance  (READ - validate mass balance)
# ---------------------------------------------------------------------------
CHECK_MASS_BALANCE = {
    "type": "function",
    "function": {
        "name": "check_mass_balance",
        "description": (
            "Validate mass balance between input and output quantities. "
            "Ensures no coffee is created out of thin air during splits or "
            "processing. Use when user asks 'check mass balance', "
            "'quantities add up', 'validate transformation', 'audit split'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input_quantities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quantity": {"type": "number"},
                            "uom": {"type": "string", "default": "KGM"},
                        },
                        "required": ["quantity"],
                    },
                    "description": "List of input quantities (with optional uom)",
                },
                "output_quantities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quantity": {"type": "number"},
                            "uom": {"type": "string", "default": "KGM"},
                        },
                        "required": ["quantity"],
                    },
                    "description": "List of output quantities (with optional uom)",
                },
                "allow_loss": {
                    "type": "boolean",
                    "description": (
                        "If true, allow output < input (for processing like roasting "
                        "where 10-30% mass loss is normal). Default false."
                    ),
                    "default": False,
                },
            },
            "required": ["input_quantities", "output_quantities"],
        },
    },
}


# ===========================================================================
# VERIFICATION TOOLS (Agent #6 - batch verification workflow)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: list_pending_verifications  (READ - show unverified batches)
# ---------------------------------------------------------------------------
LIST_PENDING_VERIFICATIONS = {
    "type": "function",
    "function": {
        "name": "list_pending_verifications",
        "description": (
            "List batches that are pending verification. "
            "Use when a cooperative manager asks 'what needs verification', "
            "'unverified batches', 'pending verifications', "
            "'what batches are waiting for me'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Filter by origin region",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: verify_batch  (WRITE - mark a batch as verified)
# ---------------------------------------------------------------------------
VERIFY_BATCH = {
    "type": "function",
    "function": {
        "name": "verify_batch",
        "description": (
            "Verify a coffee batch. Only COOPERATIVE_MANAGER role users can "
            "verify batches. Updates batch status to VERIFIED and issues a "
            "verification credential. Use when manager says 'verify batch', "
            "'approve batch', 'I checked this batch', 'confirm quality'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID to verify",
                },
                "verified_quantity_kg": {
                    "type": "number",
                    "description": (
                        "Actual quantity verified in kg. "
                        "If not provided, uses the claimed quantity."
                    ),
                },
                "quality_notes": {
                    "type": "string",
                    "description": (
                        "Quality assessment notes - grade, moisture content, "
                        "defects, overall condition"
                    ),
                },
                "cupping_score": {
                    "type": "number",
                    "description": (
                        "SCA cupping score (0-100). Specialty grade is 80+. "
                        "Extract from manager's quality assessment."
                    ),
                },
                "moisture_pct": {
                    "type": "number",
                    "description": (
                        "Moisture percentage of the green coffee (e.g. 11.5). "
                        "Ideal range is 10-12%."
                    ),
                },
                "screen_size": {
                    "type": "string",
                    "description": (
                        "Bean screen size, e.g. '15+', '14-16', '17/18'. "
                        "Measured by sieve number."
                    ),
                },
                "defect_count": {
                    "type": "integer",
                    "description": (
                        "Total defect count per 350g sample. "
                        "Specialty grade allows max 5 full defects."
                    ),
                },
                "defect_category": {
                    "type": "string",
                    "description": (
                        "SCA defect category: 'Specialty' (0-5 defects), "
                        "'Premium' (6-8), 'Exchange' (9-23), "
                        "'Below Standard' (24-86), or 'Off Grade' (86+)."
                    ),
                },
                "sensory_notes": {
                    "type": "object",
                    "description": (
                        "Sensory evaluation scores. Keys: aroma, acidity, "
                        "body, flavor, aftertaste, balance, uniformity, "
                        "clean_cup, sweetness, overall. Values are numbers."
                    ),
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ===========================================================================
# DPP TOOLS (Agent #5 - Digital Product Passport generation & lookup)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: get_dpp  (READ - retrieve Digital Product Passport for a batch)
# ---------------------------------------------------------------------------
GET_DPP = {
    "type": "function",
    "function": {
        "name": "get_dpp",
        "description": (
            "Generate or retrieve the Digital Product Passport (DPP) for a "
            "coffee batch. Returns EUDR compliance data, traceability, "
            "blockchain anchoring status, and QR code. Use when user asks "
            "'show me the passport for batch X', 'get DPP', 'product passport', "
            "'traceability info', 'where did this coffee come from'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID or GTIN to look up",
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: get_container_dpp  (READ - aggregated DPP for a container/SSCC)
# ---------------------------------------------------------------------------
GET_CONTAINER_DPP = {
    "type": "function",
    "function": {
        "name": "get_container_dpp",
        "description": (
            "Get the aggregated Digital Product Passport for a shipping "
            "container (SSCC). Shows all contributing farmers, their "
            "percentages, and combined traceability. Use when user asks "
            "'container passport', 'who contributed to this container', "
            "'show container DPP', 'aggregated passport'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container SSCC or container ID",
                },
            },
            "required": ["container_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: trace_lineage  (READ - recursive supply chain traceability)
# ---------------------------------------------------------------------------
TRACE_LINEAGE = {
    "type": "function",
    "function": {
        "name": "trace_lineage",
        "description": (
            "Trace the complete supply chain lineage of a product from "
            "retail back to farm. Shows the full hierarchy: Retail Bag → "
            "Roasted Lot → Washed Lot → Farmer Batches. Use when user asks "
            "'trace this coffee', 'where did it come from', 'full history', "
            "'supply chain lineage', 'product journey'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Batch ID, container ID, or product ID to trace",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth of tracing (default 5)",
                    "default": 5,
                },
            },
            "required": ["product_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: validate_dpp  (READ - check if a DPP is valid/complete)
# ---------------------------------------------------------------------------
VALIDATE_DPP = {
    "type": "function",
    "function": {
        "name": "validate_dpp",
        "description": (
            "Validate a Digital Product Passport for completeness and "
            "EUDR compliance. Checks all required fields are present. "
            "Use when user asks 'is this DPP valid', 'check passport', "
            "'validate DPP', 'is the passport complete'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID whose DPP to validate",
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ===========================================================================
# BLOCKCHAIN TOOLS (Agent #7 - on-chain verification & token lookup)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: check_blockchain_anchor  (READ - verify batch is anchored on-chain)
# ---------------------------------------------------------------------------
CHECK_BLOCKCHAIN_ANCHOR = {
    "type": "function",
    "function": {
        "name": "check_blockchain_anchor",
        "description": (
            "Check if a batch's EPCIS event has been anchored to the "
            "blockchain (Base Sepolia). Returns event hash, event type, "
            "IPFS CID, and timestamp. Use when user asks 'is this on "
            "the blockchain', 'check anchor', 'verify on-chain', "
            "'blockchain status for batch X'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID to check on-chain",
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: get_token_info  (READ - look up ERC-1155 batch token metadata)
# ---------------------------------------------------------------------------
GET_TOKEN_INFO = {
    "type": "function",
    "function": {
        "name": "get_token_info",
        "description": (
            "Look up the on-chain ERC-1155 token for a coffee batch. "
            "Returns token metadata, quantity, IPFS CID, and whether "
            "it's an aggregated container token. Use when user asks "
            "'token info', 'show token', 'what token is this batch', "
            "'check token metadata'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "integer",
                    "description": "On-chain token ID (number)",
                },
            },
            "required": ["token_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: verify_batch_hash  (READ - verify batch data hasn't been tampered)
# ---------------------------------------------------------------------------
VERIFY_BATCH_HASH = {
    "type": "function",
    "function": {
        "name": "verify_batch_hash",
        "description": (
            "Verify a batch's data integrity by comparing its current hash "
            "against what was anchored on-chain. Detects tampering - if the "
            "batch data was modified after anchoring, the hashes won't match. "
            "Use when user asks 'has this batch been tampered with', "
            "'verify integrity', 'check hash', 'is the data authentic'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "Batch ID to verify hash integrity",
                },
            },
            "required": ["batch_id"],
        },
    },
}


# ===========================================================================
# CONTAINER MARKETPLACE TOOLS (Agent #3b - fractional container sales)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool: browse_containers  (READ - list available containers)
# ---------------------------------------------------------------------------
BROWSE_CONTAINERS = {
    "type": "function",
    "function": {
        "name": "browse_containers",
        "description": (
            "Browse containers available for fractional purchase. "
            "Cooperatives list full shipping containers; buyers purchase portions. "
            "Use when user asks 'show containers', 'available containers', "
            "'what can I buy', 'container marketplace', 'browse lots'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variety": {
                    "type": "string",
                    "description": "Filter by coffee variety",
                },
                "min_quantity_kg": {
                    "type": "number",
                    "description": "Minimum available quantity in kg",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: purchase_container  (WRITE - buyer buys a portion of a container)
# ---------------------------------------------------------------------------
PURCHASE_CONTAINER = {
    "type": "function",
    "function": {
        "name": "purchase_container",
        "description": (
            "Purchase a partial quantity from a container offering. "
            "Only BUYER role users can purchase. "
            "Use when buyer says 'buy from container', 'purchase 500kg', "
            "'I want some from that container'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "integer",
                    "description": "Container offering ID",
                },
                "quantity_kg": {
                    "type": "number",
                    "description": "Quantity to purchase in kilograms",
                },
                "payment_terms": {
                    "type": "string",
                    "description": "Payment terms: NET_7, NET_30, CASH_ON_DELIVERY",
                    "default": "Net 7 days",
                },
            },
            "required": ["container_id", "quantity_kg"],
        },
    },
}


# Tool: browse_pools  (READ -- list active container pools with fill progress)
# ──────────────────────────────────────────────────────────────────────────────
BROWSE_POOLS = {
    "type": "function",
    "function": {
        "name": "browse_pools",
        "description": (
            "Browse shared-container pools that buyers can commit fractional "
            "quantities into. Pools aggregate demand by destination region so "
            "SME roasters can co-purchase a full container."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Filter by destination region (Benelux, DACH, Nordic, Mediterranean, etc.)",
                },
                "container_offering_id": {
                    "type": "integer",
                    "description": "Filter pools for a specific container offering",
                },
            },
            "required": [],
        },
    },
}

# Tool: commit_to_pool  (WRITE -- buyer commits a fractional qty to a pool)
# ──────────────────────────────────────────────────────────────────────────────
COMMIT_TO_POOL = {
    "type": "function",
    "function": {
        "name": "commit_to_pool",
        "description": (
            "Commit a fractional quantity from a container into a region-based "
            "pool. The system auto-assigns the buyer to the right pool based on "
            "their delivery country, and auto-confirms shipment when the pool "
            "reaches 80 percent fill."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "container_offering_id": {
                    "type": "integer",
                    "description": "ID of the container offering to buy from",
                },
                "quantity_kg": {
                    "type": "number",
                    "description": "Kilograms to commit (fractional purchase)",
                },
                "delivery_country": {
                    "type": "string",
                    "description": "ISO 3166-1 alpha-2 country code (e.g. DE, FR, NL)",
                },
                "delivery_city": {
                    "type": "string",
                    "description": "City name for last-mile delivery",
                },
            },
            "required": ["container_offering_id", "quantity_kg"],
        },
    },
}

# Tool: list_my_commitments  (READ -- buyer views their own commitments)
# ──────────────────────────────────────────────────────────────────────────────
LIST_MY_COMMITMENTS = {
    "type": "function",
    "function": {
        "name": "list_my_commitments",
        "description": (
            "List the authenticated buyer's own pool commitments, showing "
            "quantity, price, pool fill progress, and delivery status."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


# ===========================================================================
# Settlement / Payment tools (Agent #8)
# ===========================================================================

# Tool: confirm_payment  (WRITE - buyer confirms bank transfer)
# ──────────────────────────────────────────────────────────────────────────────
CONFIRM_PAYMENT = {
    "type": "function",
    "function": {
        "name": "confirm_payment",
        "description": (
            "Buyer confirms they made a bank transfer for a pool commitment "
            "or RFQ acceptance.  Records settlement on-chain as proof of "
            "payment.  Provide either commitment_id (pool purchase) or "
            "acceptance_number (RFQ purchase)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "commitment_id": {
                    "type": "integer",
                    "description": "Pool commitment ID (for pool purchases)",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number like ACC-000001 (for RFQ purchases)",
                },
                "payment_reference": {
                    "type": "string",
                    "description": "Bank transfer reference (optional)",
                },
            },
            "required": [],
        },
    },
}

# Tool: check_payment_status  (READ - check payment + settlement status)
# ──────────────────────────────────────────────────────────────────────────────
CHECK_PAYMENT_STATUS = {
    "type": "function",
    "function": {
        "name": "check_payment_status",
        "description": (
            "Check the payment and blockchain settlement status for a pool "
            "commitment or RFQ acceptance.  Shows buyer confirmation, "
            "cooperative confirmation, and on-chain transaction hashes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "commitment_id": {
                    "type": "integer",
                    "description": "Pool commitment ID",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number like ACC-000001",
                },
            },
            "required": [],
        },
    },
}

# Tool: record_cooperative_payout  (WRITE - admin records coop payout on-chain)
# ──────────────────────────────────────────────────────────────────────────────
RECORD_COOPERATIVE_PAYOUT = {
    "type": "function",
    "function": {
        "name": "record_cooperative_payout",
        "description": (
            "Admin tool: record on-chain that WAGA has forwarded the buyer's "
            "payment from the European bank account to the cooperative's "
            "Ethiopian bank account.  Creates an immutable on-chain receipt "
            "of the cooperative payout."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "commitment_id": {
                    "type": "integer",
                    "description": "Pool commitment ID (if pool purchase)",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number (if RFQ purchase)",
                },
            },
            "required": [],
        },
    },
}

# Tool: confirm_payment_received  (WRITE - cooperative confirms receipt)
# ──────────────────────────────────────────────────────────────────────────────
CONFIRM_PAYMENT_RECEIVED = {
    "type": "function",
    "function": {
        "name": "confirm_payment_received",
        "description": (
            "Cooperative confirms they received the buyer's bank transfer in "
            "their bank account.  Triggers shipment preparation.  Provide "
            "either commitment_id or acceptance_number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "commitment_id": {
                    "type": "integer",
                    "description": "Pool commitment ID",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number like ACC-000001",
                },
            },
            "required": [],
        },
    },
}


# ===========================================================================
# DeFi Financing Pool tools (Agent #10)
# ===========================================================================

# Tool: check_financing_pool  (READ - pool stats)
# ──────────────────────────────────────────────────────────────────────────────
CHECK_FINANCING_POOL = {
    "type": "function",
    "function": {
        "name": "check_financing_pool",
        "description": (
            "Check the DeFi financing pool status: total liquidity, amount "
            "currently advanced, available balance for new advances, utilisation "
            "percentage, cumulative fees, and current share price. Use when a "
            "cooperative asks 'how much financing is available?', 'pool status', "
            "'can I get an advance?', 'what is the pool balance?'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

# Tool: request_financing_advance  (WRITE - cooperative requests USDC advance)
# ──────────────────────────────────────────────────────────────────────────────
REQUEST_FINANCING_ADVANCE = {
    "type": "function",
    "function": {
        "name": "request_financing_advance",
        "description": (
            "Request a USDC advance from the financing pool against a confirmed "
            "buyer order. The cooperative's shipped container token (ERC-1155) is "
            "locked as collateral in escrow. Use when a cooperative says "
            "'I need an advance', 'finance my shipment', 'get early payment for "
            "container X'. Requires a confirmed acceptance_number or trade details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number (e.g. ACC-000001) of the confirmed trade",
                },
                "token_id": {
                    "type": "integer",
                    "description": "ERC-1155 container token ID (if known)",
                },
                "buyer_address": {
                    "type": "string",
                    "description": "Buyer's wallet address (if known)",
                },
            },
            "required": [],
        },
    },
}

# Tool: check_trade_financing  (READ - check advance/trade status)
# ──────────────────────────────────────────────────────────────────────────────
CHECK_TRADE_FINANCING = {
    "type": "function",
    "function": {
        "name": "check_trade_financing",
        "description": (
            "Check the status of a financed trade: advance amount, settlement "
            "status, fee breakdown, and deadline. Use when a cooperative asks "
            "'has my advance been settled?', 'what is the status of trade 5?', "
            "'check my financing', 'when does my trade expire?'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "trade_id": {
                    "type": "integer",
                    "description": "On-chain trade ID from the escrow contract",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number to look up associated trade",
                },
            },
            "required": [],
        },
    },
}

# Tool: confirm_trade_delivery  (WRITE - buyer confirms coffee delivery)
# ---------------------------------------------------------------------------
CONFIRM_TRADE_DELIVERY = {
    "type": "function",
    "function": {
        "name": "confirm_trade_delivery",
        "description": (
            "Buyer confirms coffee delivery and releases payment from escrow. "
            "This settles the trade: remaining 20% goes to cooperative, "
            "fees are distributed to investors, and collateral is unlocked. "
            "Use when a buyer says 'confirm delivery', 'coffee arrived', "
            "'shipment received', 'release payment for trade X'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "trade_id": {
                    "type": "integer",
                    "description": "On-chain trade ID from escrow contract",
                },
                "acceptance_number": {
                    "type": "string",
                    "description": "Acceptance number to look up associated trade",
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tool: request_don_attestation
# ---------------------------------------------------------------------------
REQUEST_DON_ATTESTATION = {
    "type": "function",
    "function": {
        "name": "request_don_attestation",
        "description": (
            "Request a Chainlink DON-attested deforestation check for a farm. "
            "This triggers the CRE workflow which verifies via satellite imagery "
            "(Global Forest Watch) across multiple DON nodes and writes the "
            "attestation on-chain. Use when a new batch is created and the farm "
            "needs EUDR deforestation verification, or when the user asks "
            "'check deforestation for farm X', 'get DON attestation', "
            "'verify my farm with Chainlink'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "farm_id": {
                    "type": "string",
                    "description": "Farmer ID to request attestation for (e.g. FARMER-001)",
                },
            },
            "required": ["farm_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: check_don_attestation
# ---------------------------------------------------------------------------
CHECK_DON_ATTESTATION = {
    "type": "function",
    "function": {
        "name": "check_don_attestation",
        "description": (
            "Read a DON-attested deforestation result from the blockchain. "
            "Returns the Chainlink DON's attestation including risk level, "
            "EUDR compliance status, and tree loss data - all verified by "
            "multiple oracle nodes and written on-chain. Use when user asks "
            "'is my farm compliant', 'what did the DON say about my farm', "
            "'check attestation status', 'EUDR status from blockchain'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "farm_id": {
                    "type": "string",
                    "description": "Farmer ID to check attestation for",
                },
            },
            "required": ["farm_id"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: get_don_provenance_metrics
# ---------------------------------------------------------------------------
GET_DON_PROVENANCE_METRICS = {
    "type": "function",
    "function": {
        "name": "get_don_provenance_metrics",
        "description": (
            "Read the latest DON-attested provenance metrics from the blockchain. "
            "These are aggregated supply-chain statistics (total farmers, batches, "
            "EUDR compliance percentage, etc.) verified by the Chainlink DON every "
            "5 minutes and written on-chain. Use when user asks 'how many farmers', "
            "'supply chain stats', 'platform metrics', 'overall compliance rate', "
            "'DON provenance report'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


# ---------------------------------------------------------------------------
# All tools grouped
# ---------------------------------------------------------------------------
SUPPLY_CHAIN_TOOLS: List[Dict[str, Any]] = [
    # Core supply chain (Agent #1)
    RECORD_COMMISSION,
    RECORD_SHIPMENT,
    RECORD_RECEIPT,
    RECORD_TRANSFORMATION,
    PACK_BATCHES,
    UNPACK_BATCHES,
    SPLIT_BATCH,
    QUERY_BATCHES,
    SEARCH_KNOWLEDGE,
    # Marketplace (Agent #3)
    CREATE_RFQ,
    BROWSE_RFQS,
    SUBMIT_OFFER,
    ACCEPT_OFFER,
    LIST_MY_OFFERS,
    # Container marketplace (Agent #3b)
    BROWSE_CONTAINERS,
    PURCHASE_CONTAINER,
    # Container pools - shared buying (Agent #3c)
    BROWSE_POOLS,
    COMMIT_TO_POOL,
    LIST_MY_COMMITMENTS,
    # Compliance (Agent #4)
    CHECK_EUDR_COMPLIANCE,
    CHECK_MASS_BALANCE,
    # DPP / Traceability (Agent #5)
    GET_DPP,
    GET_CONTAINER_DPP,
    TRACE_LINEAGE,
    VALIDATE_DPP,
    # Verification (Agent #6)
    LIST_PENDING_VERIFICATIONS,
    VERIFY_BATCH,
    # Blockchain (Agent #7)
    CHECK_BLOCKCHAIN_ANCHOR,
    GET_TOKEN_INFO,
    VERIFY_BATCH_HASH,
    # Chainlink CRE / DON Attestation (Agent #8)
    REQUEST_DON_ATTESTATION,
    CHECK_DON_ATTESTATION,
    GET_DON_PROVENANCE_METRICS,
    # Settlement / Payment (Agent #9)
    CONFIRM_PAYMENT,
    CHECK_PAYMENT_STATUS,
    RECORD_COOPERATIVE_PAYOUT,
    CONFIRM_PAYMENT_RECEIVED,
    # DeFi Financing Pool (Agent #10)
    CHECK_FINANCING_POOL,
    REQUEST_FINANCING_ADVANCE,
    CHECK_TRADE_FINANCING,
    CONFIRM_TRADE_DELIVERY,
]

