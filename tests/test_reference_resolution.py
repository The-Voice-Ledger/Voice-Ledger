"""
Test Reference Resolution

Tests the reference resolution system that allows users to say things like
"the first one", "number 2", "last batch" and have them resolved to actual IDs.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.integrations.conversation_manager import (
    ConversationManager,
    resolve_reference,
    resolve_entity_references
)


def test_store_and_retrieve_results():
    """Test storing and retrieving search results."""
    print("\n" + "="*60)
    print("TEST 1: Store and Retrieve Search Results")
    print("="*60)
    
    user_id = 99999  # Test user
    
    # Store batch results
    batch_ids = ['BATCH-001', 'BATCH-002', 'BATCH-003', 'BATCH-004']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    # Retrieve them
    retrieved = ConversationManager.get_search_results(user_id, 'batch')
    
    print(f"Stored: {batch_ids}")
    print(f"Retrieved: {retrieved}")
    
    assert retrieved == batch_ids, f"Mismatch: {retrieved} != {batch_ids}"
    print("✅ TEST 1 PASSED: Results stored and retrieved correctly")
    
    # Cleanup
    ConversationManager.clear_conversation(user_id)
    return True


def test_ordinal_references():
    """Test resolving ordinal references (first, second, third)."""
    print("\n" + "="*60)
    print("TEST 2: Ordinal References")
    print("="*60)
    
    user_id = 99999
    batch_ids = ['ABC-001', 'ABC-002', 'ABC-003', 'ABC-004', 'ABC-005']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    test_cases = [
        ("ship the first one", 'ABC-001'),
        ("I want the second batch", 'ABC-002'),
        ("use the third option", 'ABC-003'),
        ("pick the 1st", 'ABC-001'),
        ("select 2nd one", 'ABC-002'),
        ("choose 3rd", 'ABC-003'),
        ("the fourth item", 'ABC-004'),
        ("fifth batch", 'ABC-005'),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = resolve_reference(text, user_id, 'batch')
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} \"{text}\"")
        print(f"     Expected: {expected}")
        print(f"     Got:      {result}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 2 PASSED: All ordinal references resolved")
    else:
        print("\n❌ TEST 2 FAILED: Some ordinal references failed")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


def test_last_reference():
    """Test resolving 'last' reference."""
    print("\n" + "="*60)
    print("TEST 3: Last Reference")
    print("="*60)
    
    user_id = 99999
    batch_ids = ['BATCH-A', 'BATCH-B', 'BATCH-C']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    test_cases = [
        ("ship the last one", 'BATCH-C'),
        ("use the last batch", 'BATCH-C'),
        ("pick last", 'BATCH-C'),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = resolve_reference(text, user_id, 'batch')
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} \"{text}\"")
        print(f"     Expected: {expected}")
        print(f"     Got:      {result}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 3 PASSED: Last references resolved correctly")
    else:
        print("\n❌ TEST 3 FAILED: Some last references failed")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


def test_number_references():
    """Test resolving 'number X' and '#X' references."""
    print("\n" + "="*60)
    print("TEST 4: Number References")
    print("="*60)
    
    user_id = 99999
    batch_ids = ['ID-001', 'ID-002', 'ID-003', 'ID-004']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    test_cases = [
        ("ship number 1", 'ID-001'),
        ("use number 2", 'ID-002'),
        ("pick number 3", 'ID-003'),
        ("batch 2 please", 'ID-002'),
        ("option 4", 'ID-004'),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = resolve_reference(text, user_id, 'batch')
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} \"{text}\"")
        print(f"     Expected: {expected}")
        print(f"     Got:      {result}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 4 PASSED: Number references resolved correctly")
    else:
        print("\n❌ TEST 4 FAILED: Some number references failed")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


def test_out_of_range():
    """Test handling of out-of-range references."""
    print("\n" + "="*60)
    print("TEST 5: Out of Range References")
    print("="*60)
    
    user_id = 99999
    batch_ids = ['BATCH-001', 'BATCH-002']  # Only 2 results
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    test_cases = [
        "the fifth one",  # Index 4, out of range
        "number 10",      # Index 9, out of range
        "the tenth",      # Index 9, out of range
    ]
    
    all_passed = True
    for text in test_cases:
        result = resolve_reference(text, user_id, 'batch')
        passed = result is None
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} \"{text}\"")
        print(f"     Expected: None (out of range)")
        print(f"     Got:      {result}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 5 PASSED: Out of range handled correctly")
    else:
        print("\n❌ TEST 5 FAILED: Out of range handling incorrect")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


def test_no_results():
    """Test behavior when no results are stored."""
    print("\n" + "="*60)
    print("TEST 6: No Results Stored")
    print("="*60)
    
    user_id = 99999
    ConversationManager.clear_conversation(user_id)  # Ensure clean state
    
    # Try to resolve without storing results
    result = resolve_reference("the first one", user_id, 'batch')
    
    passed = result is None
    status = "✅" if passed else "❌"
    
    print(f"\n  {status} Text: \"the first one\"")
    print(f"     Expected: None (no results stored)")
    print(f"     Got:      {result}")
    
    if passed:
        print("\n✅ TEST 6 PASSED: No results handled correctly")
    else:
        print("\n❌ TEST 6 FAILED: Should return None when no results")
    
    return passed


def test_entity_resolution():
    """Test resolving references within entities dict."""
    print("\n" + "="*60)
    print("TEST 7: Entity Reference Resolution")
    print("="*60)
    
    user_id = 99999
    batch_ids = ['BATCH-X', 'BATCH-Y', 'BATCH-Z']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    
    test_cases = [
        {
            "entities": {"batch_id": "first", "quantity": 50},
            "user_text": "ship the first one with 50kg",
            "expected_batch_id": "BATCH-X",
            "name": "First reference in batch_id"
        },
        {
            "entities": {"parent_batch_id": "second", "splits": [30, 20]},
            "user_text": "split the second batch into 30 and 20",
            "expected_batch_id": "BATCH-Y",
            "name": "Second reference in parent_batch_id"
        },
        {
            "entities": {"batch_id": "BATCH-EXPLICIT", "quantity": 100},
            "user_text": "ship BATCH-EXPLICIT",
            "expected_batch_id": "BATCH-EXPLICIT",
            "name": "Explicit ID unchanged"
        },
    ]
    
    all_passed = True
    for test in test_cases:
        result_entities = resolve_entity_references(
            test["entities"].copy(),
            user_id,
            test["user_text"]
        )
        
        # Check the relevant field
        if "batch_id" in test["entities"]:
            actual = result_entities.get("batch_id")
            expected = test["expected_batch_id"]
        elif "parent_batch_id" in test["entities"]:
            actual = result_entities.get("parent_batch_id")
            expected = test["expected_batch_id"]
        else:
            actual = None
            expected = None
        
        passed = actual == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} {test['name']}")
        print(f"     Input entities: {test['entities']}")
        print(f"     User text: \"{test['user_text']}\"")
        print(f"     Expected ID: {expected}")
        print(f"     Got ID: {actual}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 7 PASSED: Entity resolution works correctly")
    else:
        print("\n❌ TEST 7 FAILED: Some entity resolutions failed")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


def test_real_world_scenarios():
    """Test realistic multi-turn conversation scenarios."""
    print("\n" + "="*60)
    print("TEST 8: Real-World Conversation Scenarios")
    print("="*60)
    
    user_id = 99999
    
    # Scenario: User searches, then acts on results
    print("\n  Scenario: Search then ship")
    
    # 1. System shows search results
    batch_ids = ['ABEBE-2025-001', 'ABEBE-2025-002', 'DIRE-2025-003']
    ConversationManager.store_search_results(user_id, 'batch', batch_ids)
    print(f"  System: Found 3 batches: {batch_ids}")
    
    # 2. User says "ship the first one to Addis"
    user_text = "ship the first one to Addis Ababa"
    resolved = resolve_reference(user_text, user_id, 'batch')
    
    passed1 = resolved == 'ABEBE-2025-001'
    status1 = "✅" if passed1 else "❌"
    print(f"  {status1} User: \"{user_text}\"")
    print(f"     Resolved to: {resolved}")
    
    # 3. User says "and also the last one"
    user_text2 = "and also ship the last one"
    resolved2 = resolve_reference(user_text2, user_id, 'batch')
    
    passed2 = resolved2 == 'DIRE-2025-003'
    status2 = "✅" if passed2 else "❌"
    print(f"  {status2} User: \"{user_text2}\"")
    print(f"     Resolved to: {resolved2}")
    
    all_passed = passed1 and passed2
    
    if all_passed:
        print("\n✅ TEST 8 PASSED: Real-world scenario handled correctly")
    else:
        print("\n❌ TEST 8 FAILED: Real-world scenario failed")
    
    ConversationManager.clear_conversation(user_id)
    return all_passed


if __name__ == "__main__":
    print("="*60)
    print("REFERENCE RESOLUTION TESTS")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("Store/Retrieve Results", test_store_and_retrieve_results()))
    results.append(("Ordinal References", test_ordinal_references()))
    results.append(("Last Reference", test_last_reference()))
    results.append(("Number References", test_number_references()))
    results.append(("Out of Range", test_out_of_range()))
    results.append(("No Results", test_no_results()))
    results.append(("Entity Resolution", test_entity_resolution()))
    results.append(("Real-World Scenarios", test_real_world_scenarios()))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("")
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nReference resolution is working correctly!")
        print("\nUsers can now say:")
        print("  • 'the first one', 'the second batch'")
        print("  • '1st', '2nd', '3rd'")
        print("  • 'the last one'")
        print("  • 'number 2', 'batch 3'")
        print("\nAnd have them resolved to actual IDs from search results!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)
