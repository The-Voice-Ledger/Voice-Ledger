"""
Verifiable Credential Issuance Module

Issues verifiable credentials by signing claims with the issuer's private key.
"""

import json
import hashlib
from datetime import datetime, timezone
from nacl.signing import SigningKey


def issue_credential(claims: dict, issuer_private_key_hex: str) -> dict:
    """
    Issue a verifiable credential by signing the claims.
    
    Args:
        claims: Dictionary of claims to include in the credential
                Must include 'type' field matching a schema
        issuer_private_key_hex: Hex-encoded Ed25519 private key of the issuer
        
    Returns:
        Verifiable credential with structure:
        {
            "@context": [...],
            "type": ["VerifiableCredential", "<CredentialType>"],
            "issuer": "<issuer_public_key_hex>",
            "issuanceDate": "<ISO8601 timestamp>",
            "credentialSubject": {...claims...},
            "proof": {
                "type": "Ed25519Signature2020",
                "created": "<ISO8601 timestamp>",
                "proofPurpose": "assertionMethod",
                "verificationMethod": "<issuer_public_key_hex>",
                "signature": "<hex_signature>"
            }
        }
        
    Example:
        >>> from ssi.did.did_key import generate_did_key
        >>> issuer = generate_did_key()
        >>> claims = {
        ...     "type": "FarmerCredential",
        ...     "name": "Abebe Fekadu",
        ...     "farm_id": "ETH-SID-001",
        ...     "did": issuer["did"]
        ... }
        >>> vc = issue_credential(claims, issuer["private_key"])
    """
    # Load issuer's signing key
    sk = SigningKey(bytes.fromhex(issuer_private_key_hex))
    vk = sk.verify_key
    
    # Build credential structure
    issuance_date = datetime.now(timezone.utc).isoformat()
    
    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://voiceledger.org/credentials/v1"
        ],
        "type": ["VerifiableCredential", claims.get("type", "GenericCredential")],
        "issuer": vk.encode().hex(),
        "issuanceDate": issuance_date,
        "credentialSubject": {k: v for k, v in claims.items() if k != "type"}
    }
    
    # Create canonical representation for signing
    credential_canonical = json.dumps(credential, separators=(",", ":"), sort_keys=True)
    
    # Sign the credential
    signature = sk.sign(credential_canonical.encode("utf-8")).signature
    
    # Add proof
    credential["proof"] = {
        "type": "Ed25519Signature2020",
        "created": issuance_date,
        "proofPurpose": "assertionMethod",
        "verificationMethod": vk.encode().hex(),
        "signature": signature.hex()
    }

    return credential


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    
    print("Issuing a sample Farmer Credential...\n")
    
    # Generate issuer identity (e.g., Guzo Cooperative)
    issuer = generate_did_key()
    print(f"Issuer DID: {issuer['did']}\n")
    
    # Generate farmer identity
    farmer = generate_did_key()
    
    # Create claims
    claims = {
        "type": "FarmerCredential",
        "name": "Abebe Fekadu",
        "farm_id": "ETH-SID-001",
        "country": "Ethiopia",
        "did": farmer["did"]
    }
    
    # Issue credential
    vc = issue_credential(claims, issuer["private_key"])
    
    print("✅ Credential Issued:")
    print(json.dumps(vc, indent=2))
