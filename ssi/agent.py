"""
SSI Agent - Self-Sovereign Identity Management

Manages DIDs, credentials, and role-based access control for the Voice Ledger system.
"""

from typing import Optional
from ssi.credentials.verify import verify_credential


class SSIAgent:
    """
    Agent for managing decentralized identities and role-based access control.
    
    The agent maintains a registry of DIDs and their associated roles, and
    enforces access control based on verifiable credentials.
    """
    
    def __init__(self):
        """Initialize the SSI agent with empty registries."""
        self.roles = {}  # Maps DID -> role
        self.trusted_issuers = set()  # Set of trusted issuer public keys
    
    def register_role(self, did: str, role: str):
        """
        Register a DID with a specific role.
        
        Args:
            did: Decentralized identifier
            role: Role name (e.g., "farmer", "cooperative", "auditor")
        """
        self.roles[did] = role
        print(f"✅ Registered {did[:30]}... as {role}")
    
    def add_trusted_issuer(self, issuer_public_key: str):
        """
        Add a trusted credential issuer.
        
        Args:
            issuer_public_key: Hex-encoded public key of trusted issuer
        """
        self.trusted_issuers.add(issuer_public_key)
        print(f"✅ Added trusted issuer: {issuer_public_key[:20]}...")
    
    def verify_role(self, did: str, vc: dict, expected_role: str) -> tuple[bool, str]:
        """
        Verify that a DID has a specific role based on its credential.
        
        Args:
            did: Decentralized identifier to check
            vc: Verifiable credential
            expected_role: Required role (e.g., "farmer", "cooperative")
            
        Returns:
            Tuple of (is_authorized, message)
        """
        # First verify the credential is cryptographically valid
        is_valid, msg = verify_credential(vc)
        if not is_valid:
            return False, f"Invalid credential: {msg}"
        
        # Check if issuer is trusted
        issuer = vc.get("issuer")
        if issuer not in self.trusted_issuers:
            return False, f"Untrusted issuer: {issuer[:20]}..."
        
        # Check if DID is registered
        if did not in self.roles:
            return False, f"DID not registered: {did[:30]}..."
        
        # Check role matches
        actual_role = self.roles[did]
        if actual_role != expected_role:
            return False, f"Insufficient permissions: has '{actual_role}', needs '{expected_role}'"
        
        return True, f"Authorized as {expected_role}"
    
    def can_submit_event(self, did: str, vc: dict, event_type: str) -> tuple[bool, str]:
        """
        Check if a DID can submit a specific event type.
        
        Args:
            did: Decentralized identifier
            vc: Verifiable credential
            event_type: EPCIS event type (e.g., "commissioning", "shipment")
            
        Returns:
            Tuple of (is_authorized, message)
        """
        # Define which roles can submit which events
        event_permissions = {
            "commissioning": ["cooperative", "facility"],
            "shipment": ["cooperative", "facility", "farmer"],
            "receipt": ["cooperative", "facility"],
            "transformation": ["facility"]
        }
        
        allowed_roles = event_permissions.get(event_type, [])
        if not allowed_roles:
            return False, f"Unknown event type: {event_type}"
        
        # Verify credential
        is_valid, msg = verify_credential(vc)
        if not is_valid:
            return False, f"Invalid credential: {msg}"
        
        # Check issuer trust
        issuer = vc.get("issuer")
        if issuer not in self.trusted_issuers:
            return False, "Untrusted issuer"
        
        # Check if DID has required role
        actual_role = self.roles.get(did)
        if not actual_role:
            return False, "DID not registered"
        
        if actual_role not in allowed_roles:
            return False, f"Role '{actual_role}' cannot submit '{event_type}' events"
        
        return True, f"Authorized to submit {event_type} event"


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    from ssi.credentials.issue import issue_credential
    
    print("=== Testing SSI Agent ===\n")
    
    # Setup: Create Guzo Cooperative as trusted issuer
    guzo = generate_did_key()
    agent = SSIAgent()
    agent.add_trusted_issuer(guzo["public_key"])
    
    # Create a farmer identity
    farmer = generate_did_key()
    farmer_claims = {
        "type": "FarmerCredential",
        "name": "Abebe Fekadu",
        "farm_id": "ETH-001",
        "did": farmer["did"]
    }
    farmer_vc = issue_credential(farmer_claims, guzo["private_key"])
    agent.register_role(farmer["did"], "farmer")
    
    # Create a cooperative identity
    coop = generate_did_key()
    coop_claims = {
        "type": "CooperativeCredential",
        "cooperative_name": "Guzo Union",
        "role": "cooperative",
        "did": coop["did"]
    }
    coop_vc = issue_credential(coop_claims, guzo["private_key"])
    agent.register_role(coop["did"], "cooperative")
    
    # Test authorization
    print("\nTest 1: Farmer submitting shipment event")
    can_submit, msg = agent.can_submit_event(farmer["did"], farmer_vc, "shipment")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
    
    print("\nTest 2: Farmer trying to submit commissioning event")
    can_submit, msg = agent.can_submit_event(farmer["did"], farmer_vc, "commissioning")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
    
    print("\nTest 3: Cooperative submitting commissioning event")
    can_submit, msg = agent.can_submit_event(coop["did"], coop_vc, "commissioning")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
