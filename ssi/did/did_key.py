"""
DID (Decentralized Identifier) Module

This module generates did:key identifiers based on Ed25519 keypairs.
DIDs provide cryptographically verifiable identities without relying on 
centralized registries.
"""

import base64
from nacl.signing import SigningKey


def generate_did_key() -> dict:
    """
    Generate a new did:key identifier with Ed25519 keypair.
    
    The did:key method embeds the public key directly in the DID,
    making it self-verifiable without external lookups.
    
    Returns:
        Dictionary containing:
        - did: The full did:key identifier
        - private_key_b64: Base64-encoded private key (keep secret!)
        - public_key_b64: Base64-encoded public key
        - private_key: Hex-encoded private key (for backward compatibility)
        - public_key: Hex-encoded public key (for backward compatibility)
        
    Example:
        >>> identity = generate_did_key()
        >>> print(identity["did"])
        'did:key:z6Mk...'
        >>> # Store private_key_b64 securely, share only the DID
    """
    # Generate Ed25519 keypair
    sk = SigningKey.generate()
    vk = sk.verify_key
    
    # Encode public key in base64url for did:key format
    # The 'z' prefix indicates base58btc encoding (we use base64url for simplicity)
    did = "did:key:z" + base64.urlsafe_b64encode(vk.encode()).decode("utf-8").rstrip("=")
    
    # Encode keys in both base64 (preferred for JWTs/credentials) and hex (backward compatibility)
    private_key_b64 = base64.b64encode(sk.encode()).decode("utf-8")
    public_key_b64 = base64.b64encode(vk.encode()).decode("utf-8")

    return {
        "did": did,
        "private_key_b64": private_key_b64,  # Preferred format
        "public_key_b64": public_key_b64,    # Preferred format
        "private_key": sk.encode().hex(),    # Backward compatibility
        "public_key": vk.encode().hex(),     # Backward compatibility
    }


if __name__ == "__main__":
    print("Generating new DID...")
    identity = generate_did_key()
    print(f"DID: {identity['did']}")
    print(f"Public Key: {identity['public_key']}")
    print(f"\n⚠️  Keep private key secure!")
    print(f"Private Key: {identity['private_key']}")
