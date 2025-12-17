"""
Registration conversation handler for Voice Ledger Telegram bot.

Implements /register command with 7-question conversation flow for
cooperative managers, exporters, and buyers to request access.

Uses simple state machine with in-memory storage for webhook-based bot.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from database.models import PendingRegistration, UserIdentity, SessionLocal

logger = logging.getLogger(__name__)

# In-memory conversation state storage (for webhook mode)
# In production, could use Redis for persistence across server restarts
conversation_states: Dict[int, Dict[str, Any]] = {}

# Conversation states
STATE_NONE = 0
STATE_ROLE = 1
STATE_FULL_NAME = 2
STATE_ORG_NAME = 3
STATE_LOCATION = 4
STATE_PHONE = 5
STATE_REG_NUMBER = 6
STATE_REASON = 7


async def handle_register_command(user_id: int, username: str, first_name: str, last_name: str) -> Dict[str, Any]:
    """
    Start registration process - show role selection.
    
    Returns dict with message and optional inline_keyboard.
    """
    db = SessionLocal()
    try:
        # Check if already registered with non-farmer role
        existing_user = db.query(UserIdentity).filter_by(
            telegram_user_id=str(user_id)
        ).first()
        
        if existing_user and existing_user.role != 'FARMER' and existing_user.is_approved:
            return {
                'message': (
                    f"✅ You are already registered as: *{existing_user.role.replace('_', ' ').title()}*\n"
                    f"Organization: {existing_user.organization.name if existing_user.organization else 'N/A'}"
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if pending registration exists
        pending = db.query(PendingRegistration).filter_by(
            telegram_user_id=user_id,
            status='PENDING'
        ).first()
        
        if pending:
            return {
                'message': (
                    f"⏳ *Pending Registration*\n\n"
                    f"Application ID: `REG-{pending.id:04d}`\n"
                    f"Role: {pending.requested_role.replace('_', ' ').title()}\n"
                    f"Submitted: {pending.created_at.strftime('%b %d, %Y')}\n\n"
                    f"Please wait for admin approval."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Initialize conversation state
        conversation_states[user_id] = {
            'state': STATE_ROLE,
            'data': {
                'telegram_username': username,
                'telegram_first_name': first_name,
                'telegram_last_name': last_name
            }
        }
        
        # Show role selection with inline keyboard
        return {
            'message': (
                "📋 *Voice Ledger Registration*\n\n"
                "Please select your role in the coffee supply chain:"
            ),
            'parse_mode': 'Markdown',
            'inline_keyboard': [
                [{'text': "🏢 Cooperative Manager", 'callback_data': 'reg_role_COOPERATIVE_MANAGER'}],
                [{'text': "📦 Exporter", 'callback_data': 'reg_role_EXPORTER'}],
                [{'text': "🛒 Buyer", 'callback_data': 'reg_role_BUYER'}],
                [{'text': "❌ Cancel", 'callback_data': 'reg_cancel'}]
            ]
        }
        
    except Exception as e:
        logger.error(f"Error starting registration: {e}", exc_info=True)
        return {
            'message': "❌ Registration failed to start. Please try again later."
        }
    finally:
        db.close()


async def handle_registration_callback(user_id: int, callback_data: str) -> Dict[str, Any]:
    """
    Handle callback queries during registration (role selection, skip buttons).
    
    Returns dict with message to send back.
    """
    # Cancel registration
    if callback_data == 'reg_cancel':
        conversation_states.pop(user_id, None)
        return {'message': "Registration cancelled."}
    
    # Role selection
    if callback_data.startswith('reg_role_'):
        role = callback_data.replace('reg_role_', '')
        
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        conversation_states[user_id]['data']['role'] = role
        conversation_states[user_id]['state'] = STATE_FULL_NAME
        
        return {
            'message': (
                f"Selected: *{role.replace('_', ' ').title()}*\n\n"
                f"What is your full name?"
            ),
            'parse_mode': 'Markdown'
        }
    
    # Skip registration number
    if callback_data == 'reg_skip_reg_number':
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        conversation_states[user_id]['data']['registration_number'] = None
        conversation_states[user_id]['state'] = STATE_REASON
        
        return {
            'message': "Why are you registering with Voice Ledger?\n(Optional - helps us understand your needs)",
            'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reason'}]]
        }
    
    # Skip reason
    if callback_data == 'reg_skip_reason':
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        conversation_states[user_id]['data']['reason'] = None
        return await submit_registration(user_id)
    
    return {'message': "❌ Unknown callback data."}


async def handle_registration_text(user_id: int, text: str) -> Dict[str, Any]:
    """
    Handle text messages during registration conversation.
    
    Returns dict with message to send back.
    """
    if user_id not in conversation_states:
        return {
            'message': "No active registration. Use /register to start."
        }
    
    state = conversation_states[user_id]['state']
    data = conversation_states[user_id]['data']
    
    # State: FULL_NAME
    if state == STATE_FULL_NAME:
        data['full_name'] = text.strip()
        conversation_states[user_id]['state'] = STATE_ORG_NAME
        return {
            'message': (
                "What is your organization name?\n"
                "(e.g., 'Sidama Coffee Cooperative', 'Yirgacheffe Exporters Ltd')"
            )
        }
    
    # State: ORG_NAME
    if state == STATE_ORG_NAME:
        data['organization_name'] = text.strip()
        conversation_states[user_id]['state'] = STATE_LOCATION
        return {
            'message': (
                "Where are you located?\n"
                "(Region and City, e.g., 'Hawassa, Sidama')"
            )
        }
    
    # State: LOCATION
    if state == STATE_LOCATION:
        data['location'] = text.strip()
        conversation_states[user_id]['state'] = STATE_PHONE
        return {
            'message': (
                "What is your phone number?\n"
                "(Include country code, e.g., +251912345678)"
            )
        }
    
    # State: PHONE
    if state == STATE_PHONE:
        data['phone_number'] = text.strip()
        conversation_states[user_id]['state'] = STATE_REG_NUMBER
        return {
            'message': (
                "Do you have a registration or license number?\n"
                "(Optional - click Skip if you don't have one)"
            ),
            'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reg_number'}]]
        }
    
    # State: REG_NUMBER
    if state == STATE_REG_NUMBER:
        data['registration_number'] = text.strip()
        conversation_states[user_id]['state'] = STATE_REASON
        return {
            'message': (
                "Why are you registering with Voice Ledger?\n"
                "(Optional - helps us understand your needs)"
            ),
            'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reason'}]]
        }
    
    # State: REASON
    if state == STATE_REASON:
        data['reason'] = text.strip()
        return await submit_registration(user_id)
    
    return {'message': "❌ Unknown registration state. Please /register again."}


async def submit_registration(user_id: int) -> Dict[str, Any]:
    """
    Submit the completed registration to database.
    
    Returns confirmation message.
    """
    if user_id not in conversation_states:
        return {'message': "❌ Session expired. Please /register again."}
    
    data = conversation_states[user_id]['data']
    db = SessionLocal()
    
    try:
        # Create pending registration
        pending = PendingRegistration(
            telegram_user_id=user_id,
            telegram_username=data.get('telegram_username'),
            telegram_first_name=data.get('telegram_first_name'),
            telegram_last_name=data.get('telegram_last_name'),
            requested_role=data['role'],
            full_name=data['full_name'],
            organization_name=data['organization_name'],
            location=data['location'],
            phone_number=data['phone_number'],
            registration_number=data.get('registration_number'),
            reason=data.get('reason'),
            status='PENDING'
        )
        
        db.add(pending)
        db.commit()
        db.refresh(pending)
        
        # Clear conversation state
        conversation_states.pop(user_id, None)
        
        # Notify admin via Telegram
        await notify_admin_new_registration(pending.id, {
            'role': pending.requested_role,
            'full_name': pending.full_name,
            'organization_name': pending.organization_name,
            'location': pending.location,
            'phone_number': pending.phone_number,
            'registration_number': pending.registration_number
        })
        
        return {
            'message': (
                f"✅ *Registration Submitted!*\n\n"
                f"Application ID: `REG-{pending.id:04d}`\n"
                f"Role: {data['role'].replace('_', ' ').title()}\n"
                f"Organization: {data['organization_name']}\n\n"
                f"Your application has been sent to the admin team for review.\n"
                f"You will be notified once approved.\n\n"
                f"⏱️ Review typically takes 1-2 business days."
            ),
            'parse_mode': 'Markdown'
        }
        
    except Exception as e:
        logger.error(f"Registration submission failed: {e}", exc_info=True)
        conversation_states.pop(user_id, None)
        return {
            'message': "❌ Registration failed. Please try again later or contact support."
        }
    finally:
        db.close()


async def notify_admin_new_registration(registration_id: int, registration_data: dict):
    """
    Send Telegram notification to admin about new registration request.
    
    Args:
        registration_id: Database ID of the pending registration
        registration_data: Dictionary with registration details
    """
    import os
    import requests
    
    try:
        admin_user_id = os.getenv("ADMIN_TELEGRAM_USER_ID")
        if not admin_user_id:
            logger.warning("ADMIN_TELEGRAM_USER_ID not configured, skipping admin notification")
            return
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return
        
        role_display = registration_data['role'].replace('_', ' ').title()
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        
        message = f"""📋 *New Registration Request*

ID: `REG-{registration_id:04d}`
Role: *{role_display}*
Name: {registration_data['full_name']}
Organization: {registration_data['organization_name']}
Location: {registration_data['location']}
Phone: {registration_data['phone_number']}
Registration #: {registration_data.get('registration_number', 'N/A')}

Review and approve at:
{base_url}/admin/registrations"""
        
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                'chat_id': admin_user_id,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=30
        )
        response.raise_for_status()
        
        logger.info(f"Sent admin notification for registration {registration_id}")
        
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}", exc_info=True)


# Export main functions for use in telegram_api webhook handler
__all__ = [
    'handle_register_command',
    'handle_registration_callback',
    'handle_registration_text',
    'conversation_states',
    'STATE_NONE',
    'STATE_FULL_NAME',
    'STATE_ORG_NAME',
    'STATE_LOCATION',
    'STATE_PHONE',
    'STATE_REG_NUMBER',
    'STATE_REASON'
]
