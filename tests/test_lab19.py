#!/usr/bin/env python3
"""
Test script for LAB 19: Enhanced RAG Conversations & State Foundation

Tests:
1. State machine - state persistence and transitions
2. ConversationManager RAG extensions - context storage and follow-up detection
3. MultiTurnRAG - new queries, follow-ups, and context reuse
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice.workflows.state_machine import ConversationState, StateManager
from voice.integrations.conversation_manager import ConversationManager
from voice.rag.multi_turn_rag import MultiTurnRAG


async def test_state_machine():
    """Test StateManager state persistence and transitions."""
    print("\n" + "="*60)
    print("TEST 1: State Machine")
    print("="*60)
    
    state_manager = StateManager()
    test_user_id = 999999  # Test user
    
    # Test 1: Initial state should be None (no active conversation)
    state_data = state_manager.get_user_state(test_user_id)
    assert state_data is None, f"Expected None for new user, got {state_data}"
    print("✅ Initial state is None (no active conversation)")
    
    # Test 2: Set state to DOCUMENTATION_QUERY
    state_manager.set_user_state(
        test_user_id,
        ConversationState.DOCUMENTATION_QUERY,
        workflow_name="rag_query",
        data={"query": "What is EPCIS?", "timestamp": "2024-01-01"}
    )
    state_data = state_manager.get_user_state(test_user_id)
    assert state_data is not None
    assert state_data['state'] == ConversationState.DOCUMENTATION_QUERY.value
    print("✅ State transition to DOCUMENTATION_QUERY successful")
    
    # Test 3: Retrieve workflow data
    assert state_data['data'].get("query") == "What is EPCIS?"
    print(f"✅ Workflow data retrieved: {state_data['data']}")
    
    # Test 4: Update workflow data
    state_manager.update_workflow_data(test_user_id, {"answer_count": 1})
    state_data = state_manager.get_user_state(test_user_id)
    assert state_data['data'].get("answer_count") == 1
    print(f"✅ Workflow data updated: {state_data['data']}")
    
    # Test 5: Clear state
    state_manager.clear_user_state(test_user_id)
    state_data = state_manager.get_user_state(test_user_id)
    assert state_data is None
    print("✅ State cleared back to None")
    
    print("\n✅ State Machine tests passed!\n")


async def test_conversation_manager_rag():
    """Test ConversationManager RAG context storage and follow-up detection."""
    print("\n" + "="*60)
    print("TEST 2: ConversationManager RAG Extensions")
    print("="*60)
    
    conv_manager = ConversationManager()
    test_user_id = 999998
    
    # Test 1: Store RAG context
    conv_manager.store_rag_context(
        user_id=test_user_id,
        query="What are EPCIS events?",
        query_type="documentation",
        retrieved_context="EPCIS events are...",
        sources=[{"file": "EPCIS_GUIDE.md", "score": 0.95}]
    )
    print("✅ RAG context stored")
    
    # Test 2: Retrieve RAG context
    context = conv_manager.get_rag_context(test_user_id)
    assert context is not None
    assert context['last_query'] == "What are EPCIS events?"
    print(f"✅ RAG context retrieved: {context['last_query']}")
    
    # Test 3: Follow-up detection - positive cases
    follow_up_queries = [
        "show me examples",
        "explain more",
        "tell me about it",
        "what about that",
        "more info"
    ]
    
    for query in follow_up_queries:
        is_followup = conv_manager.is_follow_up_question(test_user_id, query)
        assert is_followup, f"Expected '{query}' to be detected as follow-up"
        print(f"✅ Follow-up detected: '{query}'")
    
    # Test 4: Follow-up detection - negative cases
    new_queries = [
        "What is blockchain?",
        "How do I register?",
        "Tell me about coffee shipments"
    ]
    
    for query in new_queries:
        is_followup = conv_manager.is_follow_up_question(test_user_id, query)
        assert not is_followup, f"'{query}' incorrectly detected as follow-up"
        print(f"✅ New query correctly identified: '{query}'")
    
    print("\n✅ ConversationManager RAG tests passed!\n")


async def test_multi_turn_rag():
    """Test MultiTurnRAG end-to-end with simulated queries."""
    print("\n" + "="*60)
    print("TEST 3: MultiTurnRAG")
    print("="*60)
    
    test_user_id = 999997
    
    # Test 1: Initial documentation query
    print("\n--- Test 1: New documentation query ---")
    result = await MultiTurnRAG.process_rag_query(
        user_id=test_user_id,
        query="What is EPCIS?",
        language='en'
    )
    
    assert 'message' in result
    assert 'sources' in result
    assert result['is_follow_up'] == False
    print(f"✅ New query processed")
    print(f"   Follow-up: {result['is_follow_up']}")
    print(f"   Message preview: {result['message'][:100]}...")
    
    # Test 2: Follow-up query (should reuse context)
    print("\n--- Test 2: Follow-up query ---")
    await asyncio.sleep(1)  # Small delay to ensure timestamp difference
    
    result = await MultiTurnRAG.process_rag_query(
        user_id=test_user_id,
        query="show me examples",
        language='en'
    )
    
    assert 'message' in result
    # This should be detected as follow-up
    print(f"✅ Follow-up query processed")
    print(f"   Follow-up: {result['is_follow_up']}")
    print(f"   Message preview: {result['message'][:100]}...")
    
    # Test 3: New topic (should perform new search)
    print("\n--- Test 3: New topic query ---")
    result = await MultiTurnRAG.process_rag_query(
        user_id=test_user_id,
        query="How do I create a blockchain anchor?",
        language='en'
    )
    
    assert 'message' in result
    print(f"✅ New topic query processed")
    print(f"   Follow-up: {result['is_follow_up']}")
    print(f"   Message preview: {result['message'][:100]}...")
    
    # Test 4: Amharic query
    print("\n--- Test 4: Amharic query ---")
    result = await MultiTurnRAG.process_rag_query(
        user_id=test_user_id,
        query="EPCIS ምንድን ነው?",
        language='am'
    )
    
    assert 'message' in result
    print(f"✅ Amharic query processed")
    print(f"   Message preview: {result['message'][:100]}...")
    
    print("\n✅ MultiTurnRAG tests passed!\n")


async def main():
    """Run all LAB 19 tests."""
    print("\n" + "="*60)
    print("LAB 19: Enhanced RAG & State Foundation - Test Suite")
    print("="*60)
    
    try:
        # Run tests in sequence
        await test_state_machine()
        await test_conversation_manager_rag()
        await test_multi_turn_rag()
        
        print("\n" + "="*60)
        print("🎉 ALL LAB 19 TESTS PASSED!")
        print("="*60)
        print("\nLAB 19 Components:")
        print("  ✅ State Machine (ConversationState, StateManager)")
        print("  ✅ ConversationManager RAG Extensions")
        print("  ✅ MultiTurnRAG (multi-turn documentation queries)")
        print("\nNext Steps:")
        print("  • Test with real Telegram messages")
        print("  • Verify 5-minute timeout works correctly")
        print("  • Monitor Redis state persistence")
        print("  • Move to LAB 20 (Coffee Operations Workflows)")
        print()
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
