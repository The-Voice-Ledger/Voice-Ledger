"""
Verifiable Credential Verification Module

Verifies the cryptographic integrity and authenticity of credentials.
"""

import json
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


def verify_credential(vc: dict) -> tuple[bool, str]:
    """
    Verify a verifiable credential's cryptographic signature.
    
    Args:
        vc: Verifiable credential dictionary
        
    Returns:
        Tuple of (is_valid, message)
        - is_valid: True if signature is valid
        - message: Success message or error description
        
    Verification checks:
    1. Credential has required fields
    2. Signature is present
    3. Issuer's public key matches verification method
    4. Signature is cryptographically valid
        
    Example:
        >>> is_valid, msg = verify_credential(credential)
        >>> if is_valid:
        ...     print("✅ Credential is valid")
        ... else:
        ...     print(f"❌ Verification failed: {msg}")
    """
    # Check required fields
    required_fields = ["issuer", "credentialSubject", "proof"]
    for field in required_fields:
        if field not in vc:
            return False, f"Missing required field: {field}"
    
    # Extract proof
    proof = vc.get("proof", {})
    signature_hex = proof.get("signature")
    verification_method = proof.get("verificationMethod")
    
    if not signature_hex:
        return False, "Missing signature in proof"
    
    if not verification_method:
        return False, "Missing verificationMethod in proof"
    
    # Verify that issuer matches verification method
    issuer = vc.get("issuer")
    if issuer != verification_method:
        return False, "Issuer does not match verification method"
    
    try:
        # Reconstruct canonical credential (without proof)
        credential_without_proof = {k: v for k, v in vc.items() if k != "proof"}
        payload = json.dumps(credential_without_proof, separators=(",", ":"), sort_keys=True)
        
        # Verify signature
        vk = VerifyKey(bytes.fromhex(verification_method))
        signature = bytes.fromhex(signature_hex)
        vk.verify(payload.encode("utf-8"), signature)
        
        return True, "Credential signature is valid"
        
    except BadSignatureError:
        return False, "Invalid signature - credential has been tampered with"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    from ssi.credentials.issue import issue_credential
    
    print("Testing Credential Verification...\n")
    
    # Issue a credential
    issuer = generate_did_key()
    farmer = generate_did_key()
    
    claims = {
        "type": "FarmerCredential",
        "name": "Test Farmer",
        "farm_id": "TEST-001",
        "did": farmer["did"]
    }
    
    vc = issue_credential(claims, issuer["private_key"])
    print("Issued credential for:", claims["name"])
    
    # Verify the credential
    is_valid, message = verify_credential(vc)
    
    if is_valid:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    
    # Test tampering detection
    print("\nTesting tampering detection...")
    vc["credentialSubject"]["name"] = "Tampered Name"
    is_valid, message = verify_credential(vc)
    
    if not is_valid:
        print(f"✅ Tampering detected: {message}")
    else:
        print(f"❌ Failed to detect tampering")
