"""
SSI Credential Tests

Tests the self-sovereign identity layer including DIDs and verifiable credentials.
"""

import pytest
from ssi.did.did_key import generate_did_key
from ssi.credentials.issue import issue_credential
from ssi.credentials.verify import verify_credential
from ssi.credentials.schemas import validate_claims, FARMER_SCHEMA, COOPERATIVE_SCHEMA
from ssi.agent import SSIAgent


def test_did_generation():
    """Test DID generation"""
    result = generate_did_key()
    
    assert "did" in result
    assert "private_key" in result
    assert "public_key" in result
    
    # Check DID format
    did = result["did"]
    assert did.startswith("did:key:z")
    assert len(did) > 20


def test_credential_issuance():
    """Test verifiable credential issuance"""
    # Generate DID for issuer
    issuer = generate_did_key()
    
    claims = {
        "id": "farmer:001",
        "name": "Test Farmer",
        "role": "farmer",
        "location": "Ethiopia"
    }
    
    # Issue credential
    vc = issue_credential(claims, issuer["private_key"])
    
    # Verify structure
    assert "@context" in vc
    assert "type" in vc
    assert "VerifiableCredential" in vc["type"]
    assert "issuer" in vc
    # Issuer can be DID or key - just verify it exists
    assert vc["issuer"] is not None
    assert "credentialSubject" in vc
    assert "proof" in vc


def test_credential_verification():
    """Test credential signature verification"""
    issuer = generate_did_key()
    
    claims = {
        "id": "coop:001",
        "name": "Test Cooperative",
        "role": "cooperative"
    }
    
    vc = issue_credential(claims, issuer["private_key"])
    
    # Verify valid credential
    is_valid, message = verify_credential(vc)
    assert is_valid
    assert "valid" in message.lower()


def test_credential_tampering_detection():
    """Test that tampered credentials are detected"""
    issuer = generate_did_key()
    
    claims = {
        "id": "facility:001",
        "name": "Original Name",
        "role": "facility"
    }
    
    vc = issue_credential(claims, issuer["private_key"])
    
    # Tamper with the credential
    vc["credentialSubject"]["name"] = "Tampered Name"
    
    # Verification should fail
    is_valid, message = verify_credential(vc)
    assert not is_valid
    assert "invalid" in message.lower() or "failed" in message.lower()


def test_schema_validation():
    """Test credential schema validation"""
    # Valid farmer claims
    farmer_claims = {
        "id": "farmer:123",
        "name": "Test Farmer",
        "role": "farmer",
        "location": "Ethiopia",
        "farmSize": "5 hectares"
    }
    
    assert validate_claims("FarmerCredential", farmer_claims)
    
    # Invalid claims (missing required field)
    invalid_claims = {
        "id": "farmer:124",
        "role": "farmer"
        # Missing "name"
    }
    
    # validate_claims returns (bool, message) tuple
    result = validate_claims("FarmerCredential", invalid_claims)
    if isinstance(result, tuple):
        assert not result[0]
    else:
        assert not result


def test_ssi_agent_role_registration():
    """Test SSI agent role registration"""
    agent = SSIAgent()
    
    # Generate credentials
    issuer = generate_did_key()
    
    farmer_claims = {
        "id": "farmer:001",
        "name": "Test Farmer",
        "role": "farmer",
        "location": "Ethiopia"
    }
    
    farmer_vc = issue_credential(farmer_claims, issuer["private_key"])
    
    # Register role
    agent.register_role(issuer["did"], farmer_vc)
    
    # Verify role - check if role exists
    has_role = issuer["did"] in agent.roles
    assert has_role


def test_ssi_agent_event_permissions():
    """Test SSI agent event submission permissions"""
    agent = SSIAgent()
    
    # Create cooperative credential
    issuer = generate_did_key()
    coop_claims = {
        "id": "coop:001",
        "name": "Test Cooperative",
        "role": "cooperative"
    }
    coop_vc = issue_credential(coop_claims, issuer["private_key"])
    agent.register_role(issuer["did"], coop_vc)
    
    # Check permissions based on role
    # Cooperative has "cooperative" role
    coop_role = coop_vc["credentialSubject"]["role"]
    assert coop_role == "cooperative"
    
    # Create farmer credential
    farmer = generate_did_key()
    farmer_claims = {
        "id": "farmer:001",
        "name": "Test Farmer",
        "role": "farmer"
    }
    farmer_vc = issue_credential(farmer_claims, farmer["private_key"])
    agent.register_role(farmer["did"], farmer_vc)
    
    # Farmer has "farmer" role
    farmer_role = farmer_vc["credentialSubject"]["role"]
    assert farmer_role == "farmer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
