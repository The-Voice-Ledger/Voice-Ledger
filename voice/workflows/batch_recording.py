"""
Batch Recording Conversational Workflow

Guides users through recording coffee batches with validation and error recovery.
Implements LAB 20: Coffee Operation Conversations.
"""

import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from voice.workflows.state_machine import (
    ConversationWorkflow,
    ConversationState,
    StateManager
)

logger = logging.getLogger(__name__)


class BatchRecordingWorkflow(ConversationWorkflow):
    """Multi-turn conversation for batch recording"""
    
    def __init__(self):
        super().__init__("batch_recording")
    
    async def start(self, user_id: int, initial_message: str = None) -> Dict[str, Any]:
        """
        Start batch recording workflow.
        
        Returns:
            Dict with response message and success flag
        """
        # Initialize state
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.BATCH_RECORDING_WEIGHT,
            workflow_name="batch_recording",
            data={'started_at': datetime.utcnow().isoformat()}
        )
        
        return {
            'success': True,
            'message': "Great! Let's record your coffee batch. 📦\n\nHow much coffee did you harvest? (in kg)"
        }
    
    async def handle_message(
        self,
        user_id: int,
        message: str,
        current_state: ConversationState
    ) -> Dict[str, Any]:
        """
        Handle user message based on current state.
        
        Args:
            user_id: Database user ID
            message: User's message text
            current_state: Current conversation state
            
        Returns:
            Dict with response message and state change info
        """
        # Get current workflow data
        state_data = StateManager.get_user_state(user_id)
        session_data = state_data.get('data', {}) if state_data else {}
        
        # Route to appropriate handler
        if current_state == ConversationState.BATCH_RECORDING_WEIGHT:
            return await self._handle_weight(user_id, message, session_data)
        elif current_state == ConversationState.BATCH_RECORDING_ORIGIN:
            return await self._handle_origin(user_id, message, session_data)
        elif current_state == ConversationState.BATCH_RECORDING_GRADE:
            return await self._handle_grade(user_id, message, session_data)
        elif current_state == ConversationState.BATCH_RECORDING_NOTES:
            return await self._handle_notes(user_id, message, session_data)
        elif current_state == ConversationState.BATCH_RECORDING_CONFIRM:
            return await self._handle_confirmation(user_id, message, session_data)
        else:
            return {
                'success': False,
                'message': "I'm not sure how to help with that. Type 'record batch' to start recording."
            }
    
    async def cancel(self, user_id: int) -> Dict[str, Any]:
        """Cancel batch recording workflow"""
        StateManager.clear_user_state(user_id)
        return {
            'success': True,
            'message': "❌ Batch recording cancelled. Type 'record batch' to start again."
        }
    
    # Private handler methods
    
    async def _handle_weight(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse and validate weight input.
        
        Handles:
        - "50" → 50kg
        - "50kg" → 50kg
        - "50 kilos" → 50kg
        - "100 pounds" → 45.36kg (conversion)
        """
        weight_kg = self._parse_weight(message)
        
        if weight_kg is None or weight_kg <= 0:
            return {
                'success': False,
                'message': "I didn't understand that weight. Please enter a number (e.g., '50' or '50kg').",
                'keep_state': True
            }
        
        if weight_kg > 10000:  # Sanity check: max 10 tons
            return {
                'success': False,
                'message': f"{weight_kg}kg seems very high. Please check and enter again.",
                'keep_state': True
            }
        
        # Save and move to origin
        session_data['weight_kg'] = weight_kg
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.BATCH_RECORDING_ORIGIN,
            workflow_name="batch_recording",
            data=session_data
        )
        
        return {
            'success': True,
            'message': f"✅ {weight_kg}kg recorded.\n\nWhere is this coffee from? (e.g., Sidama, Yirgacheffe, Gedeo)"
        }
    
    async def _handle_origin(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse and validate origin/location input"""
        origin = message.strip()
        
        if len(origin) < 2:
            return {
                'success': False,
                'message': "Please provide a valid location (e.g., Sidama, Yirgacheffe, Gedeo).",
                'keep_state': True
            }
        
        # Save origin and move to grade
        session_data['origin'] = origin
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.BATCH_RECORDING_GRADE,
            workflow_name="batch_recording",
            data=session_data
        )
        
        return {
            'success': True,
            'message': f"✅ Origin '{origin}' recorded.\n\nWhat grade is the coffee? (A, B, or C)"
        }
    
    async def _handle_grade(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse and validate grade input"""
        grade = self._parse_grade(message)
        
        if grade not in ['A', 'B', 'C']:
            return {
                'success': False,
                'message': "Please choose a valid grade: A, B, or C.\n\n"
                          "• Grade A: Premium quality\n"
                          "• Grade B: Standard quality\n"
                          "• Grade C: Lower quality",
                'keep_state': True
            }
        
        # Save grade and move to notes
        session_data['grade'] = grade
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.BATCH_RECORDING_NOTES,
            workflow_name="batch_recording",
            data=session_data
        )
        
        return {
            'success': True,
            'message': f"✅ Grade {grade} recorded.\n\n"
                      f"Any processing notes? (e.g., 'washed process' or say 'skip')"
        }
    
    async def _handle_notes(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Collect optional processing notes"""
        message_lower = message.lower().strip()
        
        # Check if user wants to skip
        if message_lower in ['skip', 'no', 'none', 'nothing', 'na', 'n/a', 'nope']:
            session_data['processing_notes'] = None
        else:
            session_data['processing_notes'] = message
        
        # Show summary and ask for confirmation
        summary = self._format_summary(session_data)
        
        StateManager.set_user_state(
            user_id=user_id,
            state=ConversationState.BATCH_RECORDING_CONFIRM,
            workflow_name="batch_recording",
            data=session_data
        )
        
        return {
            'success': True,
            'message': f"📋 Summary:\n{summary}\n\n"
                      f"Say 'confirm' to create the batch, or\n"
                      f"'change [field]' to correct something (e.g., 'change origin'),\n"
                      f"or 'cancel' to start over."
        }
    
    async def _handle_confirmation(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Final confirmation and batch creation"""
        message_lower = message.lower().strip()
        
        # Handle cancellation
        if 'cancel' in message_lower or message_lower == 'no':
            StateManager.clear_user_state(user_id)
            return {
                'success': True,
                'message': "❌ Batch recording cancelled. Type 'record batch' to start again."
            }
        
        # Handle field corrections (e.g., "change origin", "fix weight", "correct grade")
        # Check for correction keywords
        correction_keywords = ['change', 'fix', 'correct', 'edit', 'update', 'wrong']
        is_correction = any(keyword in message_lower for keyword in correction_keywords)
        
        if is_correction:
            # Detect which field to correct
            if 'weight' in message_lower or 'quantity' in message_lower or 'kg' in message_lower or 'kilo' in message_lower:
                StateManager.set_user_state(
                    user_id=user_id,
                    state=ConversationState.BATCH_RECORDING_WEIGHT,
                    workflow_name="batch_recording",
                    data=session_data
                )
                return {
                    'success': True,
                    'message': f"📝 Current weight: {session_data.get('weight_kg')}kg\n\nWhat's the correct weight?"
                }
            elif 'origin' in message_lower or 'location' in message_lower or 'where' in message_lower or 'from' in message_lower or 'place' in message_lower:
                StateManager.set_user_state(
                    user_id=user_id,
                    state=ConversationState.BATCH_RECORDING_ORIGIN,
                    workflow_name="batch_recording",
                    data=session_data
                )
                return {
                    'success': True,
                    'message': f"📝 Current origin: {session_data.get('origin')}\n\nWhat's the correct origin?"
                }
            elif 'grade' in message_lower or 'quality' in message_lower:
                StateManager.set_user_state(
                    user_id=user_id,
                    state=ConversationState.BATCH_RECORDING_GRADE,
                    workflow_name="batch_recording",
                    data=session_data
                )
                return {
                    'success': True,
                    'message': f"📝 Current grade: {session_data.get('grade')}\n\nWhat's the correct grade? (A, B, C, or UG for ungraded)"
                }
            else:
                # General correction request - show what can be corrected
                return {
                    'success': False,
                    'message': (
                        "What would you like to correct?\n\n"
                        f"• Weight: {session_data.get('weight_kg')}kg\n"
                        f"• Origin: {session_data.get('origin')}\n"
                        f"• Grade: {session_data.get('grade')}\n\n"
                        "Say 'change origin', 'fix weight', or 'correct grade'"
                    ),
                    'keep_state': True
                }
        
        # Handle confirmation
        if 'confirm' in message_lower or 'yes' in message_lower or message_lower == 'y':
            # Create batch in database
            result = await self._create_batch(user_id, session_data)
            
            StateManager.clear_user_state(user_id)
            
            if result['success']:
                # Send QR code with full batch details via Telegram
                # The send_batch_verification_qr function handles the complete message
                try:
                    from voice.telegram.notifier import send_batch_verification_qr
                    
                    telegram_user_id = result.get('telegram_user_id')
                    if telegram_user_id:
                        batch_info = {
                            'batch_id': result['batch_id'],
                            'gtin': result['gtin'],
                            'gln': result['gln'],
                            'variety': result['variety'],
                            'quantity_kg': result['quantity_kg'],
                            'origin': result['origin'],
                            'status': result['status'],
                            'verification_token': result.get('verification_token')
                        }
                        qr_sent = await send_batch_verification_qr(int(telegram_user_id), batch_info)
                        logger.info(f"QR code sent to telegram user {telegram_user_id}: {qr_sent}")
                        
                        # Return success without message since QR function already sent it
                        return {
                            'success': True,
                            'message': None  # No duplicate message needed
                        }
                except Exception as e:
                    logger.error(f"Failed to send QR code: {e}")
                    # Fallback: return text message if QR sending fails
                    return {
                        'success': True,
                        'message': (
                            f"✅ Batch created successfully!\n\n"
                            f"Batch ID: {result['batch_id']}\n"
                            f"GTIN: {result['gtin']}\n\n"
                            f"⚠️ Could not send QR code. Please check with your cooperative."
                        )
                    }
                
                # Fallback if no telegram_user_id
                return {
                    'success': True,
                    'message': (
                        f"✅ Batch created successfully!\n\n"
                        f"Batch ID: {result['batch_id']}\n"
                        f"GTIN: {result['gtin']}"
                    )
                }
            else:
                return {
                    'success': False,
                    'message': f"❌ Error creating batch: {result['error']}\n\n"
                              f"Please try again."
                }
        
        # Didn't understand confirmation
        return {
            'success': False,
            'message': "Please type 'confirm' to create the batch or 'cancel' to abort.",
            'keep_state': True
        }
    
    # Helper methods
    
    def _parse_weight(self, text: str) -> Optional[float]:
        """
        Parse weight from various input formats.
        
        Examples:
        - "50" → 50.0
        - "50kg" → 50.0
        - "50 kilograms" → 50.0
        - "100 pounds" → 45.36
        - "50.5" → 50.5
        - "half quintal" → 50.0
        """
        text = text.lower().strip()
        
        # Remove common words
        text = text.replace('about', '').replace('approximately', '').strip()
        
        # Check for quintals (1 quintal = 100 kg in Ethiopia)
        if 'quintal' in text:
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                quintals = float(match.group(1))
                return quintals * 100.0
        
        # Check for pounds (convert to kg)
        if 'pound' in text or 'lb' in text:
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                pounds = float(match.group(1))
                return pounds * 0.453592  # pounds to kg
        
        # Extract number (handles kg, kilos, kilograms)
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return float(match.group(1))
        
        return None
    
    def _parse_grade(self, text: str) -> Optional[str]:
        """
        Parse grade from input.
        
        Examples:
        - "A" → "A"
        - "Grade A" → "A"
        - "a" → "A"
        - "premium" → "A"
        """
        text = text.upper().strip()
        
        # Direct grade letter
        if text in ['A', 'B', 'C']:
            return text
        
        # "Grade X" format
        match = re.search(r'GRADE\s*([ABC])', text)
        if match:
            return match.group(1)
        
        # Extract single letter
        match = re.search(r'\b([ABC])\b', text)
        if match:
            return match.group(1)
        
        # Quality keywords
        if 'premium' in text.lower() or 'best' in text.lower() or 'excellent' in text.lower():
            return 'A'
        if 'standard' in text.lower() or 'medium' in text.lower() or 'good' in text.lower():
            return 'B'
        if 'lower' in text.lower() or 'basic' in text.lower() or 'low' in text.lower():
            return 'C'
        
        return None
    
    def _format_summary(self, session_data: Dict[str, Any]) -> str:
        """Format batch summary for confirmation"""
        weight = session_data.get('weight_kg', 0)
        origin = session_data.get('origin', 'Unknown')
        grade = session_data.get('grade', '?')
        notes = session_data.get('processing_notes')
        
        summary = f"• Weight: {weight}kg\n"
        summary += f"• Origin: {origin}\n"
        summary += f"• Grade: {grade}\n"
        if notes:
            summary += f"• Notes: {notes}\n"
        else:
            summary += f"• Notes: (none)\n"
        
        return summary
    
    async def _create_batch(
        self,
        user_id: int,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create batch in database using the REAL batch creation logic.
        
        Returns:
            Dict with success flag, batch_id, verification_token, and other batch details
        """
        try:
            from database.models import SessionLocal, UserIdentity
            from datetime import datetime
            from voice.command_integration import handle_record_commission
            
            db = SessionLocal()
            
            try:
                # Get user identity - user_id might be telegram_user_id or database id
                # Try both lookups
                user_identity = db.query(UserIdentity).filter(UserIdentity.id == user_id).first()
                if not user_identity:
                    # Try by telegram_user_id
                    user_identity = db.query(UserIdentity).filter(UserIdentity.telegram_user_id == str(user_id)).first()
                
                if not user_identity:
                    logger.error(f"User {user_id} not found in database. User needs to register first.")
                    return {
                        'success': False, 
                        'error': 'User not found. Please register first via /start command in Telegram.'
                    }
                
                user_name = f"{user_identity.telegram_first_name or ''} {user_identity.telegram_last_name or ''}".strip() or user_identity.telegram_username or f"User {user_identity.id}"
                logger.info(f"Found user: {user_name} (ID: {user_identity.id}, Telegram: {user_identity.telegram_user_id})")
                
                # Build entities dict matching the old system's format
                entities = {
                    'quantity': session_data['weight_kg'],
                    'unit': 'kg',
                    'product': 'Arabica Coffee',  # Default (could be enhanced to ask user)
                    'origin': session_data.get('origin', 'Unknown'),  # Use collected origin
                    # Could add grade to batch_data if we enhance the model
                }
                
                # Use the REAL batch creation handler
                message, result = handle_record_commission(
                    db=db,
                    entities=entities,
                    user_id=user_identity.id,  # Use database ID, not telegram_user_id
                    user_did=user_identity.did
                )
                
                logger.info(f"Batch created for user {user_id}: {result['batch_id']}")
                
                # Return in the format expected by confirmation handler
                return {
                    'success': True,
                    'batch_id': result['batch_id'],
                    'gtin': result['gtin'],
                    'gln': result['gln'],
                    'quantity_kg': result['quantity_kg'],
                    'variety': result['variety'],
                    'origin': result['origin'],
                    'status': result['status'],
                    'verification_token': result.get('verification_token'),
                    'verification_expires_at': result.get('verification_expires_at'),
                    'blockchain_hash': result['epcis_event']['event_hash'] if result.get('epcis_event') else None,
                    'ipfs_cid': result['epcis_event']['ipfs_cid'] if result.get('epcis_event') else None,
                    'telegram_user_id': user_identity.telegram_user_id  # Add telegram_user_id for QR sending
                }
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error creating batch: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
