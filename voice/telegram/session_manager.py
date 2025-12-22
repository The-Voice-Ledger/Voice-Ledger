"""
Redis-based session manager for persistent registration state.
Replaces in-memory conversation_states dict to prevent session loss on server reload.

Version: v1.8 - Phase 3.5: Redis Session Persistence
Date: December 22, 2025
"""

import redis
import json
import logging
from typing import Dict, Any, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,  # Use DB 0 for registration sessions
    decode_responses=True  # Automatically decode bytes to strings
)

# Session TTL: 1 hour (3600 seconds)
SESSION_TTL = 3600

def get_session_key(user_id: int, prefix: str = "registration") -> str:
    """
    Generate Redis key for user session
    
    Args:
        user_id: Telegram user ID
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        Redis key string
    """
    return f"{prefix}:session:{user_id}"

def set_session(user_id: int, session_data: Dict[str, Any], prefix: str = "registration") -> bool:
    """
    Store session data in Redis with TTL.
    
    Args:
        user_id: Telegram user ID
        session_data: Dict with 'state' and 'data' keys
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        True if successful, False otherwise
    """
    try:
        key = get_session_key(user_id, prefix)
        json_data = json.dumps(session_data)
        redis_client.setex(key, SESSION_TTL, json_data)
        logger.debug(f"Stored {prefix} session for user {user_id}, TTL={SESSION_TTL}s")
        return True
    except Exception as e:
        logger.error(f"Failed to store {prefix} session for user {user_id}: {e}")
        return False

def get_session(user_id: int, prefix: str = "registration") -> Optional[Dict[str, Any]]:
    """
    Retrieve session data from Redis.
    
    Args:
        user_id: Telegram user ID
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        Session dict or None if not found/expired
    """
    try:
        key = get_session_key(user_id, prefix)
        data = redis_client.get(key)
        if data:
            session = json.loads(data)
            # Refresh TTL on access
            redis_client.expire(key, SESSION_TTL)
            return session
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve {prefix} session for user {user_id}: {e}")
        return None

def update_session_state(user_id: int, state: int, prefix: str = "registration") -> bool:
    """
    Update only the state field of a session.
    
    Args:
        user_id: Telegram user ID
        state: New state value
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        True if successful, False otherwise
    """
    session = get_session(user_id, prefix)
    if session:
        session['state'] = state
        return set_session(user_id, session, prefix)
    return False

def update_session_data(user_id: int, key: str, value: Any, prefix: str = "registration") -> bool:
    """
    Update a specific field in session data.
    
    Args:
        user_id: Telegram user ID
        key: Data field name
        value: New value
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        True if successful, False otherwise
    """
    session = get_session(user_id, prefix)
    if session:
        session['data'][key] = value
        return set_session(user_id, session, prefix)
    return False

def delete_session(user_id: int, prefix: str = "registration") -> bool:
    """
    Delete session from Redis.
    
    Args:
        user_id: Telegram user ID
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        True if successful, False otherwise
    """
    try:
        key = get_session_key(user_id, prefix)
        redis_client.delete(key)
        logger.debug(f"Deleted {prefix} session for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete {prefix} session for user {user_id}: {e}")
        return False

def session_exists(user_id: int, prefix: str = "registration") -> bool:
    """
    Check if session exists in Redis.
    
    Args:
        user_id: Telegram user ID
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        True if session exists, False otherwise
    """
    try:
        key = get_session_key(user_id, prefix)
        return redis_client.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check {prefix} session existence for user {user_id}: {e}")
        return False

def get_active_sessions_count(prefix: str = "registration") -> int:
    """
    Get count of active sessions.
    
    Args:
        prefix: Key prefix (e.g., 'registration', 'pin')
        
    Returns:
        Number of active sessions
    """
    try:
        pattern = f"{prefix}:session:*"
        keys = redis_client.keys(pattern)
        return len(keys)
    except Exception as e:
        logger.error(f"Failed to count active {prefix} sessions: {e}")
        return 0

def health_check() -> Dict[str, Any]:
    """
    Check Redis connection and return health status.
    
    Returns:
        Dict with connection status and metrics
    """
    try:
        redis_client.ping()
        active_sessions = get_active_sessions_count()
        return {
            'status': 'healthy',
            'connected': True,
            'active_sessions': active_sessions
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'connected': False,
            'error': str(e)
        }
