"""
Shared authentication and authorization utilities for verification system.
"""
import logging
from typing import Optional, Tuple
from database.models import UserIdentity

logger = logging.getLogger(__name__)


def verify_user_authorization(
    telegram_user_id: str,
    db
) -> Tuple[Optional[UserIdentity], Optional[str]]:
    """
    Verify that a user is authorized to verify batches.
    
    Args:
        telegram_user_id: Telegram user ID to authenticate
        db: Database session
        
    Returns:
        Tuple of (user, error_message)
        - If authorized: (UserIdentity, None)
        - If unauthorized: (None, error_message)
    """
    # 1. Check user exists
    user = db.query(UserIdentity).filter_by(
        telegram_user_id=telegram_user_id
    ).first()
    
    if not user:
        return None, "User not found. Please register with Voice Ledger first."
    
    # 2. Check approval status
    if not user.is_approved:
        return None, "Your account is pending admin approval."
    
    # 3. Check role permissions
    if user.role not in ['COOPERATIVE_MANAGER', 'ADMIN', 'EXPORTER']:
        logger.warning(
            f"User {telegram_user_id} (role={user.role}) attempted verification but lacks permissions"
        )
        return None, f"Insufficient permissions. Your role ({user.role}) cannot verify batches."
    
    # User is authorized
    return user, None
