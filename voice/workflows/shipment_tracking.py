"""
Shipment Tracking Conversational Workflow

Interactive shipment status queries with follow-up actions.
Implements LAB 20: Coffee Operation Conversations - Part 2.
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from voice.workflows.state_machine import (
    ConversationWorkflow,
    ConversationState,
    StateManager
)

logger = logging.getLogger(__name__)


class ShipmentTrackingWorkflow(ConversationWorkflow):
    """Multi-turn conversation for shipment tracking"""
    
    def __init__(self):
        super().__init__("shipment_tracking")
    
    async def start(self, user_id: int, initial_message: str = None) -> Dict[str, Any]:
        """
        Start shipment tracking workflow - list user's shipments.
        
        Returns:
            Dict with response message and success flag
        """
        # Get user's shipments
        shipments = await self._get_user_shipments(user_id)
        
        if not shipments:
            return {
                'success': True,
                'message': "You don't have any active shipments yet. 📦\n\n"
                          "Once you ship a batch, you can track it here."
            }
        
        # Format shipment list
        shipment_list = self._format_shipment_list(shipments)
        
        # Store shipments in state for selection
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.SHIPMENT_TRACKING_LIST,
            workflow_name="shipment_tracking",
            data={
                'shipments': [s['id'] for s in shipments],
                'shipment_details': {s['id']: s for s in shipments}
            }
        )
        
        return {
            'success': True,
            'message': f"📦 Your Active Shipments:\n\n{shipment_list}\n\n"
                      f"Which shipment would you like to check? (Enter number or ID)"
        }
    
    async def handle_message(
        self,
        user_id: int,
        message: str,
        current_state: ConversationState
    ) -> Dict[str, Any]:
        """Handle user message based on current state"""
        state_data = StateManager.get_user_state(user_id)
        session_data = state_data.get('data', {}) if state_data else {}
        
        if current_state == ConversationState.SHIPMENT_TRACKING_LIST:
            return await self._handle_selection(user_id, message, session_data)
        elif current_state == ConversationState.SHIPMENT_TRACKING_DETAIL:
            return await self._handle_followup(user_id, message, session_data)
        else:
            return {
                'success': False,
                'message': "I'm not sure how to help with that. Type 'track shipment' to check your shipments."
            }
    
    async def cancel(self, user_id: int) -> Dict[str, Any]:
        """Cancel shipment tracking workflow"""
        StateManager.clear_user_state(user_id)
        return {
            'success': True,
            'message': "Shipment tracking closed. Type 'track shipment' to check again."
        }
    
    # Private handler methods
    
    async def _handle_selection(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle shipment selection from list"""
        shipments = session_data.get('shipments', [])
        shipment_details = session_data.get('shipment_details', {})
        
        if not shipments:
            return {
                'success': False,
                'message': "No shipments available. Type 'track shipment' to refresh."
            }
        
        # Parse selection (number, ordinal, or ID)
        selection = self._parse_shipment_selection(message, shipments)
        
        if selection is None:
            return {
                'success': False,
                'message': f"Please select a shipment by number (1-{len(shipments)}) or ID.",
                'keep_state': True
            }
        
        # Get selected shipment
        shipment_id = shipments[selection] if isinstance(selection, int) and selection < len(shipments) else selection
        
        # Try both int and string keys (JSON serialization converts int keys to strings)
        shipment = shipment_details.get(shipment_id)
        if not shipment and isinstance(shipment_id, int):
            shipment = shipment_details.get(str(shipment_id))
        
        if not shipment:
            return {
                'success': False,
                'message': "Shipment not found. Please try again.",
                'keep_state': True
            }
        
        # Show shipment details
        details = self._format_shipment_details(shipment)
        
        # Update state to detail view
        session_data['selected_shipment'] = shipment_id
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.SHIPMENT_TRACKING_DETAIL,
            workflow_name="shipment_tracking",
            data=session_data
        )
        
        return {
            'success': True,
            'message': f"{details}\n\nType 'back' to see all shipments, or ask me anything about this shipment."
        }
    
    async def _handle_followup(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle follow-up actions or questions"""
        message_lower = message.lower().strip()
        
        # Handle going back to list
        if message_lower in ['back', 'list', 'show all', 'others']:
            return await self.start(user_id)
        
        # Handle exit
        if message_lower in ['done', 'exit', 'close', 'bye']:
            return await self.cancel(user_id)
        
        # Get current shipment
        shipment_id = session_data.get('selected_shipment')
        shipment_details = session_data.get('shipment_details', {})
        shipment = shipment_details.get(shipment_id)
        
        if not shipment:
            return await self.cancel(user_id)
        
        # Handle specific questions
        if 'where' in message_lower or 'location' in message_lower:
            location = shipment.get('current_location', 'Unknown')
            return {
                'success': True,
                'message': f"📍 Current location: {location}\n\nAnything else?"
            }
        
        if 'when' in message_lower or 'arrive' in message_lower or 'eta' in message_lower:
            eta = shipment.get('estimated_arrival', 'Not available')
            return {
                'success': True,
                'message': f"⏰ Estimated arrival: {eta}\n\nAnything else?"
            }
        
        if 'status' in message_lower:
            status = shipment.get('status', 'Unknown')
            return {
                'success': True,
                'message': f"📊 Status: {status}\n\nAnything else?"
            }
        
        # Default response - show full details again
        details = self._format_shipment_details(shipment)
        return {
            'success': True,
            'message': f"{details}\n\nType 'back' for all shipments, or ask me anything."
        }
    
    # Helper methods
    
    async def _get_user_shipments(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get active shipments for user from database.
        
        Returns:
            List of shipment dicts with id, tracking_id, status, location, etc.
        """
        try:
            from database.models import SessionLocal
            from database.crud import get_user_shipments
            
            db = SessionLocal()
            try:
                # Query real shipment events from database
                shipments = get_user_shipments(db, user_id)
                
                if not shipments:
                    logger.info(f"No shipments found for user {user_id}")
                    return []
                
                logger.info(f"Found {len(shipments)} shipment(s) for user {user_id}")
                return shipments
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in _get_user_shipments: {e}", exc_info=True)
            return []
    
    def _format_shipment_list(self, shipments: List[Dict[str, Any]]) -> str:
        """Format list of shipments for display"""
        lines = []
        for i, s in enumerate(shipments, 1):
            display_id = s.get('tracking_id', s.get('batch_id', 'Unknown'))
            destination = s.get('destination', 'Unknown')
            status = s.get('status', 'Unknown')
            location = s.get('current_location', 'Unknown')
            
            lines.append(
                f"{i}. {display_id} → {destination}\n"
                f"   Status: {status} | {location}"
            )
        return "\n\n".join(lines)
    
    def _format_shipment_details(self, shipment: Dict[str, Any]) -> str:
        """Format detailed shipment information"""
        tracking_id = shipment.get('tracking_id', shipment.get('batch_id', 'Unknown'))
        batch_id = shipment.get('batch_id', 'N/A')
        gtin = shipment.get('gtin', 'N/A')
        quantity = shipment.get('quantity_kg', 'N/A')
        variety = shipment.get('variety', 'N/A')
        status = shipment.get('status', 'Unknown')
        location = shipment.get('current_location', 'Unknown')
        destination = shipment.get('destination', 'Unknown')
        carrier = shipment.get('carrier', 'N/A')
        tracking_number = shipment.get('tracking_number', 'N/A')
        event_time = shipment.get('event_time', 'N/A')
        created = shipment.get('created_at', 'N/A')
        
        details = f"📦 <b>Shipment Details</b>\n\n"
        details += f"🆔 <b>Tracking:</b> {tracking_id}\n"
        details += f"📦 <b>Batch:</b> {batch_id}\n"
        
        if gtin != 'N/A':
            details += f"🏷️ <b>GTIN:</b> {gtin}\n"
        
        details += f"⚖️ <b>Quantity:</b> {quantity}kg\n"
        
        if variety != 'N/A':
            details += f"☕ <b>Variety:</b> {variety}\n"
        
        details += f"📍 <b>Status:</b> {status}\n"
        details += f"📍 <b>Current Location:</b> {location}\n"
        details += f"🎯 <b>Destination:</b> {destination}\n"
        
        if carrier != 'N/A':
            details += f"🚚 <b>Carrier:</b> {carrier}\n"
        
        if tracking_number != 'N/A':
            details += f"🔢 <b>Tracking #:</b> {tracking_number}\n"
        
        if event_time != 'N/A':
            details += f"⏰ <b>Shipped:</b> {event_time[:10]}\n"
        else:
            details += f"📅 <b>Created:</b> {created}\n"
        
        return details
    
    def _parse_shipment_selection(
        self,
        message: str,
        shipments: List[int]
    ) -> Optional[int]:
        """
        Parse user's shipment selection.
        
        Handles:
        - "1" → index 0
        - "first" / "first one" → index 0
        - "second" / "2nd" → index 1
        - "VL-SHIP-0001" → shipment ID 1
        """
        message_lower = message.lower().strip()
        
        # Direct number
        if message_lower.isdigit():
            num = int(message_lower)
            if 1 <= num <= len(shipments):
                return num - 1  # Convert to 0-indexed
        
        # Ordinal words
        ordinals = {
            'first': 0, '1st': 0,
            'second': 1, '2nd': 1,
            'third': 2, '3rd': 2,
            'fourth': 3, '4th': 3,
            'fifth': 4, '5th': 4
        }
        
        for word, index in ordinals.items():
            if word in message_lower and index < len(shipments):
                return index
        
        # Shipment ID pattern (VL-SHIP-XXXX)
        match = re.search(r'VL-SHIP-(\d+)', message, re.IGNORECASE)
        if match:
            shipment_num = int(match.group(1))
            if shipment_num in shipments:
                return shipments.index(shipment_num)
        
        return None
