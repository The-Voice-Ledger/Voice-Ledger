"""
Conversation State Manager

Manages conversational state across multiple voice messages for each user.
Stores conversation history, collected entities, and handles timeouts.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from threading import Lock
import re
import re

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
                'turn_count': 0,
                # Reference resolution storage
                'last_batch_results': [],  # List of batch IDs from last search
                'last_rfq_results': [],    # List of RFQ IDs from last search
                'last_search_type': None,  # 'batch', 'rfq', 'offer', etc.
                'last_search_timestamp': None
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
    def store_rag_context(
        user_id: int,
        query: str,
        query_type: str,
        retrieved_context: str,
        sources: list
    ):
        """
        Store RAG query context for follow-up questions.
        
        Args:
            user_id: Database user ID
            query: Original query text
            query_type: Type of query (e.g., 'documentation', 'batch_search')
            retrieved_context: Context retrieved from RAG
            sources: List of source documents/chunks used
        """
        with _conversations_lock:
            # Create conversation if it doesn't exist
            if user_id not in _conversations:
                _conversations[user_id] = {
                    'user_id': user_id,
                    'language': 'en',
                    'intent': None,
                    'context': {},
                    'created_at': datetime.utcnow(),
                    'last_updated': datetime.utcnow()
                }
            
            conversation = _conversations[user_id]
            
            # Store RAG-specific context
            conversation['rag_context'] = {
                'last_query': query,
                'query_type': query_type,
                'retrieved_context': retrieved_context,
                'sources': sources,
                'timestamp': datetime.utcnow().isoformat()
            }
            conversation['last_updated'] = datetime.utcnow()
            
            logger.debug(
                f"Stored RAG context for user {user_id}: "
                f"query='{query[:50]}...', sources={len(sources)}"
            )
    
    @staticmethod
    def get_rag_context(user_id: int) -> dict:
        """
        Get stored RAG context for follow-up processing.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Dict with RAG context or empty dict if none stored
        """
        conversation = ConversationManager.get_conversation(user_id)
        return conversation.get('rag_context', {})
    
    @staticmethod
    def is_follow_up_question(user_id: int, current_query: str) -> bool:
        """
        Detect if current query is a follow-up to previous RAG query.
        
        Uses heuristics:
        - Recent RAG context exists (within timeout)
        - Query contains follow-up indicators
        - Query is short and contextual
        
        Args:
            user_id: Database user ID
            current_query: Current user query
            
        Returns:
            True if this appears to be a follow-up question
        """
        rag_context = ConversationManager.get_rag_context(user_id)
        
        if not rag_context:
            return False
        
        # Check if context is recent (within 5 minutes)
        try:
            context_time = datetime.fromisoformat(rag_context['timestamp'])
            time_elapsed = datetime.utcnow() - context_time
            if time_elapsed > CONVERSATION_TIMEOUT:
                logger.debug(f"RAG context expired for user {user_id}")
                return False
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid RAG context timestamp: {e}")
            return False
        
        # Follow-up indicators (case-insensitive)
        current_lower = current_query.lower().strip()
        
        # Strong follow-up signals (phrases that indicate continuation)
        follow_up_phrases = [
            'show me', 'give me', 'what about', 'how about', 'tell me more',
            'can you', 'explain more', 'show examples', 'more details',
            'more info', 'elaborate', 'expand on',
            # Amharic equivalents
            'ምሳሌ', 'ተጨማሪ', 'በዝርዝር'
        ]
        
        for phrase in follow_up_phrases:
            if phrase in current_lower:
                logger.debug(
                    f"Follow-up detected for user {user_id}: "
                    f"phrase='{phrase}' in query"
                )
                return True
        
        # Special case: "tell me about X" where X is a pronoun (follow-up)
        if current_lower.startswith('tell me about'):
            words_after = current_lower.replace('tell me about', '').strip().split()
            if words_after and words_after[0] in ['it', 'that', 'this', 'them', 'those', 'these']:
                logger.debug(f"Follow-up detected for user {user_id}: tell me about pronoun")
                return True
        
        # Pronouns at the START of query (referring to previous context)
        pronoun_starters = ['it ', 'that ', 'this ', 'they ', 'them ', 'those ', 'these ']
        if any(current_lower.startswith(p) for p in pronoun_starters):
            logger.debug(f"Follow-up detected for user {user_id}: pronoun starter")
            return True
        
        # Single word queries that are contextual
        single_word_followups = ['explain', 'describe', 'examples', 'why', 'how']
        if current_lower in single_word_followups:
            logger.debug(f"Follow-up detected for user {user_id}: single word")
            return True
        
        # Very short queries (<15 chars) that don't start a new topic
        if len(current_query.strip()) < 15:
            # Check if it's NOT starting a completely new topic
            new_topic_indicators = ['what is', 'how do', 'tell me about', 'what are']
            if not any(current_lower.startswith(indicator) for indicator in new_topic_indicators):
                logger.debug(
                    f"Follow-up detected for user {user_id}: "
                    f"short contextual query ({len(current_query)} chars)"
                )
                return True
        
        logger.debug(f"Not a follow-up for user {user_id}")
        return False
    
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
    def store_search_results(
        user_id: int, 
        result_type: str, 
        result_ids: List[str]
    ):
        """
        Store search results for reference resolution.
        
        Allows users to say "the first one", "number 2", etc.
        
        Args:
            user_id: Database user ID
            result_type: Type of results ('batch', 'rfq', 'offer', etc.)
            result_ids: List of IDs in search result order
            
        Example:
            >>> store_search_results(123, 'batch', ['ABC-001', 'ABC-002', 'ABC-003'])
            >>> # User can now say "ship the first one" -> resolves to 'ABC-001'
        """
        # Ensure conversation exists
        conversation = ConversationManager.get_conversation(user_id)
        
        with _conversations_lock:
            # Store results in appropriate field
            if result_type == 'batch':
                conversation['last_batch_results'] = result_ids
            elif result_type == 'rfq':
                conversation['last_rfq_results'] = result_ids
            
            conversation['last_search_type'] = result_type
            conversation['last_search_timestamp'] = datetime.utcnow()
            conversation['last_updated'] = datetime.utcnow()
            
            logger.info(f"Stored {len(result_ids)} {result_type} results for user {user_id}")
    
    @staticmethod
    def get_search_results(
        user_id: int,
        result_type: Optional[str] = None
    ) -> List[str]:
        """
        Get stored search results.
        
        Args:
            user_id: Database user ID
            result_type: Optional filter ('batch', 'rfq'). If None, uses last search type.
            
        Returns:
            List of result IDs
        """
        conversation = ConversationManager.get_conversation(user_id)
        
        if result_type is None:
            result_type = conversation.get('last_search_type')
        
        if result_type == 'batch':
            return conversation.get('last_batch_results', [])
        elif result_type == 'rfq':
            return conversation.get('last_rfq_results', [])
        else:
            return []
    
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


def resolve_reference(
    text: str,
    user_id: int,
    result_type: Optional[str] = None
) -> Optional[str]:
    """
    Resolve reference phrases to actual IDs from stored search results.
    
    Supported phrases:
    - "first one", "1st", "first", "the first" -> index 0
    - "second one", "2nd", "second", "number 2" -> index 1
    - "third one", "3rd", "third", "number 3" -> index 2
    - "last one", "last", "the last" -> last index
    - "number X", "#X" -> index X-1
    
    Args:
        text: User's text containing reference
        user_id: Database user ID
        result_type: Optional result type filter
        
    Returns:
        Resolved ID or None if no match
        
    Example:
        >>> # After search returns ['ABC-001', 'ABC-002', 'ABC-003']
        >>> resolve_reference("ship the first one", user_id=123)
        'ABC-001'
        >>> resolve_reference("pack number 2 and 3", user_id=123)
        'ABC-002'  # Returns first match
    """
    text_lower = text.lower()
    
    # Get stored results
    results = ConversationManager.get_search_results(user_id, result_type)
    
    if not results:
        return None
    
    # Pattern matching for references
    import re
    
    # Ordinal words
    ordinal_map = {
        'first': 0, '1st': 0,
        'second': 1, '2nd': 1,
        'third': 2, '3rd': 2,
        'fourth': 3, '4th': 3,
        'fifth': 4, '5th': 4,
        'sixth': 5, '6th': 5,
        'seventh': 6, '7th': 6,
        'eighth': 7, '8th': 7,
        'ninth': 8, '9th': 8,
        'tenth': 9, '10th': 9,
    }
    
    # Check for ordinal words
    for ordinal, index in ordinal_map.items():
        if ordinal in text_lower:
            if index < len(results):
                logger.info(f"Resolved '{ordinal}' to result {index}: {results[index]}")
                return results[index]
            else:
                logger.warning(f"Reference '{ordinal}' (index {index}) out of range (only {len(results)} results)")
                return None
    
    # Check for "last"
    if 'last' in text_lower and 'last_' not in text_lower:  # Avoid "last_updated" etc.
        logger.info(f"Resolved 'last' to result {len(results)-1}: {results[-1]}")
        return results[-1]
    
    # Check for "number X" or "#X"
    number_match = re.search(r'(?:number|#)\s*(\d+)', text_lower)
    if number_match:
        num = int(number_match.group(1))
        index = num - 1  # Convert to 0-based index
        if 0 <= index < len(results):
            logger.info(f"Resolved 'number {num}' to result {index}: {results[index]}")
            return results[index]
        else:
            logger.warning(f"Reference 'number {num}' (index {index}) out of range (only {len(results)} results)")
            return None
    
    # Check for standalone digits (1, 2, 3) - only if clearly referencing
    # Look for patterns like "batch 2", "option 3", etc.
    digit_match = re.search(r'\b(batch|option|one|item|result)\s+(\d+)\b', text_lower)
    if digit_match:
        num = int(digit_match.group(2))
        index = num - 1
        if 0 <= index < len(results):
            logger.info(f"Resolved '{digit_match.group(1)} {num}' to result {index}: {results[index]}")
            return results[index]
    
    # No match found
    return None


def resolve_entity_references(
    entities: Dict[str, Any],
    user_id: int,
    user_text: str
) -> Dict[str, Any]:
    """
    Resolve reference phrases in entity values.
    
    Checks common entity fields like 'batch_id', 'parent_batch_id', 'rfq_id'
    and attempts to resolve references like "the first one".
    
    Args:
        entities: Extracted entities dict
        user_id: Database user ID
        user_text: Original user text (for context)
        
    Returns:
        Updated entities dict with resolved references
        
    Example:
        >>> entities = {'batch_id': 'the first one', 'quantity': 50}
        >>> resolve_entity_references(entities, user_id=123, user_text="ship the first one")
        {'batch_id': 'ABC-001', 'quantity': 50}
    """
    # Fields that might contain references
    reference_fields = [
        'batch_id',
        'parent_batch_id',
        'container_id',
        'rfq_id',
    ]
    
    for field in reference_fields:
        if field in entities:
            value = entities[field]
            
            # Check if value looks like a reference phrase
            if isinstance(value, str):
                value_lower = value.lower()
                
                # Keywords that suggest a reference
                reference_keywords = [
                    'first', 'second', 'third', 'last',
                    'one', 'number', '#',
                    '1st', '2nd', '3rd',
                ]
                
                is_reference = any(kw in value_lower for kw in reference_keywords)
                
                if is_reference or (len(value) < 20 and '-' not in value):  # Short, non-ID-like
                    # Try to resolve using the original user text for better context
                    resolved_id = resolve_reference(
                        user_text,
                        user_id,
                        result_type='batch'  # Default to batch for now
                    )
                    
                    if resolved_id:
                        logger.info(f"Resolved entity '{field}': '{value}' -> '{resolved_id}'")
                        entities[field] = resolved_id
                    else:
                        logger.warning(f"Could not resolve reference in '{field}': '{value}'")
    
    return entities
