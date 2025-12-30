"""
Unified State Machine Foundation

Provides a state machine architecture for managing multi-turn conversational
workflows. All workflow implementations (RAG queries, batch recording, 
shipment tracking, marketplace) use this unified foundation.

Architecture:
    ConversationState (enum) - All possible conversation states
    StateManager (class) - Redis-backed state persistence
    ConversationWorkflow (base class) - Abstract workflow implementation
"""

import logging
import json
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis

logger = logging.getLogger(__name__)

# Redis connection (reuse existing connection from session_manager)
try:
    from voice.integrations.session_manager import redis_client
    _redis = redis_client
    logger.info("Using existing Redis connection from session_manager")
except ImportError:
    # Fallback: create new connection
    import os
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    _redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    logger.info(f"Created new Redis connection to {redis_host}:{redis_port}")


class ConversationState(Enum):
    """
    All possible conversation states across all workflows.
    
    State naming convention: <WORKFLOW>_<STEP>
    
    Workflows:
        - RAG: Documentation queries with multi-turn context
        - BATCH: Batch recording workflow
        - SHIPMENT: Shipment tracking workflow
        - MARKETPLACE: RFQ creation and offer management
    """
    # Idle state (no active workflow)
    IDLE = "idle"
    
    # RAG Documentation Query States
    DOCUMENTATION_QUERY = "documentation_query"
    DOCUMENTATION_FOLLOWUP = "documentation_followup"
    
    # Batch Recording States
    BATCH_RECORDING_START = "batch_recording_start"
    BATCH_RECORDING_WEIGHT = "batch_recording_weight"
    BATCH_RECORDING_ORIGIN = "batch_recording_origin"
    BATCH_RECORDING_GRADE = "batch_recording_grade"
    BATCH_RECORDING_NOTES = "batch_recording_notes"
    BATCH_RECORDING_CONFIRM = "batch_recording_confirm"
    
    # Shipment Tracking States
    SHIPMENT_TRACKING_LIST = "shipment_tracking_list"
    SHIPMENT_TRACKING_DETAIL = "shipment_tracking_detail"
    SHIPMENT_TRACKING_FOLLOWUP = "shipment_tracking_followup"
    
    # Marketplace RFQ States
    MARKETPLACE_RFQ_START = "marketplace_rfq_start"
    MARKETPLACE_RFQ_COFFEE_TYPE = "marketplace_rfq_coffee_type"
    MARKETPLACE_RFQ_QUANTITY = "marketplace_rfq_quantity"
    MARKETPLACE_RFQ_QUALITY = "marketplace_rfq_quality"
    MARKETPLACE_RFQ_PRICE = "marketplace_rfq_price"
    MARKETPLACE_RFQ_DELIVERY = "marketplace_rfq_delivery"
    MARKETPLACE_RFQ_CONFIRM = "marketplace_rfq_confirm"
    
    # Marketplace Offer States
    MARKETPLACE_OFFER_BROWSE = "marketplace_offer_browse"
    MARKETPLACE_OFFER_DETAIL = "marketplace_offer_detail"
    MARKETPLACE_OFFER_CREATE = "marketplace_offer_create"


class StateManager:
    """
    Redis-backed state persistence for conversations.
    
    Stores conversation state with TTL expiration to prevent stale data.
    Each user has one active state at a time (stored in Redis with key: conv:state:{user_id}).
    
    State Structure:
        {
            'state': 'batch_recording_weight',
            'workflow': 'batch_recording',
            'data': {'variety': 'Arabica', 'origin': 'Sidama'},
            'created_at': '2025-12-29T10:30:00',
            'last_updated': '2025-12-29T10:31:00'
        }
    """
    
    STATE_PREFIX = "conv:state:"
    DEFAULT_TTL = 300  # 5 minutes in seconds
    
    @staticmethod
    def get_user_state(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current conversation state for user.
        
        Args:
            user_id: Database user ID (not Telegram ID)
            
        Returns:
            State dict or None if no active conversation
        """
        key = f"{StateManager.STATE_PREFIX}{user_id}"
        
        try:
            state_json = _redis.get(key)
            if not state_json:
                return None
            
            state_data = json.loads(state_json)
            
            # Refresh TTL on access
            _redis.expire(key, StateManager.DEFAULT_TTL)
            
            logger.debug(f"Retrieved state for user {user_id}: {state_data.get('state')}")
            return state_data
            
        except Exception as e:
            logger.error(f"Error getting state for user {user_id}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def set_user_state(
        user_id: int,
        state: ConversationState,
        workflow_name: str,
        data: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set conversation state for user.
        
        Args:
            user_id: Database user ID
            state: ConversationState enum value
            workflow_name: Name of workflow (e.g., 'batch_recording', 'rag_query')
            data: Additional workflow data to store
            ttl: Time-to-live in seconds (default: 300)
            
        Returns:
            True if successful, False otherwise
        """
        key = f"{StateManager.STATE_PREFIX}{user_id}"
        ttl = ttl or StateManager.DEFAULT_TTL
        
        now = datetime.utcnow().isoformat()
        
        # Get existing state to preserve created_at
        existing_state = StateManager.get_user_state(user_id)
        created_at = existing_state.get('created_at', now) if existing_state else now
        
        state_data = {
            'state': state.value,
            'workflow': workflow_name,
            'data': data or {},
            'created_at': created_at,
            'last_updated': now
        }
        
        try:
            state_json = json.dumps(state_data)
            _redis.setex(key, ttl, state_json)
            
            logger.info(
                f"Set state for user {user_id}: {state.value} "
                f"(workflow: {workflow_name}, TTL: {ttl}s)"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error setting state for user {user_id}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def update_workflow_data(
        user_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update workflow data without changing state.
        
        Args:
            user_id: Database user ID
            updates: Dict of key-value pairs to update in data
            
        Returns:
            True if successful, False otherwise
        """
        state = StateManager.get_user_state(user_id)
        if not state:
            logger.warning(f"No active state for user {user_id}, cannot update data")
            return False
        
        # Merge updates into existing data
        state['data'].update(updates)
        state['last_updated'] = datetime.utcnow().isoformat()
        
        # Parse state enum
        try:
            state_enum = ConversationState(state['state'])
        except ValueError:
            logger.error(f"Invalid state value: {state['state']}")
            return False
        
        # Re-save state with updated data
        return StateManager.set_user_state(
            user_id=user_id,
            state=state_enum,
            workflow_name=state['workflow'],
            data=state['data']
        )
    
    @staticmethod
    def clear_user_state(user_id: int) -> bool:
        """
        Clear conversation state (return to IDLE).
        
        Args:
            user_id: Database user ID
            
        Returns:
            True if successful, False otherwise
        """
        key = f"{StateManager.STATE_PREFIX}{user_id}"
        
        try:
            _redis.delete(key)
            logger.info(f"Cleared state for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing state for user {user_id}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def is_in_workflow(user_id: int, workflow_name: str) -> bool:
        """
        Check if user is currently in a specific workflow.
        
        Args:
            user_id: Database user ID
            workflow_name: Workflow to check (e.g., 'batch_recording')
            
        Returns:
            True if user is in the specified workflow
        """
        state = StateManager.get_user_state(user_id)
        if not state:
            return False
        
        return state.get('workflow') == workflow_name


class ConversationWorkflow:
    """
    Abstract base class for conversational workflows.
    
    All multi-turn workflows inherit from this class and implement:
        - start(): Initialize workflow and set initial state
        - handle_message(): Process user input based on current state
        - cancel(): Cancel workflow and clean up
    
    Example workflows:
        - BatchRecordingWorkflow: Guide user through batch creation
        - ShipmentTrackingWorkflow: Help user track shipments
        - MarketplaceRFQWorkflow: Create RFQ through conversation
    """
    
    def __init__(self, workflow_name: str):
        """
        Initialize workflow.
        
        Args:
            workflow_name: Unique workflow identifier
        """
        self.workflow_name = workflow_name
        self.logger = logging.getLogger(f"{__name__}.{workflow_name}")
    
    async def start(self, user_id: int, initial_message: str) -> Dict[str, Any]:
        """
        Start the workflow.
        
        Args:
            user_id: Database user ID
            initial_message: User's initial message that triggered workflow
            
        Returns:
            Response dict with 'message' and optional metadata
        """
        raise NotImplementedError("Subclasses must implement start()")
    
    async def handle_message(
        self,
        user_id: int,
        message: str,
        current_state: ConversationState,
        workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle user message based on current state.
        
        Args:
            user_id: Database user ID
            message: User's message
            current_state: Current conversation state (enum)
            workflow_data: Current workflow data from StateManager
            
        Returns:
            Response dict with:
                - 'message': Response to send to user
                - 'next_state': Next ConversationState (or None to stay in current)
                - 'data_updates': Dict of updates to workflow_data
                - 'complete': True if workflow is complete
        """
        raise NotImplementedError("Subclasses must implement handle_message()")
    
    async def cancel(self, user_id: int) -> Dict[str, Any]:
        """
        Cancel the workflow.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Response dict with cancellation message
        """
        StateManager.clear_user_state(user_id)
        self.logger.info(f"Workflow {self.workflow_name} cancelled for user {user_id}")
        
        return {
            'message': f"❌ {self.workflow_name.replace('_', ' ').title()} cancelled.",
            'complete': True
        }
    
    def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current workflow state for user.
        
        Args:
            user_id: Database user ID
            
        Returns:
            State dict or None
        """
        return StateManager.get_user_state(user_id)
    
    def set_state(
        self,
        user_id: int,
        state: ConversationState,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Set workflow state.
        
        Args:
            user_id: Database user ID
            state: ConversationState enum
            data: Workflow data
            
        Returns:
            True if successful
        """
        return StateManager.set_user_state(
            user_id=user_id,
            state=state,
            workflow_name=self.workflow_name,
            data=data
        )
    
    def update_data(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update workflow data.
        
        Args:
            user_id: Database user ID
            updates: Data updates
            
        Returns:
            True if successful
        """
        return StateManager.update_workflow_data(user_id, updates)


# Helper Functions

def get_current_workflow(user_id: int) -> Optional[str]:
    """
    Get name of currently active workflow for user.
    
    Args:
        user_id: Database user ID
        
    Returns:
        Workflow name or None if no active workflow
    """
    state = StateManager.get_user_state(user_id)
    return state.get('workflow') if state else None


def is_idle(user_id: int) -> bool:
    """
    Check if user has no active workflow.
    
    Args:
        user_id: Database user ID
        
    Returns:
        True if user is idle (no active conversation)
    """
    state = StateManager.get_user_state(user_id)
    if not state:
        return True
    
    return state.get('state') == ConversationState.IDLE.value
