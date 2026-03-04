"""
Telegram RFQ Marketplace Handler
Lab 15 - Buyer and Cooperative marketplace commands

Commands:
- /rfq - Buyer creates Request for Quote
- /offers - Cooperative views available RFQs and submits offers
- /myoffers - Cooperative dashboard to track submitted offers
- /myrfqs - Buyer dashboard to track posted RFQs and received offers
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from database.models import UserIdentity, Organization, SessionLocal
from voice.telegram.voice_responses import escape_markdown

logger = logging.getLogger(__name__)


async def handle_rfq_callback(user_id: int, callback_data: str, username: str = None) -> Dict[str, Any]:
    """
    Handle RFQ-related callback queries.
    
    Args:
        user_id: Telegram user ID
        callback_data: Callback data from button click
        
    Returns:
        Response dict with message and optional keyboard
    """
    try:
        if callback_data == 'myoffers':
            # Handle "My Offers" button - need username for user lookup
            return await handle_myoffers_command(user_id, username=None)
            
        elif callback_data == 'offers':
            # Handle "Offers" button - need username for user lookup
            return await handle_offers_command(user_id, username=None)
            
        elif callback_data == 'rfq':
            # Handle "Create RFQ" button
            return await handle_rfq_command(user_id, username)
            
        elif callback_data == 'myrfqs':
            # Handle "My RFQs" button
            return await handle_myrfqs_command(user_id, username)
            
        elif callback_data.startswith('offer_'):
            # Handle "Offer for RFQ" button - extract RFQ number from callback
            rfq_number = callback_data.split('_', 1)[1]  # Get everything after "offer_"
            return await handle_offer_creation(user_id, rfq_number)
            
        else:
            return {
                'message': '❌ Unknown RFQ action',
                'parse_mode': 'Markdown'
            }
            
    except Exception as e:
        logger.error(f"Error handling RFQ callback: {e}")
        return {
            'message': '❌ Error processing request',
            'parse_mode': 'Markdown'
        }


async def handle_offer_creation(user_id: int, rfq_number: str) -> Dict[str, Any]:
    """
    Handle offer creation for a specific RFQ.
    
    Args:
        user_id: Telegram user ID
        rfq_number: RFQ number (e.g., "RFQ-000010")
        
    Returns:
        Response dict with message and keyboard
    """
    try:
        # Get RFQ details by RFQ number
        API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000/api')
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Search RFQ by number
            list_response = await client.get(f"{API_BASE_URL}/rfqs?status=OPEN")
            if list_response.status_code != 200:
                return {
                    'message': '❌ Error loading RFQs',
                    'parse_mode': 'Markdown'
                }
            
            rfqs = list_response.json()
            # Find RFQ by number
            rfq = None
            for r in rfqs:
                if r.get('rfq_number') == rfq_number:
                    rfq = r
                    break
            
            if not rfq:
                return {
                    'message': f'❌ RFQ {rfq_number} not found',
                    'parse_mode': 'Markdown'
                }
            
            message = f"📋 **RFQ Details**\n\n"
            message += f"🔢 *RFQ Number*: {escape_markdown(rfq.get('rfq_number', 'N/A'))}\n"
            message += f"☕ *Variety*: {escape_markdown(rfq.get('variety', 'N/A'))}\n"
            message += f"⚖️ *Quantity*: {rfq.get('quantity_kg', 'N/A')} kg\n"
            message += f"⭐ *Grade*: {escape_markdown(rfq.get('grade', 'N/A'))}\n"
            message += f"🏷️ *Status*: {escape_markdown(rfq.get('status', 'N/A'))}\n"
            message += f"🌊 *Processing Method*: {escape_markdown(rfq.get('processing_method', 'N/A'))}\n"
            message += f"🏢 *Buyer Organization*: {escape_markdown(rfq.get('buyer_organization', 'N/A'))}\n"
            message += f"📍 *Location*: {escape_markdown(rfq.get('delivery_location', 'N/A'))}\n"
            message += f"💬 *Offers*: {rfq.get('offer_count', 0)}\n"
            message += f"📅 *Deadline*: {escape_markdown(rfq.get('delivery_deadline', 'N/A'))}\n\n"
            
            keyboard = [
                [{'text': '🔙 Back to Offers', 'callback_data': 'offers'}],
                [{'text': '📊 My Offers', 'callback_data': 'myoffers'}]
            ]
            
            return {
                'message': message,
                'parse_mode': 'Markdown',
                'inline_keyboard': keyboard
            }
            
    except Exception as e:
        logger.error(f"Error handling offer creation: {e}")
        return {
            'message': '❌ Error loading RFQ details',
            'parse_mode': 'Markdown'
        }

# API base URL
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000/api')

# Debug: Log the final API URL
logger.info(f"API_BASE_URL configured: {API_BASE_URL}")

# In-memory conversation state for multi-step RFQ creation
rfq_sessions: Dict[int, Dict[str, Any]] = {}

# RFQ creation states
STATE_QUANTITY = 1
STATE_VARIETY = 2
STATE_GRADE = 3
STATE_PROCESSING = 4
STATE_LOCATION = 5
STATE_DEADLINE = 6
STATE_CONFIRM = 7


async def handle_rfq_command(user_id: int, username: str) -> Dict[str, Any]:
    """
    Start RFQ creation flow (Buyer only)
    
    Command: /rfq
    
    Returns:
        Dict with message and keyboard
    """
    db = SessionLocal()
    try:
        # Authenticate user
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user:
            return {
                'message': (
                    "❌ *Not Registered*\n\n"
                    "You must register first to use the marketplace.\n"
                    "Use /register to get started."
                ),
                'parse_mode': 'Markdown'
            }
        
        if not user.is_approved:
            return {
                'message': (
                    "⏳ *Pending Approval*\n\n"
                    "Your registration is pending admin approval.\n"
                    "You'll be notified when approved."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check role (TEMP: Allow ADMIN for testing)
        if user.role not in ["BUYER", "ADMIN"]:
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only registered buyers can create RFQs.\n"
                    f"Your role: {user.role}\n\n"
                    "Cooperatives: Use /offers to view and respond to RFQs."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Start RFQ session
        rfq_sessions[user_id] = {
            'user_id': user.id,
            'user_role': user.role,
            'organization_id': user.organization_id,
            'state': STATE_QUANTITY,
            'data': {},
            'started_at': datetime.utcnow()
        }
        
        user_name = user.telegram_first_name or 'there'
        return {
            'message': (
                "🛒 *Create Request for Quote (RFQ)*\n\n"
                f"Welcome {user_name}!\n"
                f"Organization: {user.organization.name if user.organization else 'N/A'}\n\n"
                "Let's create your RFQ step by step.\n\n"
                "📦 *Step 1/6: Quantity*\n\n"
                "How many kilograms of coffee do you need?\n"
                "Example: 5000"
            ),
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': '1000 kg'}, {'text': '5000 kg'}],
                [{'text': '10000 kg'}, {'text': '20000 kg'}],
                [{'text': '❌ Cancel'}]
            ]
        }
    finally:
        db.close()


async def handle_rfq_message(user_id: int, message_text: str) -> Dict[str, Any]:
    """
    Handle multi-step RFQ creation conversation
    
    Args:
        user_id: Telegram user ID
        message_text: User's text input
        
    Returns:
        Dict with response message and keyboard
    """
    # Check if user has active session
    if user_id not in rfq_sessions:
        return {
            'message': (
                "No active RFQ session.\n"
                "Use /rfq to start creating a new request."
            )
        }
    
    session = rfq_sessions[user_id]
    state = session['state']
    
    # Handle cancel
    if message_text.strip().lower() in ['cancel', '❌ cancel']:
        del rfq_sessions[user_id]
        return {
            'message': "❌ RFQ creation cancelled.",
            'keyboard': [[{'text': '/rfq - Create New RFQ'}]]
        }
    
    # State machine
    if state == STATE_QUANTITY:
        return await handle_quantity_input(user_id, message_text, session)
    elif state == STATE_VARIETY:
        return await handle_variety_input(user_id, message_text, session)
    elif state == STATE_GRADE:
        return await handle_grade_input(user_id, message_text, session)
    elif state == STATE_PROCESSING:
        return await handle_processing_input(user_id, message_text, session)
    elif state == STATE_LOCATION:
        return await handle_location_input(user_id, message_text, session)
    elif state == STATE_DEADLINE:
        return await handle_deadline_input(user_id, message_text, session)
    elif state == STATE_CONFIRM:
        return await handle_confirm_input(user_id, message_text, session)
    
    return {'message': 'Invalid state. Use /rfq to start over.'}


async def handle_quantity_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle quantity input (Step 1)"""
    try:
        # Parse quantity (handle "5000 kg" or "5000")
        quantity = float(text.replace('kg', '').strip())
        
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if quantity > 1000000:
            return {
                'message': "⚠️ Quantity seems too large. Please enter a realistic amount (max 1,000,000 kg).",
                'keyboard': [[{'text': '❌ Cancel'}]]
            }
        
        session['data']['quantity_kg'] = quantity
        session['state'] = STATE_VARIETY
        
        return {
            'message': (
                f"✅ Quantity: {quantity:,.0f} kg\n\n"
                "☕ *Step 2/6: Variety*\n\n"
                "Which coffee variety do you need?\n"
                "Select from options or type custom variety:"
            ),
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': 'YIRGACHEFFE'}, {'text': 'SIDAMO'}],
                [{'text': 'GUJI'}, {'text': 'HARAR'}],
                [{'text': 'LIMU'}, {'text': 'JIMMA'}],
                [{'text': 'Any Variety'}, {'text': '❌ Cancel'}]
            ]
        }
    except ValueError:
        return {
            'message': (
                "⚠️ Invalid quantity. Please enter a number.\n"
                "Example: 5000"
            ),
            'keyboard': [[{'text': '❌ Cancel'}]]
        }


async def handle_variety_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle variety input (Step 2)"""
    variety = text.strip().upper()
    session['data']['variety'] = variety
    session['state'] = STATE_GRADE
    
    return {
        'message': (
            f"✅ Variety: {escape_markdown(variety)}\n\n"
            "⭐ *Step 3/6: Grade*\n\n"
            "What quality grade do you need?"
        ),
        'parse_mode': 'Markdown',
        'keyboard': [
            [{'text': 'GRADE_1'}, {'text': 'GRADE_2'}],
            [{'text': 'GRADE_3'}, {'text': 'GRADE_4'}],
            [{'text': 'Any Grade'}, {'text': '❌ Cancel'}]
        ]
    }


async def handle_grade_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle grade input (Step 3)"""
    grade = text.strip().upper()
    session['data']['grade'] = grade
    session['state'] = STATE_PROCESSING
    
    return {
        'message': (
            f"✅ Grade: {escape_markdown(grade)}\n\n"
            "🌊 *Step 4/6: Processing Method*\n\n"
            "Which processing method do you prefer?"
        ),
        'parse_mode': 'Markdown',
        'keyboard': [
            [{'text': 'WASHED'}, {'text': 'NATURAL'}],
            [{'text': 'HONEY'}, {'text': 'PULPED_NATURAL'}],
            [{'text': 'Any Processing'}, {'text': '❌ Cancel'}]
        ]
    }


async def handle_processing_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle processing method input (Step 4)"""
    processing = text.strip().upper()
    session['data']['processing_method'] = processing if processing != 'ANY PROCESSING' else None
    session['state'] = STATE_LOCATION
    
    return {
        'message': (
            f"✅ Processing: {escape_markdown(processing)}\n\n"
            "📍 *Step 5/6: Delivery Location*\n\n"
            "Where should the coffee be delivered?\n"
            "Example: Addis Ababa, Djibouti Port, etc."
        ),
        'parse_mode': 'Markdown',
        'keyboard': [
            [{'text': 'Addis Ababa'}, {'text': 'Dire Dawa'}],
            [{'text': 'Djibouti Port'}, {'text': 'Berbera Port'}],
            [{'text': '❌ Cancel'}]
        ]
    }


async def handle_location_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle delivery location input (Step 5)"""
    location = text.strip()
    session['data']['delivery_location'] = location
    session['state'] = STATE_DEADLINE
    
    return {
        'message': (
            f"✅ Location: {escape_markdown(location)}\n\n"
            "📅 *Step 6/6: Delivery Deadline*\n\n"
            "When do you need the coffee delivered?\n"
            "Use format: YYYY-MM-DD\n"
            "Example: 2025-02-15"
        ),
        'parse_mode': 'Markdown',
        'keyboard': [
            [{'text': f'{(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")}'}, 
             {'text': f'{(datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")}'}],
            [{'text': f'{(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")}'}, 
             {'text': '❌ Cancel'}]
        ]
    }


async def handle_deadline_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle deadline input (Step 6) - accepts natural language dates"""
    try:
        from dateutil import parser as date_parser
        import re
        
        text_clean = text.strip().lower()
        deadline = None
        
        # Try parsing relative dates first
        if re.search(r'(\d+)\s*(day|days|week|weeks|month|months)', text_clean):
            # Extract number and unit
            match = re.search(r'(\d+)\s*(day|days|week|weeks|month|months)', text_clean)
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                
                if 'day' in unit:
                    deadline = (datetime.now() + timedelta(days=num)).date()
                elif 'week' in unit:
                    deadline = (datetime.now() + timedelta(weeks=num)).date()
                elif 'month' in unit:
                    deadline = (datetime.now() + timedelta(days=num*30)).date()
        
        # Try parsing absolute dates (natural language)
        if not deadline:
            try:
                parsed = date_parser.parse(text, fuzzy=True)
                deadline = parsed.date()
            except:
                # Try standard format as fallback
                deadline = datetime.strptime(text.strip(), '%Y-%m-%d').date()
        
        # Validate deadline is in the future
        if deadline <= datetime.now().date():
            return {
                'message': "⚠️ Deadline must be in the future. Please try again.",
                'keyboard': [[{'text': '❌ Cancel'}]]
            }
        
        # Ensure it's a full ISO datetime string for the API
        session['data']['delivery_deadline'] = datetime.combine(deadline, datetime.min.time()).isoformat()
        session['state'] = STATE_CONFIRM
        
        # Show summary
        data = session['data']
        return {
            'message': (
                f"✅ Deadline: {escape_markdown(deadline.strftime('%B %d, %Y'))}\n\n"
                "📋 *Review your RFQ:*\n\n"
                f"📦 Quantity: {data['quantity_kg']:,.0f} kg\n"
                f"☕ Variety: {escape_markdown(data['variety'])}\n"
                f"⭐ Grade: {escape_markdown(data['grade'])}\n"
                f"🔧 Processing: {escape_markdown(data.get('processing_method', 'Any'))}\n"
                f"📍 Location: {escape_markdown(data['delivery_location'])}\n"
                f"📅 Delivery: {escape_markdown(deadline.strftime('%B %d, %Y'))}\n\n"
                "Is everything correct?"
            ),
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': '✅ Confirm & Broadcast'}, {'text': '❌ Cancel'}]
            ]
        }
    except Exception as e:
        logger.warning(f"Date parsing failed for '{text}': {e}")
        return {
            'message': (
                "⚠️ I couldn't understand that date.\n\n"
                "Try saying:\n"
                "• '30 days' or '2 months'\n"
                "• 'March 15' or '15th of March'\n"
                "• '2025-03-15' (YYYY-MM-DD)\n"
            ),
            'keyboard': [[{'text': '❌ Cancel'}]]
        }


async def handle_confirm_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle confirmation and create RFQ via API (Step 7)"""
    text_lower = text.strip().lower()
    
    # Check for cancellation keywords
    cancel_keywords = ['cancel', 'no', 'stop', 'abort', 'nevermind', 'never mind']
    if any(keyword in text_lower for keyword in cancel_keywords):
        del rfq_sessions[user_id]
        return {
            'message': "❌ RFQ creation cancelled.",
            'keyboard': [[{'text': '/rfq - Create New RFQ'}]]
        }
    
    # Check for confirmation keywords (more lenient)
    confirm_keywords = ['yes', 'confirm', 'ok', 'okay', 'sure', 'proceed', 'broadcast', 'ready']
    if not any(keyword in text_lower for keyword in confirm_keywords):
        # Unclear response - ask again
        return {
            'message': "⚠️ I didn't understand. Please confirm or cancel:",
            'keyboard': [
                [{'text': '✅ Confirm & Broadcast'}, {'text': '❌ Cancel'}]
            ]
        }
    
    # Call API to create RFQ
    try:
        data = session['data']
        api_url = f"{API_BASE_URL}/rfq?user_id={session['user_id']}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json={
                'quantity_kg': data['quantity_kg'],
                'variety': data['variety'],
                'grade': data['grade'],
                'processing_method': data.get('processing_method'),
                'delivery_location': data['delivery_location'],
                'delivery_deadline': data['delivery_deadline']
            })
        
        if response.status_code == 201:
            rfq = response.json()
            broadcast_count = rfq.get('broadcast_count', 0)
            
            # Clean up session
            del rfq_sessions[user_id]
            
            return {
                'message': (
                    "✅ *RFQ Created Successfully!*\n\n"
                    f"📋 RFQ Number: `{escape_markdown(rfq['rfq_number'])}`\n"
                    f"📦 Quantity: {rfq['quantity_kg']:,.0f} kg\n"
                    f"☕ Variety: {escape_markdown(rfq['variety'])}\n"
                    f"⭐ Grade: {escape_markdown(rfq.get('grade', 'Not specified'))}\n"
                    f"🔧 Processing: {escape_markdown(rfq.get('processing_method', 'Any'))}\n"
                    f"📍 Location: {escape_markdown(rfq.get('delivery_location', 'Not specified'))}\n\n"
                    f"🔔 *Broadcasted to {broadcast_count} cooperatives*\n"
                    f"Status: {escape_markdown(rfq['status'])}\n"
                    f"Expires: {escape_markdown(rfq.get('expires_at', 'N/A')[:10] if rfq.get('expires_at') else 'N/A')}\n\n"
                    f"💡 Use /myrfqs to track offers as they come in."
                ),
                'parse_mode': 'Markdown',
                'keyboard': [
                    [{'text': '/myrfqs - View My RFQs'}],
                    [{'text': '/rfq - Create Another RFQ'}]
                ]
            }
        else:
            error_detail = response.text
            logger.error(f"API Error (Status {response.status_code}): {error_detail}")
            
            try:
                error_json = response.json()
                error_msg = error_json.get('detail', 'Unknown error')
                if isinstance(error_msg, list):
                    # Format validation errors nicely
                    error_msg = "; ".join([f"{e.get('loc', [])}: {e.get('msg')}" for e in error_msg])
            except:
                error_msg = response.text
                
            return {
                'message': f"❌ Failed to create RFQ: {escape_markdown(str(error_msg))}",
                'keyboard': [[{'text': '/rfq - Try Again'}]]
            }
    
    except Exception as e:
        logger.error(f"Error creating RFQ: {e}")
        return {
            'message': (
                "❌ Error creating RFQ. Please try again later.\n"
                f"Error: {str(e)}"
            ),
            'keyboard': [[{'text': '/rfq - Try Again'}]]
        }


async def handle_offers_command(user_id: int, username: str) -> Dict[str, Any]:
    """
    Show available RFQs (Cooperative only)
    
    Command: /offers
    
    Returns:
        Dict with message and inline keyboard
    """
    db = SessionLocal()
    try:
        # Authenticate user
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user:
            return {
                'message': (
                    "❌ *Not Registered*\n\n"
                    "You must register first to use the marketplace.\n"
                    "Use /register to get started."
                ),
                'parse_mode': 'Markdown'
            }
        
        if user.role != "COOPERATIVE_MANAGER":
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only cooperative managers can view and respond to RFQs.\n"
                    f"Your role: {user.role}\n\n"
                    "Buyers: Use /rfq to create purchase requests."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Fetch open RFQs from API
        api_url = f"{API_BASE_URL}/rfqs?status=OPEN"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
        
        if response.status_code != 200:
            return {
                'message': "❌ Error fetching RFQs. Please try again later."
            }
        
        rfqs = response.json()
        
        if not rfqs:
            return {
                'message': (
                    "📭 *No Open RFQs*\n\n"
                    "There are currently no open purchase requests.\n"
                    "Check back later!"
                ),
                'parse_mode': 'Markdown'
            }
        
        # Build message with RFQ list
        user_name = user.telegram_first_name or 'there'
        message = f"🛒 *Open Purchase Requests ({len(rfqs)})*\n\n"
        message += f"Hello {user_name}!\n"
        message += f"Organization: {user.organization.name if user.organization else 'N/A'}\n\n"
        
        keyboard = []
        for rfq in rfqs[:10]:  # Show first 10
            rfq_summary = (
                f"📋 *{escape_markdown(rfq['rfq_number'])}*\n"
                f"📦 {rfq['quantity_kg']:,.0f} kg {escape_markdown(rfq['variety'])} {escape_markdown(rfq['grade'])}\n"
                f"📍 {escape_markdown(rfq['delivery_location'])}\n"
                f"📅 Deadline: {escape_markdown(rfq['delivery_deadline'])}\n"
                f"💬 Offers: {rfq.get('offer_count', 0)}\n\n"
            )
            message += rfq_summary
            
            # Add button to make offer
            keyboard.append([
                {'text': f"💰 Offer for {rfq['rfq_number']}", 'callback_data': f"offer_{rfq['rfq_number']}"}
            ])
        
        if len(rfqs) > 10:
            message += f"\n_Showing first 10 of {len(rfqs)} RFQs_\n"
        
        keyboard.append([{'text': '📊 My Offers', 'callback_data': 'myoffers'}])
        
        return {
            'message': message,
            'parse_mode': 'Markdown',
            'keyboard': keyboard
        }
    
    except Exception as e:
        logger.error(f"Error fetching offers: {e}")
        return {
            'message': f"❌ Error: {str(e)}"
        }
    finally:
        db.close()


async def handle_myoffers_command(user_id: int, username: str) -> Dict[str, Any]:
    """
    Show cooperative's submitted offers (Cooperative only)
    
    Command: /myoffers
    
    Returns:
        Dict with message showing offer status
    """
    db = SessionLocal()
    try:
        # Authenticate user
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user or user.role not in ["COOPERATIVE_MANAGER", "ADMIN"]:
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only cooperative managers can view their offers."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Store organization name before closing session
        org_name = user.organization.name if user.organization else 'Your Organization'
        
        # Close first connection to avoid SSL timeout
        db.close()
        
        # Fetch offers from API
        api_url = f"{API_BASE_URL}/offers?user_id={user.id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
        
        if response.status_code != 200:
            return {
                'message': "❌ Error fetching your offers. Please try again later."
            }
        
        offers = response.json()
        
        if not offers:
            return {
                'message': (
                    "📭 *No Offers Yet*\n\n"
                    "You haven't submitted any offers.\n"
                    "Use /offers to view and respond to RFQs."
                ),
                'parse_mode': 'Markdown',
                'keyboard': [[{'text': '📋 Available RFQs', 'callback_data': 'offers'}]]
            }
        
        # Build message
        message = f"📊 *Your Offers ({len(offers)})*\n\n"
        message += f"{org_name}\n\n"
        
        for offer in offers:
            status_emoji = {
                'PENDING': '⏳',
                'ACCEPTED': '✅',
                'REJECTED': '❌',
                'WITHDRAWN': '↩️'
            }.get(offer['status'], '📝')
            
            total_value = offer['quantity_offered_kg'] * offer['price_per_kg']
            message += (
                f"{status_emoji} *{escape_markdown(offer['offer_number'])}*\n"
                f"RFQ: {offer['rfq_id']}\n"
                f"💰 ${offer['price_per_kg']}/kg × {offer['quantity_offered_kg']:,.0f} kg\n"
                f"💵 Total: ${total_value:,.2f}\n"
                f"⏱️ Delivery: {escape_markdown(offer.get('delivery_timeline', 'N/A'))}\n"
                f"Status: {escape_markdown(offer['status'])}\n\n"
            )
        
        return {
            'message': message,
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': '📋 Available RFQs', 'callback_data': 'offers'}],
                [{'text': '🔄 Refresh', 'callback_data': 'refresh_myoffers'}]
            ]
        }
    
    except Exception as e:
        logger.error(f"Error fetching my offers: {e}")
        return {
            'message': f"❌ Error: {str(e)}"
        }


async def handle_myrfqs_command(user_id: int, username: str) -> Dict[str, Any]:
    """
    Show buyer's RFQs and received offers (Buyer only)
    
    Command: /myrfqs
    
    Returns:
        Dict with message showing RFQ status and offers
    """
    db = SessionLocal()
    try:
        # Authenticate user
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user or user.role not in ["BUYER", "ADMIN"]:
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only buyers can view their RFQs."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Fetch buyer's RFQs from API
        api_url = f"{API_BASE_URL}/rfqs?buyer_id={user.id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
        
        if response.status_code != 200:
            return {
                'message': "❌ Error fetching your RFQs. Please try again later."
            }
        
        rfqs = response.json()
        
        if not rfqs:
            return {
                'message': (
                    "📭 *No RFQs Yet*\n\n"
                    "You haven't created any purchase requests.\n"
                    "Use /rfq to create your first RFQ."
                ),
                'parse_mode': 'Markdown',
                'inline_keyboard': [[{'text': '➕ Create RFQ', 'callback_data': 'rfq'}]]
            }
        
        # Build message
        message = f"📋 *Your RFQs ({len(rfqs)})*\n\n"
        
        keyboard = []
        for rfq in rfqs:
            status_emoji = {
                'OPEN': '🟢',
                'PARTIALLY_FILLED': '🟡',
                'FULFILLED': '✅',
                'CANCELLED': '❌',
                'EXPIRED': '⏰'
            }.get(rfq['status'], '📝')
            
            message += (
                f"{status_emoji} *{escape_markdown(rfq['rfq_number'])}*\n"
                f"📦 {rfq['quantity_kg']:,.0f} kg {escape_markdown(rfq['variety'])}\n"
                f"💬 Offers: {rfq.get('offer_count', 0)}\n"
                f"Status: {escape_markdown(rfq['status'])}\n\n"
            )
            
            if rfq.get('offer_count', 0) > 0:
                keyboard.append([
                    {'text': f"👀 View Offers for {rfq['rfq_number']}", 
                     'callback_data': f"view_offers_{rfq['id']}"}
                ])
        
        keyboard.append([{'text': '➕ Create New RFQ', 'callback_data': 'rfq'}])
        
        return {
            'message': message,
            'parse_mode': 'Markdown',
            'inline_keyboard': keyboard
        }
    
    except Exception as e:
        logger.error(f"Error fetching my RFQs: {e}")
        return {
            'message': f"❌ Error: {str(e)}"
        }
    finally:
        db.close()


async def handle_rfq_voice_clarification(
    user_id: int,
    transcript: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle voice clarification messages during RFQ creation flow.
    
    When a user has an active RFQ session and sends a voice message,
    this routes it to the appropriate step handler.
    
    Args:
        user_id: Telegram user ID
        transcript: Voice transcript
        metadata: Request metadata
        
    Returns:
        Response dict with message and keyboard
    """
    from voice.channels.processor import get_processor
    
    processor = get_processor()
    
    # Route to text message handler (reuse existing logic)
    response = await handle_rfq_message(user_id, transcript)
    
    # Send response via Telegram (use processor for voice support)
    try:
        # Always use processor for consistent voice delivery
        await processor.send_notification(
            channel_name='telegram',
            user_id=user_id,
            message=response['message'],
            parse_mode=response.get('parse_mode', 'Markdown'),
            reply_markup=response.get('keyboard') or response.get('inline_keyboard'),
            send_voice=True  # Clarification questions should have voice
        )
    except Exception as e:
        logger.error(f"Failed to send RFQ clarification response: {e}")
    
    return {"ok": True, "message": "RFQ clarification processed"}


async def handle_voice_rfq_creation(
    user_id: int,
    transcript: str,
    extraction: Dict[str, Any],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle RFQ creation from voice message.
    
    Args:
        user_id: Telegram user ID
        transcript: Original voice transcript
        extraction: Extracted RFQ data from voice_rfq_extractor
        metadata: Request metadata
        
    Returns:
        Response dict with message and optional keyboard
    """
    from voice.channels.processor import get_processor
    from voice.marketplace.voice_rfq_extractor import format_rfq_preview, create_missing_field_question
    
    db = SessionLocal()
    processor = get_processor()
    
    try:
        # Authenticate user
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user:
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message="❌ Not registered. Use /register to get started.",
                send_voice=False  # Error message - text only
            )
            return {"ok": False}
        
        if not user.is_approved:
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message="⏳ Your registration is pending admin approval.",
                send_voice=False  # Status notification - text only
            )
            return {"ok": False}
        
        # Check role (TEMP: Allow ADMIN for testing)
        if user.role not in ["BUYER", "ADMIN"]:
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=(
                    "⚠️ *Access Denied*\n\n"
                    "Only registered buyers can create RFQs.\n"
                    f"Your role: {user.role}\n\n"
                    "Cooperatives: Use /offers to view available RFQs."
                ),
                parse_mode='Markdown',
                send_voice=False  # Access error - text only
            )
            return {"ok": False}
        
        fields = extraction.get('extracted_fields', {})
        missing = extraction.get('missing_fields', [])
        confidence = extraction.get('confidence', 0.0)
        
        logger.info(f"Voice RFQ extraction: confidence={confidence}, missing={len(missing)} fields")
        
        # Show preview
        preview = format_rfq_preview(extraction)
        preview += f"\n🎤 *From voice:* {transcript[:100]}...\n"
        
        await processor.send_notification(
            channel_name='telegram',
            user_id=user_id,
            message=preview,
            parse_mode='Markdown',
            send_voice=True  # Preview - conversational content
        )
        
        # If confidence is low or ANY fields missing, start conversation flow
        if confidence < 0.6 or len(missing) > 0:
            # Store partial data in session
            rfq_sessions[user_id] = {
                'user_id': user.id,
                'user_role': user.role,
                'organization_id': user.organization_id,
                'state': STATE_QUANTITY if not fields.get('quantity_kg') else (
                    STATE_VARIETY if not fields.get('variety') else (
                        STATE_GRADE if not fields.get('grade') else (
                            STATE_PROCESSING if not fields.get('processing_method') else (
                                STATE_LOCATION if not fields.get('delivery_location') else STATE_DEADLINE
                            )
                        )
                    )
                ),
                'data': {
                    'quantity_kg': fields.get('quantity_kg'),
                    'variety': fields.get('variety'),
                    'grade': fields.get('grade'),
                    'processing_method': fields.get('processing_method'),
                    'delivery_location': fields.get('delivery_location'),
                    'deadline_days': fields.get('deadline_days')
                },
                'started_at': datetime.utcnow(),
                'from_voice': True
            }
            
            # Ask for first missing field
            first_missing = missing[0] if missing else 'quantity_kg'
            question = create_missing_field_question(first_missing)
            
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=question['message'],
                reply_markup=question.get('keyboard'),
                send_voice=True  # Question - conversational content
            )
            
            return {"ok": True, "needs_clarification": True}
        
        # High confidence - create RFQ directly
        try:
            from datetime import timedelta
            
            rfq_data = {
                "buyer_user_id": user.id,
                "buyer_organization_id": user.organization_id,
                "quantity_kg": fields['quantity_kg'],
                "variety": fields['variety'] or "Arabica",
                "grade": fields.get('grade'),
                "processing_method": fields.get('processing_method') or "Washed",
                "delivery_location": fields.get('delivery_location'),
                "deadline": (datetime.utcnow() + timedelta(days=fields['deadline_days'])).isoformat() if fields.get('deadline_days') else None,
                "status": "OPEN"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/rfq?user_id={user.id}",
                    json=rfq_data,
                    headers={"Content-Type": "application/json"}
                )
            
            if response.status_code in [200, 201]:  # Accept both 200 and 201
                rfq = response.json()
                broadcast_count = rfq.get('broadcast_count', 0)
                
                await processor.send_notification(
                    channel_name='telegram',
                    user_id=user_id,
                    message=(
                        f"✅ *RFQ Created from Voice!*\n\n"
                        f"📋 RFQ Number: `{escape_markdown(rfq['rfq_number'])}`\n"
                        f"📦 Quantity: {rfq['quantity_kg']:,.0f} kg\n"
                        f"☕ Variety: {escape_markdown(rfq['variety'])}\n"
                        f"⭐ Grade: {escape_markdown(rfq.get('grade', 'Not specified'))}\n"
                        f"🔧 Processing: {escape_markdown(rfq.get('processing_method', 'Any'))}\n"
                        f"📍 Location: {escape_markdown(rfq.get('delivery_location', 'Not specified'))}\n\n"
                        f"🔔 *Broadcasted to {broadcast_count} cooperatives*\n"
                        f"Status: {escape_markdown(rfq['status'])}\n"
                        f"Expires: {escape_markdown(rfq.get('expires_at', 'N/A')[:10] if rfq.get('expires_at') else 'N/A')}\n\n"
                        f"💡 Use /myrfqs to track offers as they come in."
                    ),
                    parse_mode='Markdown'
                )
                
                return {"ok": True, "rfq_created": True, "rfq": rfq}
            else:
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as api_error:
            logger.error(f"Failed to create RFQ: {api_error}")
            await processor.send_notification(
                channel_name='telegram',
                user_id=user_id,
                message=f"❌ Failed to create RFQ: {str(api_error)}\n\nPlease try using /rfq command.",
                send_voice=False  # Error message - text only
            )
            return {"ok": False, "error": str(api_error)}
    
    finally:
        db.close()
