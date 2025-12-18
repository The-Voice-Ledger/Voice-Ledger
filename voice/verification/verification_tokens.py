"""
Verification Token Generation and Management

Generates unique verification tokens for batch verification workflow.
Format: VRF-{random_8_chars}-{batch_id_hash}
"""

import secrets
import hashlib
from datetime import datetime, timedelta


def generate_verification_token(batch_id: str) -> str:
    """
    Generate unique verification token for a batch.
    
    Format: VRF-{random_8_chars}-{batch_id_hash}
    Example: VRF-K7M2P9QR-3F8A2B1C
    
    Args:
        batch_id: Unique batch identifier
        
    Returns:
        Verification token string (32 characters)
    """
    # Generate 8 random characters (alphanumeric, uppercase)
    random_part = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
    
    # Hash batch_id to get deterministic suffix (first 8 hex chars)
    batch_hash = hashlib.sha256(batch_id.encode()).hexdigest()[:8].upper()
    
    return f"VRF-{random_part}-{batch_hash}"


def get_verification_expiration(hours: int = 48) -> datetime:
    """
    Calculate verification token expiration time.
    
    Args:
        hours: Hours until expiration (default: 48)
        
    Returns:
        Expiration datetime
    """
    return datetime.utcnow() + timedelta(hours=hours)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Check if verification token has expired.
    
    Args:
        expires_at: Token expiration datetime
        
    Returns:
        True if expired, False otherwise
    """
    return datetime.utcnow() > expires_at


def is_token_valid(verification_token: str) -> bool:
    """
    Validate verification token format.
    
    Args:
        verification_token: Token to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    if not verification_token:
        return False
    
    parts = verification_token.split('-')
    if len(parts) != 3:
        return False
    
    prefix, random_part, hash_part = parts
    
    # Check prefix
    if prefix != 'VRF':
        return False
    
    # Check random part (8 alphanumeric chars)
    if len(random_part) != 8 or not random_part.isalnum():
        return False
    
    # Check hash part (8 hexadecimal chars)
    if len(hash_part) != 8 or not all(c in '0123456789ABCDEF' for c in hash_part):
        return False
    
    return True
