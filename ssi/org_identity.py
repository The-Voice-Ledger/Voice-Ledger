"""
Organization Identity Management - DID Generation for Organizations

Organizations (cooperatives, exporters, buyers) need DIDs to act as 
credential issuers. This module generates did:key DIDs with Ed25519 
key pairs, similar to user DIDs but with organizational context.
"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)


def generate_organization_did():
    """
    Generate a did:key DID with Ed25519 key pair for an organization.
    
    Returns:
        dict: {
            'did': 'did:key:z6Mk...',
            'public_key': base64 encoded public key,
            'encrypted_private_key': Fernet encrypted private key
        }
    
    Example:
        >>> org_identity = generate_organization_did()
        >>> org_identity['did']
        'did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH'
    """
    try:
        # Generate Ed25519 key pair (same as user DIDs)
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys to bytes
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Create did:key from public key (multibase multicodec format)
        # Ed25519 public key multicodec: 0xed (237 in decimal)
        # Multibase base58btc prefix: 'z'
        multicodec_prefix = bytes([0xed, 0x01])  # Ed25519 public key
        multicodec_pubkey = multicodec_prefix + public_key_bytes
        
        # Base58 encode (Bitcoin alphabet)
        did_suffix = base58_encode(multicodec_pubkey)
        did = f"did:key:z{did_suffix}"
        
        # Encrypt private key with app secret
        encrypted_private_key = encrypt_private_key(private_key_bytes)
        
        # Base64 encode public key for storage
        public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
        
        logger.info(f"Generated organization DID: {did[:30]}...")
        
        return {
            'did': did,
            'public_key': public_key_b64,
            'encrypted_private_key': encrypted_private_key
        }
        
    except Exception as e:
        logger.error(f"Failed to generate organization DID: {e}", exc_info=True)
        raise


def encrypt_private_key(private_key_bytes: bytes) -> str:
    """
    Encrypt organization private key using app secret key.
    
    Args:
        private_key_bytes: Raw Ed25519 private key (32 bytes)
        
    Returns:
        str: Encrypted private key (base64 encoded Fernet token)
    """
    # Get encryption key from environment (same key used for user DIDs)
    secret_key = os.getenv('APP_SECRET_KEY')
    if not secret_key:
        raise ValueError("APP_SECRET_KEY not set in environment")
    
    # Derive Fernet key from secret (must be 32 bytes, base64 encoded)
    key_bytes = hashlib.sha256(secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    
    # Encrypt private key
    fernet = Fernet(fernet_key)
    encrypted = fernet.encrypt(private_key_bytes)
    
    return encrypted.decode('utf-8')


def decrypt_organization_private_key(encrypted_private_key: str) -> bytes:
    """
    Decrypt organization private key for signing credentials.
    
    Args:
        encrypted_private_key: Base64 encoded Fernet token
        
    Returns:
        bytes: Raw Ed25519 private key (32 bytes)
    """
    secret_key = os.getenv('APP_SECRET_KEY')
    if not secret_key:
        raise ValueError("APP_SECRET_KEY not set in environment")
    
    # Derive Fernet key
    key_bytes = hashlib.sha256(secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    
    # Decrypt
    fernet = Fernet(fernet_key)
    decrypted = fernet.decrypt(encrypted_private_key.encode())
    
    return decrypted


def base58_encode(data: bytes) -> str:
    """
    Encode bytes to base58 (Bitcoin alphabet).
    
    Args:
        data: Bytes to encode
        
    Returns:
        str: Base58 encoded string
    """
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    
    # Convert bytes to integer
    num = int.from_bytes(data, 'big')
    
    # Encode to base58
    encoded = ''
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded = alphabet[remainder] + encoded
    
    # Handle leading zeros
    for byte in data:
        if byte == 0:
            encoded = '1' + encoded
        else:
            break
    
    return encoded or '1'


def verify_organization_did(did: str, public_key_b64: str) -> bool:
    """
    Verify that a DID matches its public key.
    
    Args:
        did: The did:key DID to verify
        public_key_b64: Base64 encoded public key
        
    Returns:
        bool: True if DID is valid for the public key
    """
    try:
        # Decode public key
        public_key_bytes = base64.b64decode(public_key_b64)
        
        # Reconstruct expected DID
        multicodec_prefix = bytes([0xed, 0x01])
        multicodec_pubkey = multicodec_prefix + public_key_bytes
        expected_suffix = base58_encode(multicodec_pubkey)
        expected_did = f"did:key:z{expected_suffix}"
        
        return did == expected_did
        
    except Exception as e:
        logger.error(f"DID verification failed: {e}")
        return False


# Export functions
__all__ = [
    'generate_organization_did',
    'encrypt_private_key',
    'decrypt_organization_private_key',
    'verify_organization_did'
]
