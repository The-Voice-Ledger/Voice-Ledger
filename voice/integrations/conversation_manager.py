"""
Conversation State Manager

Manages conversational state across multiple voice messages for each user.
Stores conversation history, collected entities, and handles timeouts.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# Global conversation store (in-memory)
# In production, consider using Redis for distributed systems
_conversations: Dict[int, Dict[str, Any]] = {}
_conversations_lock = Lock()

# Conversation timeout (5 minutes of inactivity)
CONVERSATION_TIMEOUT = timedelta(minutes=5)


class ConversationManager:
    """
    Manages conversation state for individual users.
    
    Features:
    - Stores conversation history (user/assistant messages)
    - Tracks collected entities
    - Handles conversation timeouts
    - Thread-safe operations
    """
    
    @staticmethod
    def get_conversation(user_id: int) -> Dict[str, Any]:
        """
        Get active conversation for user, or create new one.
        
        Args:
            user_id: Database user ID (not Telegram ID)
            
        Returns:
            Conversation dict with history, entities, and metadata
        """
        with _conversations_lock:
            now = datetime.utcnow()
            
            # Check if conversation exists and is not timed out
            if user_id in _conversations:
                conversation = _conversations[user_id]
                last_updated = conversation['last_updated']
                
                if now - last_updated > CONVERSATION_TIMEOUT:
                    logger.info(f"Conversation for user {user_id} timed out, creating new one")
                    del _conversations[user_id]
                else:
                    return conversation
            
            # Create new conversation
            conversation = {
                'user_id': user_id,
                'language': None,  # Set on first message
                'messages': [],
                'collected_entities': {},
                'intent': None,
                'created_at': now,
                'last_updated': now,
                'turn_count': 0
            }
            
            _conversations[user_id] = conversation
            logger.info(f"Created new conversation for user {user_id}")
            return conversation
    
    @staticmethod
    def add_message(user_id: int, role: str, content: str):
        """
        Add message to conversation history.
        
        Args:
            user_id: Database user ID
            role: 'user' or 'assistant'
            content: Message content
        """
        with _conversations_lock:
            if user_id in _conversations:
                conversation = _conversations[user_id]
                conversation['messages'].append({
                    'role': role,
                    'content': content,
                    'timestamp': datetime.utcnow().isoformat()
                })
                conversation['last_updated'] = datetime.utcnow()
                
                if role == 'user':
                    conversation['turn_count'] += 1
                
                logger.debug(f"Added {role} message to user {user_id} conversation")
    
    @staticmethod
    def get_history(user_id: int) -> List[Dict[str, str]]:
        """
        Get conversation history for AI API calls.
        
        Args:
            user_id: Database user ID
            
        Returns:
            List of message dicts with role and content
        """
        conversation = ConversationManager.get_conversation(user_id)
        return conversation['messages']
    
    @staticmethod
    def update_entities(user_id: int, entities: Dict[str, Any]):
        """
        Update collected entities.
        
        Args:
            user_id: Database user ID
            entities: Dict of entity key-value pairs
        """
        with _conversations_lock:
            if user_id in _conversations:
                conversation = _conversations[user_id]
                conversation['collected_entities'].update(entities)
                conversation['last_updated'] = datetime.utcnow()
                logger.debug(f"Updated entities for user {user_id}: {entities}")
    
    @staticmethod
    def set_intent(user_id: int, intent: str):
        """
        Set conversation intent.
        
        Args:
            user_id: Database user ID
            intent: Intent name (e.g., 'record_commission')
        """
        with _conversations_lock:
            if user_id in _conversations:
                conversation = _conversations[user_id]
                conversation['intent'] = intent
                logger.debug(f"Set intent for user {user_id}: {intent}")
    
    @staticmethod
    def clear_conversation(user_id: int):
        """
        Clear conversation (after successful command execution or manual reset).
        
        Args:
            user_id: Database user ID
        """
        with _conversations_lock:
            if user_id in _conversations:
                del _conversations[user_id]
                logger.info(f"Cleared conversation for user {user_id}")
    
    @staticmethod
    def get_collected_entities(user_id: int) -> Dict[str, Any]:
        """
        Get all collected entities so far.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Dict of collected entities
        """
        conversation = ConversationManager.get_conversation(user_id)
        return conversation['collected_entities']
    
    @staticmethod
    def get_intent(user_id: int) -> Optional[str]:
        """
        Get current intent if set.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Intent string or None
        """
        conversation = ConversationManager.get_conversation(user_id)
        return conversation.get('intent')
    
    @staticmethod
    def get_turn_count(user_id: int) -> int:
        """
        Get number of user turns in conversation.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Number of user messages
        """
        conversation = ConversationManager.get_conversation(user_id)
        return conversation['turn_count']
    
    @staticmethod
    def set_language(user_id: int, language: str):
        """
        Set conversation language.
        
        Args:
            user_id: Database user ID
            language: 'en' or 'am'
        """
        with _conversations_lock:
            if user_id in _conversations:
                conversation = _conversations[user_id]
                conversation['language'] = language
    
    @staticmethod
    def cleanup_old_conversations():
        """
        Cleanup timed-out conversations (call periodically).
        """
        with _conversations_lock:
            now = datetime.utcnow()
            expired = [
                user_id for user_id, conv in _conversations.items()
                if now - conv['last_updated'] > CONVERSATION_TIMEOUT
            ]
            
            for user_id in expired:
                del _conversations[user_id]
                logger.info(f"Cleaned up expired conversation for user {user_id}")
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired conversations")
