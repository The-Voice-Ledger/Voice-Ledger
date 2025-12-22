"""
Registration conversation handler for Voice Ledger Telegram bot.

Implements /register command with 7-question conversation flow for
cooperative managers, exporters, and buyers to request access.

Uses Redis-based session storage for persistence across server restarts.
Version: v1.8 - Phase 3.5: Redis Session Persistence
"""

import logging
import bcrypt  # For PIN hashing (v1.7 - Phase 3: PIN Setup Integration)
from typing import Dict, Any, Optional
from datetime import datetime
from database.models import PendingRegistration, UserIdentity, SessionLocal
from voice.telegram.session_manager import (
    get_session,
    set_session,
    delete_session,
    session_exists,
    update_session_state,
    update_session_data
)

logger = logging.getLogger(__name__)


# Redis-backed dict-like wrapper for conversation states
class ConversationStates:
    """Dict-like wrapper around Redis session storage for backward compatibility"""
    
    def __contains__(self, user_id: int) -> bool:
        """Check if user has active session"""
        return session_exists(user_id)
    
    def __getitem__(self, user_id: int) -> Dict[str, Any]:
        """Get session data"""
        session = get_session(user_id)
        if session is None:
            raise KeyError(f"No session for user {user_id}")
        return session
    
    def __setitem__(self, user_id: int, value: Dict[str, Any]):
        """Set session data"""
        set_session(user_id, value)
    
    def pop(self, user_id: int, default=None):
        """Remove and return session data"""
        session = get_session(user_id)
        delete_session(user_id)
        return session if session else default


# Use Redis-backed conversation states instead of in-memory dict
conversation_states = ConversationStates()

# Conversation states
STATE_NONE = 0
STATE_LANGUAGE = 1  # NEW: Ask for language preference
STATE_ROLE = 2
STATE_FULL_NAME = 3
STATE_ORG_NAME = 4
STATE_LOCATION = 5
STATE_PHONE = 6
STATE_SET_PIN = 7  # NEW (v1.7): Set 4-digit PIN for web UI access
STATE_CONFIRM_PIN = 8  # NEW (v1.7): Confirm PIN
STATE_REG_NUMBER = 9  # Moved from 7
STATE_REASON = 10  # Moved from 8

# Exporter-specific states (renumbered)
STATE_EXPORT_LICENSE = 11  # Moved from 9
STATE_PORT_ACCESS = 12  # Moved from 10
STATE_SHIPPING_CAPACITY = 13  # Moved from 11

# Buyer-specific states (renumbered)
STATE_BUSINESS_TYPE = 14  # Moved from 12
STATE_COUNTRY = 15  # Moved from 13
STATE_TARGET_VOLUME = 16  # Moved from 14
STATE_QUALITY_PREFS = 17  # Moved from 15

# Farmer GPS photo verification states (EUDR compliance - renumbered)
STATE_UPLOAD_FARM_PHOTO = 18  # Moved from 16
STATE_VERIFY_GPS = 19  # Moved from 17


async def handle_register_command(user_id: int, username: str, first_name: str, last_name: str) -> Dict[str, Any]:
    """
    Start registration process - show language and role selection.
    
    This is the primary entry point for new users. No /start required.
    
    Returns dict with message and optional inline_keyboard.
    """
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(UserIdentity).filter_by(
            telegram_user_id=str(user_id)
        ).first()
        
        # Check if already registered with a role
        if existing_user and existing_user.role and existing_user.is_approved:
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
        
        # Check if user already has language preference from existing UserIdentity
        existing_lang = existing_user.preferred_language if existing_user else 'en'
        
        # Initialize conversation state in Redis - start with language selection
        session_data = {
            'state': STATE_LANGUAGE,
            'data': {
                'telegram_username': username,
                'telegram_first_name': first_name,
                'telegram_last_name': last_name,
                'preferred_language': existing_lang  # Carry over existing preference
            }
        }
        set_session(user_id, session_data)
        
        # Show language selection with appropriate default language
        # If user has Amharic preference, show Amharic first. Otherwise default to English.
        if existing_lang == 'am':
            message_text = (
                "🌍 *እንኳን ደህና መጡ ወደ Voice Ledger*\n\n"
                "የድምጽ ትዕዛዞችዎን ቋንቋ ይምረጡ:\n"
                "Please select your preferred language for voice commands:"
            )
        else:
            message_text = (
                "🌍 *Welcome to Voice Ledger*\n\n"
                "Please select your preferred language for voice commands:\n"
                "የድምጽ ትዕዛዞችዎን ቋንቋ ይምረጡ:"
            )
        
        return {
            'message': message_text,
            'parse_mode': 'Markdown',
            'inline_keyboard': [
                [{'text': "🇺🇸 English", 'callback_data': 'reg_lang_en'}],
                [{'text': "🇪🇹 Amharic (አማርኛ)", 'callback_data': 'reg_lang_am'}],
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
    Handle callback queries during registration (language, role selection, skip buttons).
    
    Returns dict with message to send back.
    """
    # Cancel registration
    if callback_data == 'reg_cancel':
        conversation_states.pop(user_id, None)
        return {'message': "Registration cancelled."}
    
    # Language selection (NEW)
    if callback_data.startswith('reg_lang_'):
        language = callback_data.replace('reg_lang_', '')
        
        session = get_session(user_id)
        if not session:
            return {'message': "❌ Session expired. Please /register again."}
        
        session['data']['preferred_language'] = language
        session['state'] = STATE_ROLE
        set_session(user_id, session)
        
        lang_name = "English" if language == 'en' else "Amharic (አማርኛ)"
        
        # Show role selection
        return {
            'message': (
                f"✅ Language set to: *{lang_name}*\n\n"
                "📋 *Voice Ledger Registration*\n\n"
                "Please select your role in the coffee supply chain:"
            ),
            'parse_mode': 'Markdown',
            'inline_keyboard': [
                [{'text': "👨‍🌾 Farmer", 'callback_data': 'reg_role_FARMER'}],
                [{'text': "🏢 Cooperative Manager", 'callback_data': 'reg_role_COOPERATIVE_MANAGER'}],
                [{'text': "📦 Exporter", 'callback_data': 'reg_role_EXPORTER'}],
                [{'text': "🛒 Buyer", 'callback_data': 'reg_role_BUYER'}],
                [{'text': "❌ Cancel", 'callback_data': 'reg_cancel'}]
            ]
        }
    
    # Role selection
    if callback_data.startswith('reg_role_'):
        role = callback_data.replace('reg_role_', '')
        
        session = get_session(user_id)
        if not session:
            return {'message': "❌ Session expired. Please /register again."}
        
        session['data']['role'] = role
        session['state'] = STATE_FULL_NAME
        set_session(user_id, session)
        
        # Role-specific welcome message
        role_info = {
            'FARMER': 'You will be able to record coffee batches using voice commands.',
            'COOPERATIVE_MANAGER': 'You will manage coffee batches from farmers and coordinate verification.',
            'EXPORTER': 'You will have access to verified batches and export documentation tools.',
            'BUYER': 'You will be able to browse verified inventory and place purchase orders.'
        }
        
        # Farmers get simplified registration (auto-approved)
        if role == 'FARMER':
            # Request farm photo for GPS verification (EUDR compliance)
            session['state'] = STATE_UPLOAD_FARM_PHOTO
            set_session(user_id, session)
            
            lang = session['data'].get('preferred_language', 'en')
            
            if lang == 'am':
                message = (
                    "📸 *የእርሻ ፎቶ* (Farm Photo)\n\n"
                    "ለ EUDR ተገዢነት፣ እባክዎ በእርሻዎ ላይ የተነሱ ፎቶግራፍ ያስገቡ።\n\n"
                    "የፎቶግራፍ መስፈርቶች፡\n"
                    "✅ በቅርብ ጊዜ የተነሳ (ባለፉት 7 ቀናት ውስጥ)\n"
                    "✅ GPS መረጃ መያዝ አለበት (አብዛኛዎቹ ስማርትፎኖች ይህንን በራስ ሰር ያከማቻሉ)\n"
                    "✅ ወደ ኢትዮጵያ መገኛ ቦታ መጠቆም አለበት\n\n"
                    "የእርሻዎን ፎቶ ለመላክ አሁን ይጫኑ።\n\n"
                    "_ይህ ወደ አውሮፓ ከሚላኩ ጫማዎች EUDR ማረጋገጫ ይረዳል።_"
                )
            else:
                message = (
                    "📸 *Farm Photo Upload*\n\n"
                    "For EUDR compliance, please upload a photo taken at your farm.\n\n"
                    "Photo requirements:\n"
                    "✅ Taken recently (within 7 days)\n"
                    "✅ Must have GPS data (most smartphones auto-save this)\n"
                    "✅ Must show Ethiopia location\n\n"
                    "Press the 📎 button and send a photo from your farm now.\n\n"
                    "_This helps verify your farm location for EU export compliance._"
                )
            
            return {
                'message': message,
                'parse_mode': 'Markdown',
                'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
            }
        
        # Non-farmers continue with full registration flow
        return {
            'message': (
                f"✅ Selected: *{role.replace('_', ' ').title()}*\n\n"
                f"{role_info.get(role, '')}\n\n"
                f"What is your full name?"
            ),
            'parse_mode': 'Markdown'
        }
    
    # Skip registration number
    if callback_data == 'reg_skip_reg_number':
        session = get_session(user_id)
        if not session:
            return {'message': "❌ Session expired. Please /register again."}
        
        session['data']['registration_number'] = None
        session['state'] = STATE_REASON
        set_session(user_id, session)
        
        return {
            'message': "Why are you registering with Voice Ledger?\n(Optional - helps us understand your needs)",
            'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reason'}]]
        }
    
    # Skip reason
    if callback_data == 'reg_skip_reason':
        session = get_session(user_id)
        if not session:
            return {'message': "❌ Session expired. Please /register again."}
        
        session['data']['reason'] = None
        set_session(user_id, session)
        return await submit_registration(user_id)
    
    # Skip farm photo (farmer registration)
    if callback_data == 'reg_skip_photo':
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        # Complete registration without GPS verification
        return await complete_farmer_registration(user_id, skip_photo=True)
    
    # Confirm GPS from photo
    if callback_data == 'reg_confirm_gps':
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        # Complete registration with GPS verification
        return await complete_farmer_registration(user_id, skip_photo=False)
    
    # Retry photo upload
    if callback_data == 'reg_retry_photo':
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        # Reset to photo upload state
        conversation_states[user_id]['state'] = STATE_UPLOAD_FARM_PHOTO
        conversation_states[user_id]['data'].pop('farm_photo', None)
        
        lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
        if lang == 'am':
            return {
                'message': "📸 እባክዎ አዲስ የእርሻ ፎቶ ይስቀሉ።",
                'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
            }
        else:
            return {
                'message': "📸 Please upload a new farm photo.",
                'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
            }
    
    # Business type selection (Buyer)
    if callback_data.startswith('reg_business_'):
        business_type = callback_data.replace('reg_business_', '')
        
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        conversation_states[user_id]['data']['business_type'] = business_type
        conversation_states[user_id]['state'] = STATE_COUNTRY
        
        return {
            'message': (
                f"Selected: *{business_type.replace('_', ' ').title()}*\n\n"
                f"What country are you based in?\n"
                f"(e.g., 'United States', 'Germany', 'Japan')"
            ),
            'parse_mode': 'Markdown'
        }
    
    # Port selection (Exporter)
    if callback_data.startswith('reg_port_'):
        port = callback_data.replace('reg_port_', '')
        
        if user_id not in conversation_states:
            return {'message': "❌ Session expired. Please /register again."}
        
        if port == 'OTHER':
            conversation_states[user_id]['state'] = STATE_PORT_ACCESS
            return {
                'message': "Please type the name of your primary export port:"
            }
        else:
            conversation_states[user_id]['data']['port_access'] = port
            conversation_states[user_id]['state'] = STATE_SHIPPING_CAPACITY
            return {
                'message': (
                    f"Selected: *{port}*\n\n"
                    f"What is your annual shipping capacity? (in tons)\n"
                    f"(e.g., '100' for 100 tons per year)"
                ),
                'parse_mode': 'Markdown'
            }
    
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
        
        # Check if user already shared phone during /start
        db = SessionLocal()
        try:
            existing_user = db.query(UserIdentity).filter_by(
                telegram_user_id=str(user_id)
            ).first()
            
            if existing_user and existing_user.phone_number:
                # User already has phone from /start - skip phone question
                logger.info(f"Reusing phone {existing_user.phone_number} from /start for user {user_id}")
                data['phone_number'] = existing_user.phone_number
                
                # Route directly to role-specific questions
                role = data.get('role')
                
                if role == 'EXPORTER':
                    conversation_states[user_id]['state'] = STATE_EXPORT_LICENSE
                    db.close()
                    return {
                        'message': (
                            "What is your export license number?\n"
                            "(e.g., 'EXP-2024-1234' or similar official license)"
                        )
                    }
                elif role == 'BUYER':
                    conversation_states[user_id]['state'] = STATE_BUSINESS_TYPE
                    db.close()
                    return {
                        'message': "What type of business are you?",
                        'inline_keyboard': [
                            [{'text': "☕ Coffee Roaster", 'callback_data': 'reg_business_ROASTER'}],
                            [{'text': "📦 Importer", 'callback_data': 'reg_business_IMPORTER'}],
                            [{'text': "🏪 Wholesaler", 'callback_data': 'reg_business_WHOLESALER'}],
                            [{'text': "🛒 Retailer", 'callback_data': 'reg_business_RETAILER'}],
                            [{'text': "☕ Cafe Chain", 'callback_data': 'reg_business_CAFE_CHAIN'}]
                        ]
                    }
                else:
                    # COOPERATIVE_MANAGER - go to registration number
                    conversation_states[user_id]['state'] = STATE_REG_NUMBER
                    db.close()
                    return {
                        'message': (
                            "What is your cooperative's registration number? (optional)\n\n"
                            "Reply with 'skip' if not applicable."
                        )
                    }
            
            db.close()
        except Exception as e:
            logger.error(f"Error checking existing phone: {e}")
            db.close()
        
        # No phone yet - ask for it
        conversation_states[user_id]['state'] = STATE_PHONE
        return {
            'message': (
                "What is your phone number?\n"
                "(Include country code, e.g., +251912345678)\n\n"
                "💡 Tip: You can also share your contact via /start"
            )
        }
    
    # State: PHONE (only reached if user didn't share phone in /start)
    if state == STATE_PHONE:
        data['phone_number'] = text.strip()
        
        # Ask for PIN (v1.7 - Phase 3: PIN Setup Integration)
        conversation_states[user_id]['state'] = STATE_SET_PIN
        return {
            'message': (
                "🔒 Set up a 4-digit PIN for web access\n\n"
                "This PIN will allow you to log into the Voice Ledger web dashboard.\n\n"
                "📌 Please enter exactly 4 digits (e.g., 1234):"
            )
        }
    
    # State: SET_PIN (v1.7 - Phase 3)
    if state == STATE_SET_PIN:
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
        
        # Store PIN temporarily for confirmation
        data['temp_pin'] = pin
        conversation_states[user_id]['state'] = STATE_CONFIRM_PIN
        return {
            'message': (
                "🔒 Confirm your PIN\n\n"
                "Please enter the same 4 digits again:"
            )
        }
    
    # State: CONFIRM_PIN (v1.7 - Phase 3)
    if state == STATE_CONFIRM_PIN:
        pin_confirmation = text.strip()
        original_pin = data.get('temp_pin')
        
        if pin_confirmation != original_pin:
            conversation_states[user_id]['state'] = STATE_SET_PIN
            del data['temp_pin']  # Clear the temp PIN
            return {
                'message': (
                    "❌ PINs don't match!\n\n"
                    "Let's try again. Please enter your 4-digit PIN:"
                )
            }
        
        # Hash PIN with bcrypt
        pin_hash = bcrypt.hashpw(original_pin.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        data['pin_hash'] = pin_hash
        
        # Clear temp PIN from memory
        del data['temp_pin']
        
        # Route to role-specific questions
        role = data.get('role')
        
        if role == 'EXPORTER':
            conversation_states[user_id]['state'] = STATE_EXPORT_LICENSE
            return {
                'message': (
                    "✅ PIN set successfully!\n\n"
                    "What is your export license number?\n"
                    "(e.g., 'EXP-2024-1234' or similar official license)"
                )
            }
        elif role == 'BUYER':
            conversation_states[user_id]['state'] = STATE_BUSINESS_TYPE
            return {
                'message': "✅ PIN set successfully!\n\nWhat type of business are you?",
                'inline_keyboard': [
                    [{'text': "☕ Coffee Roaster", 'callback_data': 'reg_business_ROASTER'}],
                    [{'text': "📦 Importer", 'callback_data': 'reg_business_IMPORTER'}],
                    [{'text': "🏪 Wholesaler", 'callback_data': 'reg_business_WHOLESALER'}],
                    [{'text': "🛒 Retailer", 'callback_data': 'reg_business_RETAILER'}],
                    [{'text': "☕ Cafe Chain", 'callback_data': 'reg_business_CAFE_CHAIN'}]
                ]
            }
        else:  # COOPERATIVE_MANAGER
            conversation_states[user_id]['state'] = STATE_REG_NUMBER
            return {
                'message': (
                    "✅ PIN set successfully!\n\n"
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
    
    # Exporter-specific states
    if state == STATE_EXPORT_LICENSE:
        data['export_license'] = text.strip()
        conversation_states[user_id]['state'] = STATE_PORT_ACCESS
        return {
            'message': "Which port do you primarily use for exports?",
            'inline_keyboard': [
                [{'text': "🚢 Djibouti", 'callback_data': 'reg_port_DJIBOUTI'}],
                [{'text': "🚢 Berbera", 'callback_data': 'reg_port_BERBERA'}],
                [{'text': "🚢 Mombasa", 'callback_data': 'reg_port_MOMBASA'}],
                [{'text': "🚢 Other", 'callback_data': 'reg_port_OTHER'}]
            ]
        }
    
    if state == STATE_PORT_ACCESS:
        # User typed custom port name (after selecting "Other")
        data['port_access'] = text.strip()
        conversation_states[user_id]['state'] = STATE_SHIPPING_CAPACITY
        return {
            'message': (
                "What is your annual shipping capacity? (in tons)\n"
                "(e.g., '100' for 100 tons per year)"
            )
        }
    
    if state == STATE_SHIPPING_CAPACITY:
        try:
            capacity = float(text.strip())
            data['shipping_capacity_tons'] = capacity
            conversation_states[user_id]['state'] = STATE_REASON
            return {
                'message': (
                    "Why are you registering with Voice Ledger?\n"
                    "(Optional - helps us understand your needs)"
                ),
                'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reason'}]]
            }
        except ValueError:
            return {'message': "Please enter a valid number (e.g., 100 for 100 tons per year)"}
    
    # Buyer-specific states
    if state == STATE_COUNTRY:
        data['country'] = text.strip()
        conversation_states[user_id]['state'] = STATE_TARGET_VOLUME
        return {
            'message': (
                "What is your annual target volume? (in tons)\n"
                "(e.g., '50' for 50 tons per year, or type 'Skip' if unsure)"
            )
        }
    
    if state == STATE_TARGET_VOLUME:
        if text.strip().lower() == 'skip':
            data['target_volume_tons_annual'] = None
        else:
            try:
                volume = float(text.strip())
                data['target_volume_tons_annual'] = volume
            except ValueError:
                return {'message': "Please enter a valid number (e.g., 50) or type 'Skip'"}
        
        conversation_states[user_id]['state'] = STATE_QUALITY_PREFS
        return {
            'message': (
                "What quality/certifications do you typically look for?\n"
                "(e.g., 'Grade 1, Organic certified, cup score 85+' or type 'Skip')"
            )
        }
    
    if state == STATE_QUALITY_PREFS:
        if text.strip().lower() == 'skip':
            data['quality_preferences'] = None
        else:
            data['quality_preferences'] = {'description': text.strip()}
        
        conversation_states[user_id]['state'] = STATE_REASON
        return {
            'message': (
                "Why are you registering with Voice Ledger?\n"
                "(Optional - helps us understand your needs)"
            ),
            'inline_keyboard': [[{'text': "⏭️ Skip", 'callback_data': 'reg_skip_reason'}]]
        }
    
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
        # Create pending registration with common fields
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
            pin_hash=data.get('pin_hash'),  # v1.7 - Phase 3: Store PIN hash
            pin_salt=None,  # bcrypt includes salt in hash, kept NULL for compatibility
            status='PENDING'
        )
        
        # Store language preference in reason field temporarily (since PendingRegistration doesn't have language field)
        # Admin will see this and it will be set when approved
        language_pref = data.get('preferred_language', 'en')
        if pending.reason:
            pending.reason = f"[LANG:{language_pref}] {pending.reason}"
        else:
            pending.reason = f"[LANG:{language_pref}]"
        
        # Add role-specific fields
        if data['role'] == 'EXPORTER':
            pending.export_license = data.get('export_license')
            pending.port_access = data.get('port_access')
            pending.shipping_capacity_tons = data.get('shipping_capacity_tons')
        elif data['role'] == 'BUYER':
            pending.business_type = data.get('business_type')
            pending.country = data.get('country')
            pending.target_volume_tons_annual = data.get('target_volume_tons_annual')
            pending.quality_preferences = data.get('quality_preferences')
        
        db.add(pending)
        db.commit()
        db.refresh(pending)
        
        # Clear conversation state from Redis
        delete_session(user_id)
        
        # Notify admin via Telegram
        notification_data = {
            'role': pending.requested_role,
            'full_name': pending.full_name,
            'organization_name': pending.organization_name,
            'location': pending.location,
            'phone_number': pending.phone_number,
            'registration_number': pending.registration_number
        }
        
        # Add role-specific data
        if pending.requested_role == 'EXPORTER':
            notification_data.update({
                'export_license': pending.export_license,
                'port_access': pending.port_access,
                'shipping_capacity': pending.shipping_capacity_tons
            })
        elif pending.requested_role == 'BUYER':
            notification_data.update({
                'business_type': pending.business_type,
                'country': pending.country,
                'target_volume': pending.target_volume_tons_annual
            })
        
        await notify_admin_new_registration(pending.id, notification_data)
        
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
        
        # Build message with role-specific fields
        message = f"""📋 *New Registration Request*

ID: `REG-{registration_id:04d}`
Role: *{role_display}*
Name: {registration_data['full_name']}
Organization: {registration_data['organization_name']}
Location: {registration_data['location']}
Phone: {registration_data['phone_number']}
Registration #: {registration_data.get('registration_number', 'N/A')}"""

        # Add role-specific details
        if registration_data['role'] == 'EXPORTER':
            message += f"""

*Exporter Details:*
Export License: {registration_data.get('export_license', 'N/A')}
Primary Port: {registration_data.get('port_access', 'N/A')}
Shipping Capacity: {registration_data.get('shipping_capacity', 'N/A')} tons/year"""
        elif registration_data['role'] == 'BUYER':
            message += f"""

*Buyer Details:*
Business Type: {registration_data.get('business_type', 'N/A').replace('_', ' ').title()}
Country: {registration_data.get('country', 'N/A')}
Target Volume: {registration_data.get('target_volume', 'N/A')} tons/year"""
        
        message += f"""

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


async def handle_farm_photo_upload(user_id: int, photo_file_id: str, photo_file_url: str) -> Dict[str, Any]:
    """
    Handle farm photo upload during farmer registration.
    Extracts GPS from EXIF and validates for EUDR compliance.
    """
    import io
    import requests
    from voice.verification.gps_photo_verifier import GPSPhotoVerifier, GPSExtractionError
    from database.models import UserIdentity, FarmerIdentity
    from datetime import datetime
    
    if user_id not in conversation_states:
        return {'message': "❌ Session expired. Please /register again."}
    
    if conversation_states[user_id]['state'] != STATE_UPLOAD_FARM_PHOTO:
        return {'message': "❌ Please follow the registration flow. Use /register to restart."}
    
    db = SessionLocal()
    try:
        # Download photo from Telegram
        logger.info(f"Downloading farm photo for user {user_id}: {photo_file_url}")
        response = requests.get(photo_file_url, timeout=10)
        response.raise_for_status()
        photo_bytes = io.BytesIO(response.content)
        
        # Extract GPS from photo
        verifier = GPSPhotoVerifier()
        gps_data = verifier.extract_gps_data(photo_bytes)
        
        # Validate GPS data exists
        if not gps_data['has_gps']:
            lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
            if lang == 'am':
                return {
                    'message': (
                        "❌ *GPS መረጃ አልተገኘም*\n\n"
                        "ፎቶው GPS መጋጠሚያዎች የሉትም። እባክዎ፡\n"
                        "1. በስልክዎ ቅንብሮች ውስጥ የአካባቢ አገልግሎቶች ይፍቀዱ\n"
                        "2. ለካሜራ መተግበሪያዎ የአካባቢ ፈቃድ ይስጡ\n"
                        "3. አዲስ ፎቶ ያንሱ እና እንደገና ይሞክሩ\n\n"
                        "ወይም አሁን ለጊዜው ይዝለሉ።"
                    ),
                    'parse_mode': 'Markdown',
                    'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                }
            else:
                return {
                    'message': (
                        "❌ *No GPS Data Found*\n\n"
                        "The photo does not contain GPS coordinates. Please:\n"
                        "1. Enable Location Services in your phone settings\n"
                        "2. Grant location permission to your Camera app\n"
                        "3. Take a new photo and try again\n\n"
                        "Or skip for now."
                    ),
                    'parse_mode': 'Markdown',
                    'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                }
        
        # Validate Ethiopia bounds
        in_ethiopia = verifier.validate_ethiopia_bounds(gps_data['latitude'], gps_data['longitude'])
        if not in_ethiopia:
            lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
            if lang == 'am':
                return {
                    'message': (
                        f"❌ *GPS ከኢትዮጵያ ውጭ*\n\n"
                        f"ፎቶው የተነሳው ከኢትዮጵያ ውጭ ይመስላል፡\n"
                        f"📍 {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}\n\n"
                        f"እባክዎ በእርሻዎ ቦታ ላይ የተነሱ ፎቶግራፍ ይስቀሉ።"
                    ),
                    'parse_mode': 'Markdown',
                    'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                }
            else:
                return {
                    'message': (
                        f"❌ *GPS Outside Ethiopia*\n\n"
                        f"The photo appears to be taken outside Ethiopia:\n"
                        f"📍 {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}\n\n"
                        f"Please upload a photo taken at your farm location."
                    ),
                    'parse_mode': 'Markdown',
                    'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                }
        
        # Validate photo recency (within 30 days)
        if gps_data['timestamp']:
            recency_result = verifier.validate_timestamp_recency(gps_data['timestamp'], max_age_days=30)
            if not recency_result['valid']:
                lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
                if lang == 'am':
                    return {
                        'message': (
                            f"⚠️ *ፎቶው በጣም አሮጌ ነው*\n\n"
                            f"ፎቶው የተነሳው ከ {recency_result['age_days']:.0f} ቀናት በፊት ነው።\n"
                            f"እባክዎ ከ 30 ቀናት ባልበለጠ ጊዜ ውስጥ የተነሱ ቅርብ ፎቶ ይስቀሉ።"
                        ),
                        'parse_mode': 'Markdown',
                        'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                    }
                else:
                    return {
                        'message': (
                            f"⚠️ *Photo Too Old*\n\n"
                            f"The photo was taken {recency_result['age_days']:.0f} days ago.\n"
                            f"Please upload a recent photo (within 30 days)."
                        ),
                        'parse_mode': 'Markdown',
                        'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
                    }
        
        # Compute photo hash
        photo_bytes.seek(0)
        photo_hash = verifier.compute_photo_hash(photo_bytes)
        
        # Store photo data in conversation state
        conversation_states[user_id]['data']['farm_photo'] = {
            'file_id': photo_file_id,
            'file_url': photo_file_url,
            'hash': photo_hash,
            'latitude': gps_data['latitude'],
            'longitude': gps_data['longitude'],
            'timestamp': gps_data['timestamp'],
            'device_make': gps_data.get('device_make'),
            'device_model': gps_data.get('device_model')
        }
        
        conversation_states[user_id]['state'] = STATE_VERIFY_GPS
        
        # Show GPS confirmation
        lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
        if lang == 'am':
            return {
                'message': (
                    f"✅ *GPS ማረጋገጫ ተሳክቷል!*\n\n"
                    f"📍 መጋጠሚያዎች፡ {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}\n"
                    f"📅 ቀን፡ {gps_data['timestamp'][:10] if gps_data['timestamp'] else 'N/A'}\n"
                    f"📱 መሳሪያ፡ {gps_data.get('device_make', 'Unknown')} {gps_data.get('device_model', '')}\n\n"
                    f"_ይህ የእርሻዎ መረጃ EUDR ተገዢነት ይረዳል።_\n\n"
                    f"ምዝገባዎን ለማጠናቀቅ ያረጋግጡ።"
                ),
                'parse_mode': 'Markdown',
                'inline_keyboard': [[
                    {'text': '✅ አረጋግጥ', 'callback_data': 'reg_confirm_gps'},
                    {'text': '🔄 እንደገና ሞክር', 'callback_data': 'reg_retry_photo'}
                ]]
            }
        else:
            return {
                'message': (
                    f"✅ *GPS Verification Successful!*\n\n"
                    f"📍 Coordinates: {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}\n"
                    f"📅 Date: {gps_data['timestamp'][:10] if gps_data['timestamp'] else 'N/A'}\n"
                    f"📱 Device: {gps_data.get('device_make', 'Unknown')} {gps_data.get('device_model', '')}\n\n"
                    f"_This helps verify your farm location for EUDR compliance._\n\n"
                    f"Confirm to complete registration."
                ),
                'parse_mode': 'Markdown',
                'inline_keyboard': [[
                    {'text': '✅ Confirm', 'callback_data': 'reg_confirm_gps'},
                    {'text': '🔄 Retry', 'callback_data': 'reg_retry_photo'}
                ]]
            }
        
    except GPSExtractionError as e:
        logger.error(f"GPS extraction failed for user {user_id}: {e}")
        return {
            'message': (
                f"❌ *GPS Extraction Failed*\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try uploading a different photo with GPS enabled."
            ),
            'parse_mode': 'Markdown',
            'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
        }
    except Exception as e:
        logger.error(f"Error processing farm photo: {e}", exc_info=True)
        return {
            'message': "❌ Failed to process photo. Please try again or skip for now.",
            'inline_keyboard': [[{'text': '⏭️ Skip for now', 'callback_data': 'reg_skip_photo'}]]
        }
    finally:
        db.close()


async def complete_farmer_registration(user_id: int, skip_photo: bool = False) -> Dict[str, Any]:
    """
    Complete farmer registration with or without GPS photo verification.
    """
    from database.models import SessionLocal, UserIdentity, FarmerIdentity
    from ssi.user_identity import get_or_create_user_identity
    from datetime import datetime
    
    if user_id not in conversation_states:
        return {'message': "❌ Session expired. Please /register again."}
    
    db = SessionLocal()
    try:
        # Create/update user identity
        identity = get_or_create_user_identity(
            telegram_user_id=str(user_id),
            telegram_username=conversation_states[user_id]['data'].get('telegram_username'),
            telegram_first_name=conversation_states[user_id]['data'].get('telegram_first_name'),
            telegram_last_name=conversation_states[user_id]['data'].get('telegram_last_name'),
            db_session=db
        )
        
        # Update user preferences (but NOT approved yet)
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if user:
            user.preferred_language = conversation_states[user_id]['data'].get('preferred_language', 'en')
            user.role = 'FARMER'
            user.language_set_at = datetime.utcnow()
            # NOTE: is_approved set to True AFTER FarmerIdentity is created successfully
        
        # Create or update FarmerIdentity with GPS photo data
        # CRITICAL: FarmerIdentity must be created during registration to preserve GPS verification
        farmer = db.query(FarmerIdentity).filter_by(did=identity['did']).first()
        
        if not farmer:
            # Create FarmerIdentity linked to UserIdentity
            # This ensures GPS photo data from registration is preserved
            farmer_id_str = f"FARMER-{user.id}"  # Link to UserIdentity.id
            
            farmer = FarmerIdentity(
                farmer_id=farmer_id_str,
                did=identity['did'],  # Same DID as UserIdentity for linkage
                encrypted_private_key=user.encrypted_private_key,
                public_key=user.public_key,
                name=f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip(),
                phone_number=user.phone_number,
                country_code='ET'  # Default to Ethiopia for Voice Ledger
            )
            db.add(farmer)
            db.flush()
            logger.info(f"Created FarmerIdentity {farmer_id_str} for user {user_id} during registration")
        
        # Update farmer with GPS photo data (if provided)
        if not skip_photo and 'farm_photo' in conversation_states[user_id]['data']:
            photo_data = conversation_states[user_id]['data']['farm_photo']
            
            farmer.farm_photo_url = photo_data['file_url']
            farmer.farm_photo_hash = photo_data['hash']
            farmer.photo_latitude = photo_data['latitude']
            farmer.photo_longitude = photo_data['longitude']
            farmer.photo_timestamp = datetime.fromisoformat(photo_data['timestamp']) if photo_data['timestamp'] else None
            farmer.gps_verified_at = datetime.utcnow()
            farmer.photo_device_make = photo_data.get('device_make')
            farmer.photo_device_model = photo_data.get('device_model')
            
            # Set farm coordinates from GPS photo (EUDR plot-level traceability)
            if not farmer.latitude:
                farmer.latitude = photo_data['latitude']
            if not farmer.longitude:
                farmer.longitude = photo_data['longitude']
            
            logger.info(f"Updated farmer {farmer.farmer_id} with GPS-verified photo: {photo_data['latitude']:.6f}, {photo_data['longitude']:.6f}")
        
        # Only approve AFTER FarmerIdentity is successfully created
        if user:
            user.is_approved = True  # Farmers are auto-approved after FarmerIdentity created
            user.approved_at = datetime.utcnow()
        
        db.commit()
        
        # Clear conversation state
        lang = conversation_states[user_id]['data'].get('preferred_language', 'en')
        gps_verified = not skip_photo and 'farm_photo' in conversation_states[user_id]['data']
        conversation_states.pop(user_id, None)
        
        lang_name = "English" if lang == 'en' else "Amharic (አማርኛ)"
        
        if lang == 'am':
            message = (
                f"✅ *ምዝገባ ተጠናቀቀ!*\n\n"
                f"ሚና፡ *ገበሬ*\n"
                f"ቋንቋ፡ *{lang_name}*\n"
            )
            if gps_verified:
                message += f"📍 GPS ማረጋገጫ፡ *✅ ተረጋግጧል*\n"
            message += (
                f"\n"
                f"አሁን የቡና ጥሬ ዕቃዎችን በድምጽ መልዕክቶች መመዝገብ ይችላሉ!\n\n"
                f"🎤 ይሞክሩ፡\n"
                f"• \"ከጌዴዎ 50 ኪሎግራም ቡና ሰበሰብኩ\"\n"
                f"• \"100 ኪሎግራም ሲዳማ ይመዝገብ\"\n\n"
                f"ትዕዛዞች፡\n"
                f"/language - ቋንቋ ለመቀየር\n"
                f"/mybatches - የእርስዎን ጥሬ ዕቃዎች ለማየት\n"
                f"/help - እገዛ ለማግኘት"
            )
        else:
            message = (
                f"✅ *Registration Complete!*\n\n"
                f"Role: *Farmer*\n"
                f"Language: *{lang_name}*\n"
            )
            if gps_verified:
                message += f"📍 GPS Verification: *✅ Verified*\n"
            message += (
                f"\n"
                f"You can now record coffee batches using voice messages!\n\n"
                f"🎤 Try saying:\n"
                f"• \"I harvested 50 kg of coffee from Gedeo\"\n"
                f"• \"Record 100 kilograms Sidama\"\n\n"
                f"Commands:\n"
                f"/language - Change language\n"
                f"/mybatches - View your batches\n"
                f"/help - Get help"
            )
        
        return {
            'message': message,
            'parse_mode': 'Markdown'
        }
    
    except Exception as e:
        logger.error(f"Error completing farmer registration: {e}", exc_info=True)
        return {
            'message': "❌ Registration failed. Please try again with /register"
        }
    finally:
        db.close()


# Export main functions for use in telegram_api webhook handler
__all__ = [
    'handle_register_command',
    'handle_registration_callback',
    'handle_registration_text',
    'handle_farm_photo_upload',
    'complete_farmer_registration',
    'conversation_states',
    'STATE_NONE',
    'STATE_ROLE',
    'STATE_FULL_NAME',
    'STATE_ORG_NAME',
    'STATE_LOCATION',
    'STATE_PHONE',
    'STATE_REG_NUMBER',
    'STATE_REASON',
    'STATE_EXPORT_LICENSE',
    'STATE_PORT_ACCESS',
    'STATE_SHIPPING_CAPACITY',
    'STATE_BUSINESS_TYPE',
    'STATE_COUNTRY',
    'STATE_TARGET_VOLUME',
    'STATE_QUALITY_PREFS',
    'STATE_UPLOAD_FARM_PHOTO',
    'STATE_VERIFY_GPS'
]
