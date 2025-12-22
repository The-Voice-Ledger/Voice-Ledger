"""
Batch Photo Upload Session Management

Tracks users who just created batches and are expected to upload verification photos.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# In-memory storage for batch photo upload sessions
# {user_id: {"batch_id": int, "batch_number": str, "expires_at": datetime}}
batch_photo_sessions: Dict[int, Dict[str, Any]] = {}

# Session timeout (30 minutes)
SESSION_TIMEOUT_MINUTES = 30


def create_batch_photo_session(user_id: int, batch_id: int, batch_number: str) -> None:
    """
    Create a session for batch photo upload after user records a batch.
    
    Args:
        user_id: Telegram user ID
        batch_id: Database batch ID
        batch_number: Human-readable batch number (for display)
    """
    batch_photo_sessions[user_id] = {
        "batch_id": batch_id,
        "batch_number": batch_number,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    }
    logger.info(f"Created batch photo session for user {user_id}, batch {batch_id}")


def get_batch_photo_session(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get active batch photo upload session for user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Session dict or None if not found/expired
    """
    if user_id not in batch_photo_sessions:
        return None
    
    session = batch_photo_sessions[user_id]
    
    # Check if expired
    if datetime.utcnow() > session['expires_at']:
        logger.info(f"Batch photo session expired for user {user_id}")
        batch_photo_sessions.pop(user_id, None)
        return None
    
    return session


def clear_batch_photo_session(user_id: int) -> None:
    """
    Clear batch photo upload session for user.
    
    Args:
        user_id: Telegram user ID
    """
    if user_id in batch_photo_sessions:
        logger.info(f"Cleared batch photo session for user {user_id}")
        batch_photo_sessions.pop(user_id)


def has_active_session(user_id: int) -> bool:
    """
    Check if user has an active batch photo upload session.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if active session exists
    """
    return get_batch_photo_session(user_id) is not None
