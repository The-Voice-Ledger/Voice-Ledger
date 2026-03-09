"""
PIN management commands for Voice Ledger Telegram bot (v1.8 - Phase 3.5)

Implements:
- /set-pin: Set PIN for existing users without one
- /change-pin: Change existing PIN (requires old PIN verification)
- /reset-pin: Request PIN reset (admin approval required)

Uses Redis-based session storage for persistence across server restarts.
"""

import logging
import bcrypt
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from database.models import UserIdentity, SessionLocal
from voice.telegram.session_manager import (
    get_session,
    set_session,
    delete_session,
    session_exists
)

logger = logging.getLogger(__name__)


# Redis-backed dict-like wrapper for PIN conversation states
class PinConversationStates:
    """Dict-like wrapper around Redis session storage for backward compatibility.

    Uses an in-memory write-through cache (same pattern as ConversationStates)
    so that dict-style mutations like  pin_conversation_states[uid]['state'] = X
    work correctly.  Call save(uid) to persist cached changes to Redis.
    """

    def __init__(self):
        self._cache: Dict[int, Dict[str, Any]] = {}

    def __contains__(self, user_id: int) -> bool:
        """Check if user has active PIN session"""
        if user_id in self._cache:
            return True
        if session_exists(user_id, prefix="pin"):
            session = get_session(user_id, prefix="pin")
            if session is not None:
                self._cache[user_id] = session
            return True
        return False

    def __getitem__(self, user_id: int) -> Dict[str, Any]:
        """Get PIN session data - returns cached reference so mutations persist"""
        if user_id in self._cache:
            return self._cache[user_id]
        session = get_session(user_id, prefix="pin")
        if session is None:
            raise KeyError(f"No PIN session for user {user_id}")
        self._cache[user_id] = session
        return session

    def __setitem__(self, user_id: int, value: Dict[str, Any]):
        """Set PIN session data (writes to both cache and Redis)"""
        self._cache[user_id] = value
        set_session(user_id, value, prefix="pin")

    def pop(self, user_id: int, default=None):
        """Remove and return PIN session data"""
        session = self._cache.pop(user_id, None)
        if session is None:
            session = get_session(user_id, prefix="pin")
        delete_session(user_id, prefix="pin")
        return session if session else default

    def save(self, user_id: int):
        """Persist cached mutations to Redis and clear the cache entry."""
        if user_id in self._cache:
            set_session(user_id, self._cache[user_id], prefix="pin")
            del self._cache[user_id]


# Use Redis-backed PIN conversation states
pin_conversation_states = PinConversationStates()

# PIN conversation states
PIN_STATE_NONE = 0
PIN_STATE_SET_NEW = 1
PIN_STATE_CONFIRM_NEW = 2
PIN_STATE_OLD_PIN = 3
PIN_STATE_CHANGE_NEW = 4
PIN_STATE_CHANGE_CONFIRM = 5


async def handle_set_pin_command(user_id: int, telegram_user_id: str) -> Dict[str, Any]:
    """
    Handle /set-pin command - for existing users without PIN.
    
    Args:
        user_id: Internal user ID
        telegram_user_id: Telegram user ID string
        
    Returns:
        dict with 'message' key
    """
    db = SessionLocal()
    
    try:
        # Check if user exists
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == telegram_user_id
        ).first()
        
        if not user:
            return {
                'message': (
                    "❌ User not found.\n\n"
                    "Please complete registration first using /register"
                )
            }
        
        # Check if PIN already set
        if user.pin_hash:
            return {
                'message': (
                    "❌ You already have a PIN set.\n\n"
                    "To change your PIN, use /change-pin\n"
                    "To reset your PIN, use /reset-pin"
                )
            }
        
        # Start PIN setup conversation
        pin_conversation_states[user_id] = {
            'state': PIN_STATE_SET_NEW,
            'user_db_id': user.id,
            'telegram_user_id': telegram_user_id
        }
        
        return {
            'message': (
                "🔒 Set up your 4-digit PIN\n\n"
                "This PIN will allow you to log into the Voice Ledger web dashboard.\n\n"
                "📌 Please enter exactly 4 digits (e.g., 1234):\n\n"
                "<i>(Note: Your PIN message will be deleted immediately for security.)</i>"
            ),
            'parse_mode': 'HTML'
        }
        
    except Exception as e:
        logger.error(f"Error in /set-pin: {e}", exc_info=True)
        return {
            'message': "❌ Error processing command. Please try again."
        }
    finally:
        db.close()


async def handle_change_pin_command(user_id: int, telegram_user_id: str) -> Dict[str, Any]:
    """
    Handle /change-pin command - change existing PIN.
    
    Requires old PIN verification for security.
    """
    db = SessionLocal()
    
    try:
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == telegram_user_id
        ).first()
        
        if not user:
            return {
                'message': (
                    "❌ User not found.\n\n"
                    "Please complete registration first using /register"
                )
            }
        
        if not user.pin_hash:
            return {
                'message': (
                    "❌ You don't have a PIN set yet.\n\n"
                    "Use /set-pin to set up your PIN first."
                )
            }
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = (user.locked_until - datetime.utcnow()).seconds // 60
            return {
                'message': (
                    f"🔒 Account temporarily locked due to failed attempts.\n\n"
                    f"Please try again in {remaining} minutes."
                )
            }
        
        # Start PIN change conversation
        pin_conversation_states[user_id] = {
            'state': PIN_STATE_OLD_PIN,
            'user_db_id': user.id,
            'telegram_user_id': telegram_user_id
        }
        
        return {
            'message': (
                "🔒 Change your PIN\n\n"
                "First, please enter your current PIN:\n\n"
                "<i>(Note: Your PIN message will be deleted immediately for security.)</i>"
            ),
            'parse_mode': 'HTML'
        }
        
    except Exception as e:
        logger.error(f"Error in /change-pin: {e}", exc_info=True)
        return {
            'message': "❌ Error processing command. Please try again."
        }
    finally:
        db.close()


async def handle_reset_pin_command(user_id: int, telegram_user_id: str) -> Dict[str, Any]:
    """
    Handle /reset-pin command - request admin PIN reset.
    
    This immediately clears the PIN and notifies admin.
    User can then use /set-pin to create a new one.
    """
    db = SessionLocal()
    
    try:
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == telegram_user_id
        ).first()
        
        if not user:
            return {
                'message': (
                    "❌ User not found.\n\n"
                    "Please complete registration first using /register"
                )
            }
        
        if not user.pin_hash:
            return {
                'message': (
                    "❌ You don't have a PIN to reset.\n\n"
                    "Use /set-pin to set up your PIN."
                )
            }
        
        # Clear PIN and unlock account
        user.pin_hash = None
        user.pin_salt = None
        user.pin_set_at = None
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        
        user_name = f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip() or telegram_user_id
        logger.info(f"PIN reset for user {user.id} ({user_name})")
        
        return {
            'message': (
                "✅ PIN reset successful!\n\n"
                "Your PIN has been cleared and your account unlocked.\n\n"
                "Use /set-pin to create a new PIN."
            )
        }
        
    except Exception as e:
        logger.error(f"Error in /reset-pin: {e}", exc_info=True)
        return {
            'message': "❌ Error processing command. Please try again."
        }
    finally:
        db.close()


async def handle_pin_conversation(user_id: int, telegram_user_id: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Handle ongoing PIN conversation state machine.
    
    Returns:
        dict with 'message' if conversation active, None otherwise
    """
    if user_id not in pin_conversation_states:
        return None
    
    state_data = pin_conversation_states[user_id]
    state = state_data['state']
    db = SessionLocal()
    
    try:
        # State: SET_NEW (initial PIN setup)
        if state == PIN_STATE_SET_NEW:
            pin = text.strip()
            
            # Validate PIN
            if not pin.isdigit():
                return {
                    'message': (
                        "❌ PIN must contain only numbers.\n\n"
                        "Please enter exactly 4 digits (e.g., 1234):"
                    )
                }
            
            if len(pin) != 4:
                return {
                    'message': (
                        f"❌ PIN must be exactly 4 digits (you entered {len(pin)}).\n\n"
                        "Please enter exactly 4 digits (e.g., 1234):"
                    )
                }
            
            # Store PIN temporarily
            state_data['temp_pin'] = pin
            state_data['state'] = PIN_STATE_CONFIRM_NEW
            
            return {
                'message': (
                    "🔒 Confirm your PIN\n\n"
                    "Please enter the same 4 digits again:\n\n"
                    "<i>(Note: Your PIN message will be deleted immediately for security.)</i>"
                ),
                'parse_mode': 'HTML'
            }
        
        # State: CONFIRM_NEW (confirm initial PIN)
        if state == PIN_STATE_CONFIRM_NEW:
            pin_confirmation = text.strip()
            original_pin = state_data.get('temp_pin')
            
            if pin_confirmation != original_pin:
                # Reset to SET_NEW state
                state_data['state'] = PIN_STATE_SET_NEW
                del state_data['temp_pin']
                
                return {
                    'message': (
                        "❌ PINs don't match!\n\n"
                        "Let's try again. Please enter your 4-digit PIN:"
                    )
                }
            
            # Hash PIN and save
            pin_hash = bcrypt.hashpw(original_pin.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
            
            user = db.query(UserIdentity).filter(
                UserIdentity.id == state_data['user_db_id']
            ).first()
            
            if not user:
                pin_conversation_states.pop(user_id, None)
                return {
                    'message': "❌ User not found. Please try again."
                }
            
            user.pin_hash = pin_hash
            user.pin_set_at = datetime.utcnow()
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()
            
            # Clear conversation state
            pin_conversation_states.pop(user_id, None)
            
            user_name = f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip() or telegram_user_id
            logger.info(f"PIN set for user {user.id} ({user_name})")
            
            return {
                'message': (
                    "✅ PIN set successfully!\n\n"
                    "You can now use your PIN to log into the Voice Ledger web dashboard."
                )
            }
        
        # State: OLD_PIN (verify current PIN before change)
        if state == PIN_STATE_OLD_PIN:
            old_pin = text.strip()
            
            user = db.query(UserIdentity).filter(
                UserIdentity.id == state_data['user_db_id']
            ).first()
            
            if not user or not user.pin_hash:
                pin_conversation_states.pop(user_id, None)
                return {
                    'message': "❌ User not found or no PIN set."
                }
            
            # Verify old PIN
            try:
                if not bcrypt.checkpw(old_pin.encode('utf-8'), user.pin_hash.encode('utf-8')):
                    # Increment failed attempts
                    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                    
                    if user.failed_login_attempts >= 5:
                        # Lock account for 30 minutes
                        user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                        db.commit()
                        pin_conversation_states.pop(user_id, None)
                        
                        return {
                            'message': (
                                "❌ Too many failed attempts.\n\n"
                                "Your account has been locked for 30 minutes.\n"
                                "Use /reset-pin if you've forgotten your PIN."
                            )
                        }
                    
                    db.commit()
                    remaining = 5 - user.failed_login_attempts
                    
                    return {
                        'message': (
                            f"❌ Incorrect PIN.\n\n"
                            f"Attempts remaining: {remaining}\n\n"
                            "Please try again or use /reset-pin if you've forgotten your PIN:"
                        )
                    }
            except Exception as e:
                logger.error(f"PIN verification error: {e}")
                pin_conversation_states.pop(user_id, None)
                return {
                    'message': "❌ Error verifying PIN. Please try again."
                }
            
            # Old PIN correct, ask for new PIN
            user.failed_login_attempts = 0
            db.commit()
            
            state_data['state'] = PIN_STATE_CHANGE_NEW
            
            return {
                'message': (
                    "✅ Current PIN verified.\n\n"
                    "Now enter your new 4-digit PIN:"
                )
            }
        
        # State: CHANGE_NEW (enter new PIN)
        if state == PIN_STATE_CHANGE_NEW:
            pin = text.strip()
            
            # Validate PIN
            if not pin.isdigit():
                return {
                    'message': (
                        "❌ PIN must contain only numbers.\n\n"
                        "Please enter exactly 4 digits (e.g., 1234):"
                    )
                }
            
            if len(pin) != 4:
                return {
                    'message': (
                        f"❌ PIN must be exactly 4 digits (you entered {len(pin)}).\n\n"
                        "Please enter exactly 4 digits (e.g., 1234):"
                    )
                }
            
            # Store new PIN temporarily
            state_data['temp_new_pin'] = pin
            state_data['state'] = PIN_STATE_CHANGE_CONFIRM
            
            return {
                'message': (
                    "🔒 Confirm your new PIN\n\n"
                    "Please enter the same 4 digits again:"
                )
            }
        
        # State: CHANGE_CONFIRM (confirm new PIN)
        if state == PIN_STATE_CHANGE_CONFIRM:
            pin_confirmation = text.strip()
            new_pin = state_data.get('temp_new_pin')
            
            if pin_confirmation != new_pin:
                # Reset to CHANGE_NEW state
                state_data['state'] = PIN_STATE_CHANGE_NEW
                del state_data['temp_new_pin']
                
                return {
                    'message': (
                        "❌ PINs don't match!\n\n"
                        "Let's try again. Please enter your new 4-digit PIN:"
                    )
                }
            
            # Hash new PIN and save
            pin_hash = bcrypt.hashpw(new_pin.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
            
            user = db.query(UserIdentity).filter(
                UserIdentity.id == state_data['user_db_id']
            ).first()
            
            if not user:
                pin_conversation_states.pop(user_id, None)
                return {
                    'message': "❌ User not found. Please try again."
                }
            
            user.pin_hash = pin_hash
            user.pin_set_at = datetime.utcnow()
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()
            
            # Clear conversation state
            pin_conversation_states.pop(user_id, None)
            
            user_name = f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip() or telegram_user_id
            logger.info(f"PIN changed for user {user.id} ({user_name})")
            
            return {
                'message': (
                    "✅ PIN changed successfully!\n\n"
                    "You can now use your new PIN to log into the Voice Ledger web dashboard."
                )
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error in PIN conversation: {e}", exc_info=True)
        pin_conversation_states.pop(user_id, None)
        return {
            'message': "❌ Error processing PIN. Please try again."
        }
    finally:
        db.close()
        # Persist any in-memory mutations back to Redis
        pin_conversation_states.save(user_id)


def clear_pin_conversation(user_id: int):
    """Clear PIN conversation state (e.g., on /cancel)"""
    pin_conversation_states.pop(user_id, None)
