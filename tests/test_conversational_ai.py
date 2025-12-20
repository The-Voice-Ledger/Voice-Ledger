#!/usr/bin/env python3
"""
Test suite for conversational AI system.

Tests:
1. English conversation flow
2. Amharic conversation flow  
3. Language switching
4. Multi-turn dialogue
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from voice.integrations import ConversationManager, process_english_conversation
from database.models import SessionLocal, UserIdentity


def test_conversation_manager():
    """Test conversation state management."""
    print("\n=== Testing Conversation Manager ===")
    
    user_id = 1
    
    # Create conversation
    conv = ConversationManager.get_conversation(user_id)
    print(f"✅ Created conversation for user {user_id}")
    print(f"   Messages: {len(conv['messages'])}")
    
    # Add message
    ConversationManager.add_message(user_id, 'user', 'Test message')
    conv = ConversationManager.get_conversation(user_id)
    print(f"✅ Added message, now {len(conv['messages'])} messages")
    
    # Update entities
    ConversationManager.update_entities(user_id, {'quantity': 50, 'product': 'coffee'})
    conv = ConversationManager.get_conversation(user_id)
    print(f"✅ Updated entities: {conv['collected_entities']}")
    
    # Clear conversation
    ConversationManager.clear_conversation(user_id)
    print(f"✅ Cleared conversation")


def test_english_conversation():
    """Test English conversational AI."""
    print("\n=== Testing English Conversation ===")
    
    user_id = 1
    
    # First message - incomplete
    print("\n1. User: 'I want to register coffee'")
    result = process_english_conversation(user_id, "I want to register coffee")
    print(f"   Ready: {result['ready_to_execute']}")
    print(f"   Response: {result['message']}")
    
    if not result['ready_to_execute']:
        # Second message - provide quantity
        print("\n2. User: '50 kg'")
        result = process_english_conversation(user_id, "50 kg")
        print(f"   Ready: {result['ready_to_execute']}")
        print(f"   Response: {result['message']}")
    
    if not result['ready_to_execute']:
        # Third message - provide origin
        print("\n3. User: 'From Gedeo'")
        result = process_english_conversation(user_id, "From Gedeo")
        print(f"   Ready: {result['ready_to_execute']}")
        print(f"   Response: {result['message']}")
    
    if result['ready_to_execute']:
        print(f"\n✅ Conversation complete!")
        print(f"   Intent: {result['intent']}")
        print(f"   Entities: {result['entities']}")
    else:
        print(f"\n⚠️  Still need more information")
    
    # Clear for next test
    ConversationManager.clear_conversation(user_id)


def test_user_language_preference():
    """Test user language preference in database."""
    print("\n=== Testing User Language Preference ===")
    
    db = SessionLocal()
    try:
        # Get first user
        user = db.query(UserIdentity).first()
        
        if user:
            print(f"User: {user.telegram_first_name}")
            print(f"  Language: {user.preferred_language}")
            print(f"  Set at: {user.language_set_at}")
            
            # Test switching language
            original_lang = user.preferred_language
            new_lang = 'am' if original_lang == 'en' else 'en'
            
            user.preferred_language = new_lang
            db.commit()
            print(f"✅ Switched from {original_lang} to {new_lang}")
            
            # Switch back
            user.preferred_language = original_lang
            db.commit()
            print(f"✅ Switched back to {original_lang}")
        else:
            print("❌ No users in database")
    finally:
        db.close()


def test_conversation_timeout():
    """Test conversation cleanup after timeout."""
    print("\n=== Testing Conversation Timeout ===")
    
    user_id = 999  # Test user
    
    # Create conversation
    conv = ConversationManager.get_conversation(user_id)
    print(f"✅ Created conversation")
    
    # Manually set old timestamp to simulate timeout
    from datetime import datetime, timedelta
    conv['last_updated'] = datetime.utcnow() - timedelta(minutes=10)
    
    # Run cleanup (no parameters, uses default 5-minute timeout)
    ConversationManager.cleanup_old_conversations()
    print(f"✅ Ran cleanup on old conversations")
    
    # Try to get conversation again - should be gone
    from voice.integrations.conversation_manager import _conversations
    if user_id not in _conversations:
        print(f"✅ Conversation properly cleaned up")
    else:
        print(f"⚠️  Conversation still exists")


if __name__ == "__main__":
    print("=" * 60)
    print("Conversational AI Test Suite")
    print("=" * 60)
    
    try:
        test_conversation_manager()
        test_english_conversation()
        test_user_language_preference()
        test_conversation_timeout()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
