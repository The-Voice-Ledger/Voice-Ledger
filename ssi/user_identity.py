"""
User Identity Management for Telegram Users

Handles auto-generation of DIDs for Telegram users and manages their identities.
Implements Option B: Auto-Generated DID approach for zero-friction onboarding.
"""

import os
import base64
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from database.models import UserIdentity
from ssi.did.did_key import generate_did_key


def get_or_create_user_identity(
    telegram_user_id: str,
    telegram_username: str = None,
    telegram_first_name: str = None,
    telegram_last_name: str = None,
    db_session: Session = None
) -> dict:
    """
    Get existing user identity or create new one with auto-generated DID.
    
    This implements zero-friction onboarding: farmers don't need to manage
    private keys or understand DIDs. We generate and encrypt their keys
    automatically on first interaction.
    
    Args:
        telegram_user_id: Telegram user ID (unique identifier)
        telegram_username: Optional Telegram @username
        telegram_first_name: User's first name from Telegram
        telegram_last_name: User's last name from Telegram
        db_session: Database session (optional, creates new if not provided)
        
    Returns:
        Dictionary with:
        - user_id: Database ID
        - telegram_user_id: Telegram user ID
        - did: User's DID
        - public_key: User's public key (for verification)
        - created: Whether user was newly created (True) or existing (False)
        
    Example:
        >>> from database.models import SessionLocal
        >>> db = SessionLocal()
        >>> identity = get_or_create_user_identity("123456", "farmer_john", db_session=db)
        >>> print(f"User DID: {identity['did']}")
    """
    # Create session if not provided
    close_session = False
    if db_session is None:
        from database.models import SessionLocal
        db_session = SessionLocal()
        close_session = True
    
    try:
        # Check if user already exists
        user = db_session.query(UserIdentity).filter_by(
            telegram_user_id=str(telegram_user_id)
        ).first()
        
        if user:
            # Update last active timestamp
            user.last_active_at = datetime.utcnow()
            # Update user info if changed
            if telegram_username and telegram_username != user.telegram_username:
                user.telegram_username = telegram_username
            if telegram_first_name and telegram_first_name != user.telegram_first_name:
                user.telegram_first_name = telegram_first_name
            if telegram_last_name and telegram_last_name != user.telegram_last_name:
                user.telegram_last_name = telegram_last_name
            
            db_session.commit()
            
            return {
                "user_id": user.id,
                "telegram_user_id": user.telegram_user_id,
                "did": user.did,
                "public_key": user.public_key,
                "created": False
            }
        
        # Generate new DID for user
        identity = generate_did_key()
        
        # Encrypt private key (using app secret as encryption key)
        encryption_key = _get_encryption_key()
        fernet = Fernet(encryption_key)
        encrypted_private_key = fernet.encrypt(identity["private_key"].encode()).decode()
        
        # Create new user record
        new_user = UserIdentity(
            telegram_user_id=str(telegram_user_id),
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
            did=identity["did"],
            encrypted_private_key=encrypted_private_key,
            public_key=identity["public_key"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_active_at=datetime.utcnow()
        )
        
        db_session.add(new_user)
        db_session.commit()
        db_session.refresh(new_user)
        
        return {
            "user_id": new_user.id,
            "telegram_user_id": new_user.telegram_user_id,
            "did": new_user.did,
            "public_key": new_user.public_key,
            "created": True
        }
        
    finally:
        if close_session:
            db_session.close()


def get_user_private_key(user_id: int, db_session: Session = None) -> str:
    """
    Decrypt and retrieve user's private key.
    
    WARNING: Only use for signing operations. Never expose to client.
    
    Args:
        user_id: Database user ID
        db_session: Database session (optional)
        
    Returns:
        Decrypted private key as hex string
    """
    close_session = False
    if db_session is None:
        from database.models import SessionLocal
        db_session = SessionLocal()
        close_session = True
    
    try:
        user = db_session.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Decrypt private key
        encryption_key = _get_encryption_key()
        fernet = Fernet(encryption_key)
        decrypted_key = fernet.decrypt(user.encrypted_private_key.encode()).decode()
        
        return decrypted_key
        
    finally:
        if close_session:
            db_session.close()


def get_user_by_telegram_id(telegram_user_id: str, db_session: Session = None) -> UserIdentity:
    """
    Retrieve user identity by Telegram user ID.
    
    Args:
        telegram_user_id: Telegram user ID
        db_session: Database session (optional)
        
    Returns:
        UserIdentity object or None if not found
    """
    close_session = False
    if db_session is None:
        from database.models import SessionLocal
        db_session = SessionLocal()
        close_session = True
    
    try:
        return db_session.query(UserIdentity).filter_by(
            telegram_user_id=str(telegram_user_id)
        ).first()
    finally:
        if close_session:
            db_session.close()


def get_user_by_did(did: str, db_session: Session = None) -> UserIdentity:
    """
    Retrieve user identity by DID.
    
    Args:
        did: Decentralized Identifier (e.g., did:key:z6Mk...)
        db_session: Database session (optional)
        
    Returns:
        UserIdentity object or None if not found
    """
    close_session = False
    if db_session is None:
        from database.models import SessionLocal
        db_session = SessionLocal()
        close_session = True
    
    try:
        return db_session.query(UserIdentity).filter_by(did=did).first()
    finally:
        if close_session:
            db_session.close()


def get_or_create_user_gln(user_id: int, db_session: Session = None) -> str:
    """
    Get or create a Global Location Number (GLN) for a user.
    
    GLN Format: 13 digits (company_prefix + location_ref + check_digit)
    We use user_id as the location reference for deterministic GLN generation.
    
    Args:
        user_id: Database user ID
        db_session: Database session (optional)
        
    Returns:
        13-digit GLN string
        
    Example:
        >>> gln = get_or_create_user_gln(42)
        >>> print(gln)  # e.g., "0614141000429"
    """
    from gs1.identifiers import gln as generate_gln
    
    close_session = False
    if db_session is None:
        from database.models import SessionLocal
        db_session = SessionLocal()
        close_session = True
    
    try:
        user = db_session.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # If GLN already exists, return it
        if user.gln:
            return user.gln
        
        # Generate GLN using user_id as location reference
        # Pad user_id to 5 digits for location code
        location_ref = str(user_id).zfill(5)
        gln = generate_gln(location_ref)
        
        # Store GLN in database
        user.gln = gln
        db_session.commit()
        
        return gln
        
    finally:
        if close_session:
            db_session.close()


def _get_encryption_key() -> bytes:
    """
    Get or generate encryption key for private key storage.
    
    In production, this should be stored in a secure vault (e.g., AWS KMS, HashiCorp Vault).
    For now, we derive it from app secret in .env
    """
    secret = os.getenv("APP_SECRET_KEY", "voice-ledger-default-secret-change-in-production")
    
    # Derive Fernet key from secret (Fernet requires 32 url-safe base64 bytes)
    from hashlib import sha256
    key_material = sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_material)


if __name__ == "__main__":
    # Test user identity creation
    print("Testing User Identity Management...\n")
    
    from database.models import SessionLocal
    db = SessionLocal()
    
    # Create test user
    identity = get_or_create_user_identity(
        telegram_user_id="test_user_123",
        telegram_username="test_farmer",
        telegram_first_name="Abebe",
        telegram_last_name="Fekadu",
        db_session=db
    )
    
    print(f"✓ User {'created' if identity['created'] else 'retrieved'}")
    print(f"  DID: {identity['did']}")
    print(f"  Public Key: {identity['public_key'][:20]}...")
    print(f"  Telegram ID: {identity['telegram_user_id']}")
    
    # Test retrieval
    identity2 = get_or_create_user_identity("test_user_123", db_session=db)
    print(f"\n✓ Second call retrieved existing user: {not identity2['created']}")
    
    db.close()
