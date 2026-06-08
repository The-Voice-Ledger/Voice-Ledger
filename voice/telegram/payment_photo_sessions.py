"""
Payment Receipt Photo Session Management

Tracks users who sent /confirm_payment <ACC-#> without a photo attached,
so the next photo they send is treated as the receipt for that acceptance.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# {user_id: {"acceptance_number": str, "expires_at": datetime}}
payment_photo_sessions: Dict[int, Dict[str, Any]] = {}

# 10-minute window to upload the receipt photo
SESSION_TIMEOUT_MINUTES = 10


def create_payment_photo_session(user_id: int, acceptance_number: str) -> None:
    payment_photo_sessions[user_id] = {
        "acceptance_number": acceptance_number,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES),
    }
    logger.info("Created payment photo session for user %s, acceptance %s", user_id, acceptance_number)


def get_payment_photo_session(user_id: int) -> Optional[Dict[str, Any]]:
    session = payment_photo_sessions.get(user_id)
    if not session:
        return None
    if datetime.utcnow() > session["expires_at"]:
        logger.info("Payment photo session expired for user %s", user_id)
        payment_photo_sessions.pop(user_id, None)
        return None
    return session


def clear_payment_photo_session(user_id: int) -> None:
    if user_id in payment_photo_sessions:
        payment_photo_sessions.pop(user_id)
        logger.info("Cleared payment photo session for user %s", user_id)
