"""
Verifiable Credential Schemas

Defines the structure of credentials used in the Voice Ledger system.
Each credential type has specific claims that can be verified.
"""

# Farmer Identity Credential
FARMER_SCHEMA = {
    "type": "FarmerCredential",
    "description": "Verifies the identity of a coffee farmer",
    "claims": ["name", "farm_id", "country", "did"],
    "required": ["name", "farm_id", "did"]
}

# Facility Location Credential
FACILITY_SCHEMA = {
    "type": "FacilityCredential",
    "description": "Verifies a facility's identity and location",
    "claims": ["facility_name", "facility_type", "gln", "did"],
    "required": ["facility_name", "gln", "did"]
}

# Due Diligence Credential
DUE_DILIGENCE_SCHEMA = {
    "type": "DueDiligenceCredential",
    "description": "Certifies due diligence checks for EUDR compliance",
    "claims": ["batch_id", "geolocation", "verified_by", "timestamp"],
    "required": ["batch_id", "geolocation", "verified_by", "timestamp"]
}

# Cooperative Role Credential
COOPERATIVE_SCHEMA = {
    "type": "CooperativeCredential",
    "description": "Identifies a cooperative and its role",
    "claims": ["cooperative_name", "role", "country", "did"],
    "required": ["cooperative_name", "role", "did"]
}


def get_schema(credential_type: str) -> dict:
    """
    Retrieve a credential schema by type.
    
    Args:
        credential_type: Type of credential (e.g., "FarmerCredential")
        
    Returns:
        Schema dictionary or None if not found
    """
    schemas = {
        "FarmerCredential": FARMER_SCHEMA,
        "FacilityCredential": FACILITY_SCHEMA,
        "DueDiligenceCredential": DUE_DILIGENCE_SCHEMA,
        "CooperativeCredential": COOPERATIVE_SCHEMA
    }
    return schemas.get(credential_type)


def validate_claims(credential_type: str, claims: dict) -> tuple[bool, str]:
    """
    Validate that claims match the schema requirements.
    
    Args:
        credential_type: Type of credential
        claims: Dictionary of claim key-value pairs
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    schema = get_schema(credential_type)
    if not schema:
        return False, f"Unknown credential type: {credential_type}"
    
    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in claims:
            return False, f"Missing required claim: {field}"
    
    # Check that all provided claims are in schema
    allowed = schema.get("claims", [])
    for claim_key in claims.keys():
        if claim_key not in allowed:
            return False, f"Unknown claim: {claim_key}"
    
    return True, ""


if __name__ == "__main__":
    print("Available Credential Schemas:\n")
    for schema_name in ["FarmerCredential", "FacilityCredential", "DueDiligenceCredential", "CooperativeCredential"]:
        schema = get_schema(schema_name)
        print(f"📋 {schema['type']}")
        print(f"   {schema['description']}")
        print(f"   Claims: {', '.join(schema['claims'])}")
        print(f"   Required: {', '.join(schema['required'])}\n")
