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
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from database.models import UserIdentity, Organization, SessionLocal

logger = logging.getLogger(__name__)

# API base URL
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000/api')

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
        
        # Check role
        if user.role != "BUYER":
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
            f"✅ Variety: {variety}\n\n"
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
            f"✅ Grade: {grade}\n\n"
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
            f"✅ Processing: {processing}\n\n"
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
            f"✅ Location: {location}\n\n"
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
    """Handle deadline input (Step 6)"""
    try:
        # Parse date
        deadline = datetime.strptime(text.strip(), '%Y-%m-%d').date()
        
        if deadline <= datetime.now().date():
            return {
                'message': "⚠️ Deadline must be in the future. Please enter a valid date.",
                'keyboard': [[{'text': '❌ Cancel'}]]
            }
        
        session['data']['delivery_deadline'] = deadline.isoformat()
        session['state'] = STATE_CONFIRM
        
        # Show summary
        data = session['data']
        return {
            'message': (
                "📋 *RFQ Summary - Please Confirm*\n\n"
                f"📦 Quantity: {data['quantity_kg']:,.0f} kg\n"
                f"☕ Variety: {data['variety']}\n"
                f"⭐ Grade: {data['grade']}\n"
                f"🌊 Processing: {data.get('processing_method', 'Any')}\n"
                f"📍 Location: {data['delivery_location']}\n"
                f"📅 Deadline: {deadline.strftime('%B %d, %Y')}\n\n"
                "Ready to broadcast to cooperatives?"
            ),
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': '✅ Confirm & Broadcast'}, {'text': '❌ Cancel'}]
            ]
        }
    except ValueError:
        return {
            'message': (
                "⚠️ Invalid date format. Please use YYYY-MM-DD\n"
                "Example: 2025-02-15"
            ),
            'keyboard': [[{'text': '❌ Cancel'}]]
        }


async def handle_confirm_input(user_id: int, text: str, session: Dict) -> Dict[str, Any]:
    """Handle confirmation and create RFQ via API (Step 7)"""
    if text.strip().lower() not in ['✅ confirm & broadcast', 'confirm', 'yes']:
        del rfq_sessions[user_id]
        return {
            'message': "❌ RFQ creation cancelled.",
            'keyboard': [[{'text': '/rfq - Create New RFQ'}]]
        }
    
    # Call API to create RFQ
    try:
        data = session['data']
        api_url = f"{API_BASE_URL}/rfq?user_id={session['user_id']}"
        
        response = requests.post(api_url, json={
            'quantity_kg': data['quantity_kg'],
            'variety': data['variety'],
            'grade': data['grade'],
            'processing_method': data.get('processing_method'),
            'delivery_location': data['delivery_location'],
            'delivery_deadline': data['delivery_deadline']
        }, timeout=10)
        
        if response.status_code == 201:
            rfq = response.json()
            
            # Clean up session
            del rfq_sessions[user_id]
            
            return {
                'message': (
                    "✅ *RFQ Created Successfully!*\n\n"
                    f"📋 RFQ Number: `{rfq['rfq_number']}`\n"
                    f"📦 Quantity: {rfq['quantity_kg']:,.0f} kg\n"
                    f"☕ Variety: {rfq['variety']}\n"
                    f"📍 Location: {rfq['delivery_location']}\n"
                    f"📅 Deadline: {rfq['delivery_deadline']}\n\n"
                    f"🔔 Broadcast to cooperatives: In progress...\n\n"
                    "Use /myrfqs to track offers as they come in."
                ),
                'parse_mode': 'Markdown',
                'keyboard': [
                    [{'text': '/myrfqs - View My RFQs'}],
                    [{'text': '/rfq - Create Another RFQ'}]
                ]
            }
        else:
            error = response.json().get('detail', 'Unknown error')
            return {
                'message': f"❌ Failed to create RFQ: {error}",
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
        response = requests.get(api_url, timeout=10)
        
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
                f"📋 *{rfq['rfq_number']}*\n"
                f"📦 {rfq['quantity_kg']:,.0f} kg {rfq['variety']} {rfq['grade']}\n"
                f"📍 {rfq['delivery_location']}\n"
                f"📅 Deadline: {rfq['delivery_deadline']}\n"
                f"💬 Offers: {rfq.get('offer_count', 0)}\n\n"
            )
            message += rfq_summary
            
            # Add button to make offer
            keyboard.append([
                {'text': f"💰 Offer for {rfq['rfq_number']}", 'callback_data': f"offer_{rfq['id']}"}
            ])
        
        if len(rfqs) > 10:
            message += f"\n_Showing first 10 of {len(rfqs)} RFQs_\n"
        
        keyboard.append([{'text': '/myoffers - View My Offers'}])
        
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
        
        if not user or user.role != "COOPERATIVE_MANAGER":
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only cooperative managers can view their offers."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Fetch offers from API
        api_url = f"{API_BASE_URL}/offers?user_id={user.id}"
        response = requests.get(api_url, timeout=10)
        
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
                'keyboard': [[{'text': '/offers - View Available RFQs'}]]
            }
        
        # Build message
        message = f"📊 *Your Offers ({len(offers)})*\n\n"
        message += f"{user.organization.name if user.organization else 'Your Organization'}\n\n"
        
        for offer in offers:
            status_emoji = {
                'PENDING': '⏳',
                'ACCEPTED': '✅',
                'REJECTED': '❌',
                'WITHDRAWN': '↩️'
            }.get(offer['status'], '📝')
            
            total_value = offer['quantity_offered_kg'] * offer['price_per_kg']
            message += (
                f"{status_emoji} *{offer['offer_number']}*\n"
                f"RFQ: {offer['rfq_id']}\n"
                f"💰 ${offer['price_per_kg']}/kg × {offer['quantity_offered_kg']:,.0f} kg\n"
                f"💵 Total: ${total_value:,.2f}\n"
                f"⏱️ Delivery: {offer['delivery_timeline_days']} days\n"
                f"Status: {offer['status']}\n\n"
            )
        
        return {
            'message': message,
            'parse_mode': 'Markdown',
            'keyboard': [
                [{'text': '/offers - View Available RFQs'}],
                [{'text': '🔄 Refresh'}]
            ]
        }
    
    except Exception as e:
        logger.error(f"Error fetching my offers: {e}")
        return {
            'message': f"❌ Error: {str(e)}"
        }
    finally:
        db.close()


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
        
        if not user or user.role != "BUYER":
            return {
                'message': (
                    "⚠️ *Access Denied*\n\n"
                    "Only buyers can view their RFQs."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Fetch buyer's RFQs from API
        api_url = f"{API_BASE_URL}/rfqs?buyer_id={user.id}"
        response = requests.get(api_url, timeout=10)
        
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
                'keyboard': [[{'text': '/rfq - Create RFQ'}]]
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
                f"{status_emoji} *{rfq['rfq_number']}*\n"
                f"📦 {rfq['quantity_kg']:,.0f} kg {rfq['variety']}\n"
                f"💬 Offers: {rfq.get('offer_count', 0)}\n"
                f"Status: {rfq['status']}\n\n"
            )
            
            if rfq.get('offer_count', 0) > 0:
                keyboard.append([
                    {'text': f"👀 View Offers for {rfq['rfq_number']}", 
                     'callback_data': f"view_offers_{rfq['id']}"}
                ])
        
        keyboard.append([{'text': '/rfq - Create New RFQ'}])
        
        return {
            'message': message,
            'parse_mode': 'Markdown',
            'keyboard': keyboard
        }
    
    except Exception as e:
        logger.error(f"Error fetching my RFQs: {e}")
        return {
            'message': f"❌ Error: {str(e)}"
        }
    finally:
        db.close()
