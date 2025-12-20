"""
Conversational AI integrations for Voice Ledger.

This package provides conversational AI interfaces for both English and Amharic users.
"""

from .conversation_manager import ConversationManager
from .english_conversation import process_english_conversation
from .amharic_conversation import process_amharic_conversation

__all__ = [
    'ConversationManager',
    'process_english_conversation',
    'process_amharic_conversation',
]
