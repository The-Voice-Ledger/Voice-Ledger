"""
Test RAG Integration with Conversational AI

Validates that:
1. Documentation queries return knowledge-grounded responses
2. No wrong fallback responses ("don't handle" when feature exists)
3. Transactional commands bypass RAG
4. JSON format is preserved in all cases

Lab 18: RAG-Enhanced Conversational AI
Date: December 24, 2024
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice.integrations.english_conversation import process_english_conversation
from voice.rag import classify_query_type, QueryType
import json


def test_rfq_documentation_query():
    """Test: RFQ documentation query returns correct information"""
    print("\n[TEST 1] RFQ Documentation Query")
    print("-" * 60)
    
    result = process_english_conversation(
        user_id=999,  # Test user
        transcript='How are RFQs implemented in this system?',
        use_rag=True
    )
    
    msg = result.get('message_text', '')
    mentions_rfq = 'RFQ' in msg or 'rfq' in msg.lower()
    no_wrong_answer = 'dont handle' not in msg.lower() and 'do not handle' not in msg.lower()
    
    passed = mentions_rfq and no_wrong_answer
    
    print(f"✓ Mentions RFQs: {mentions_rfq}")
    print(f"✓ No wrong fallback: {no_wrong_answer}")
    print(f"Result: {'✅ PASS' if passed else '❌ FAIL'}")
    
    if not passed:
        print(f"Response preview: {msg[:200]}")
    
    return passed


def test_epcis_documentation_query():
    """Test: EPCIS documentation query returns correct information"""
    print("\n[TEST 2] EPCIS Documentation Query")
    print("-" * 60)
    
    result = process_english_conversation(
        user_id=999,
        transcript='What is EPCIS and how does it work?',
        use_rag=True
    )
    
    msg = result.get('message_text', '')
    mentions_epcis = 'EPCIS' in msg or 'epcis' in msg.lower()
    no_wrong_answer = 'dont handle' not in msg.lower()
    
    passed = mentions_epcis and no_wrong_answer
    
    print(f"✓ Mentions EPCIS: {mentions_epcis}")
    print(f"✓ No wrong fallback: {no_wrong_answer}")
    print(f"Result: {'✅ PASS' if passed else '❌ FAIL'}")
    
    if not passed:
        print(f"Response preview: {msg[:200]}")
    
    return passed


def test_transactional_bypass():
    """Test: Transactional commands correctly bypass RAG"""
    print("\n[TEST 3] Transactional Command Bypass")
    print("-" * 60)
    
    # Test transactional commands (should be classified as TRANSACTIONAL)
    transactional_commands = [
        'Record 50 kg of Arabica coffee',
        'I want to ship batch ABC123',
        'Create a new shipment',
        'Register a new commission'
    ]
    
    # Test operational queries (should NOT be transactional)
    operational_queries = [
        'Show me my batches',
        'What is my credential status?',
        'List all pending shipments'
    ]
    
    all_passed = True
    
    print("Testing TRANSACTIONAL commands:")
    for cmd in transactional_commands:
        query_type = classify_query_type(cmd)
        is_transactional = query_type == QueryType.TRANSACTIONAL
        
        if not is_transactional:
            print(f"  ❌ '{cmd}' classified as {query_type.value} (expected TRANSACTIONAL)")
            all_passed = False
        else:
            print(f"  ✓ '{cmd}' → TRANSACTIONAL")
    
    print("\nTesting OPERATIONAL queries:")
    for cmd in operational_queries:
        query_type = classify_query_type(cmd)
        is_operational = query_type == QueryType.OPERATIONAL
        
        if not is_operational:
            print(f"  ⚠️  '{cmd}' classified as {query_type.value} (expected OPERATIONAL)")
        else:
            print(f"  ✓ '{cmd}' → OPERATIONAL")
    
    print(f"\nResult: {'✅ PASS' if all_passed else '❌ FAIL'}")
    return all_passed


def test_json_format_preservation():
    """Test: JSON format is preserved even with RAG context"""
    print("\n[TEST 4] JSON Format Preservation")
    print("-" * 60)
    
    result = process_english_conversation(
        user_id=999,
        transcript='Tell me about blockchain anchoring',
        use_rag=True
    )
    
    # Check that result has expected JSON structure
    has_message_text = 'message_text' in result
    has_message_spoken = 'message_spoken' in result
    has_ready_to_execute = 'ready_to_execute' in result
    
    # For documentation queries, these should be present but ready_to_execute should be False
    is_valid_doc_response = (
        has_message_text and 
        has_message_spoken and 
        has_ready_to_execute and 
        not result['ready_to_execute']
    )
    
    print(f"✓ Has message_text: {has_message_text}")
    print(f"✓ Has message_spoken: {has_message_spoken}")
    print(f"✓ Has ready_to_execute: {has_ready_to_execute}")
    print(f"✓ Valid doc response format: {is_valid_doc_response}")
    print(f"Result: {'✅ PASS' if is_valid_doc_response else '❌ FAIL'}")
    
    return is_valid_doc_response


def test_hybrid_query():
    """Test: Hybrid query combining documentation and operational data"""
    print("\n[TEST 5] Hybrid Query")
    print("-" * 60)
    
    result = process_english_conversation(
        user_id=999,
        transcript='What batches are currently pending verification?',
        use_rag=True
    )
    
    msg = result.get('message_text', '')
    
    # Should provide an answer (not say "don't handle")
    no_wrong_answer = 'dont handle' not in msg.lower()
    has_response = len(msg) > 10
    
    passed = no_wrong_answer and has_response
    
    print(f"✓ Has substantive response: {has_response}")
    print(f"✓ No wrong fallback: {no_wrong_answer}")
    print(f"Result: {'✅ PASS' if passed else '❌ FAIL'}")
    
    if not passed:
        print(f"Response preview: {msg[:200]}")
    
    return passed


def run_all_tests():
    """Run all RAG integration tests"""
    print("\n" + "=" * 60)
    print("RAG INTEGRATION TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("RFQ Documentation Query", test_rfq_documentation_query),
        ("EPCIS Documentation Query", test_epcis_documentation_query),
        ("Transactional Command Bypass", test_transactional_bypass),
        ("JSON Format Preservation", test_json_format_preservation),
        ("Hybrid Query", test_hybrid_query),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ RAG system working correctly:")
        print("   - Documentation queries return knowledge-grounded responses")
        print("   - No wrong fallback responses")
        print("   - Transactional commands bypass RAG")
        print("   - JSON format preserved")
    else:
        failed_count = sum(1 for _, passed in results if not passed)
        print(f"\n⚠️  {failed_count}/{len(results)} tests failed")
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
