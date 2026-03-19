"""
Test Voice Formatting Helper

Tests the format_for_voice() function that converts text with symbols
into natural voice-friendly text for TTS synthesis.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.telegram.voice_responses import format_for_voice


def test_currency_formatting():
    """Test currency symbol conversion."""
    print("\n" + "="*60)
    print("TEST 1: Currency Formatting")
    print("="*60)
    
    test_cases = [
        ("Price is $50", "Price is 50 dollars"),
        ("€100 total", "100 euros total"),
        ("£75.50 each", "75.50 pounds each"),
        ("450 ETB per kg", "450 birr per kg"),
        ("Cost: $25.99", "Cost: 25.99 dollars"),
        ("100 USD", "100 US dollars"),
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        result = format_for_voice(input_text)
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} Input:    '{input_text}'")
        print(f"     Expected: '{expected}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 1 PASSED: All currency conversions correct")
    else:
        print("\n❌ TEST 1 FAILED: Some currency conversions incorrect")
    
    return all_passed


def test_units_formatting():
    """Test unit conversion."""
    print("\n" + "="*60)
    print("TEST 2: Units Formatting")
    print("="*60)
    
    test_cases = [
        ("50kg of coffee", "50 kilograms of coffee"),
        ("Quality is 95%", "Quality is 95 percent"),
        ("500g sample", "500 grams sample"),
        ("10km away", "10 kilometers away"),
        ("2.5m height", "2.5 meters height"),
        ("Weight: 25 kg", "Weight: 25 kilograms"),
        ("100 lb", "100 pounds"),
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        result = format_for_voice(input_text)
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} Input:    '{input_text}'")
        print(f"     Expected: '{expected}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 2 PASSED: All unit conversions correct")
    else:
        print("\n❌ TEST 2 FAILED: Some unit conversions incorrect")
    
    return all_passed


def test_ordinals_formatting():
    """Test ordinal number conversion."""
    print("\n" + "="*60)
    print("TEST 3: Ordinals Formatting")
    print("="*60)
    
    test_cases = [
        ("Select the 1st option", "Select the first option"),
        ("2nd batch", "second batch"),
        ("3rd place", "third place"),
        ("10th item", "tenth item"),
        ("20th century", "twentieth century"),
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        result = format_for_voice(input_text)
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} Input:    '{input_text}'")
        print(f"     Expected: '{expected}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 3 PASSED: All ordinal conversions correct")
    else:
        print("\n❌ TEST 3 FAILED: Some ordinal conversions incorrect")
    
    return all_passed


def test_small_numbers_formatting():
    """Test small number spelling."""
    print("\n" + "="*60)
    print("TEST 4: Small Numbers Formatting")
    print("="*60)
    
    test_cases = [
        ("Found 1 batch", "Found one batch"),
        ("Select 2 options", "Select two options"),
        ("Got 5 bags", "Got five bags"),
        ("There are 10 items", "There are ten items"),
        ("Pick 15 samples", "Pick fifteen samples"),
        # Should NOT convert in codes/years
        ("Batch ABC-123", "Batch ABC-123"),  # Keep codes as-is
        ("Year 2025", "Year 2025"),  # Keep years
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        result = format_for_voice(input_text)
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} Input:    '{input_text}'")
        print(f"     Expected: '{expected}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 4 PASSED: All number conversions correct")
    else:
        print("\n❌ TEST 4 FAILED: Some number conversions incorrect")
    
    return all_passed


def test_complex_messages():
    """Test realistic complex messages."""
    print("\n" + "="*60)
    print("TEST 5: Complex Real-World Messages")
    print("="*60)
    
    test_cases = [
        {
            "input": "Batch ABC-123: 50kg of Arabica coffee for $450 (Grade A, 95% quality)",
            "expected": "Batch ABC-123: 50 kilograms of Arabica coffee for 450 dollars (Grade A, 95 percent quality)",
            "name": "Batch details with mixed formatting"
        },
        {
            "input": "Shipment of 3 batches totaling 150kg arrived. Cost: €500. Quality: 1st grade.",
            "expected": "Shipment of three batches totaling 150 kilograms arrived. Cost: 500 euros. Quality: first grade.",
            "name": "Shipment notification"
        },
        {
            "input": "Payment received: 1500 ETB for 10kg. This is the 2nd payment today.",
            "expected": "Payment received: 1500 birr for 10 kilograms. This is the second payment today.",
            "name": "Payment confirmation"
        },
        {
            "input": "Your batch is ranked 5th out of 20 submissions with 88% quality score.",
            "expected": "Your batch is ranked fifth out of 20 submissions with 88 percent quality score.",
            "name": "Ranking notification"
        },
    ]
    
    all_passed = True
    for test in test_cases:
        result = format_for_voice(test["input"])
        passed = result == test["expected"]
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} {test['name']}")
        print(f"     Input:")
        print(f"       {test['input']}")
        print(f"     Expected:")
        print(f"       {test['expected']}")
        print(f"     Got:")
        print(f"       {result}")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 5 PASSED: All complex messages formatted correctly")
    else:
        print("\n❌ TEST 5 FAILED: Some complex messages incorrect")
    
    return all_passed


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\n" + "="*60)
    print("TEST 6: Edge Cases")
    print("="*60)
    
    test_cases = [
        {
            "input": "",
            "expected": "",
            "name": "Empty string"
        },
        {
            "input": "   ",
            "expected": "",
            "name": "Whitespace only"
        },
        {
            "input": "No special formatting needed here",
            "expected": "No special formatting needed here",
            "name": "Plain text unchanged"
        },
        {
            "input": "$$$", 
            "expected": "$$$",
            "name": "Invalid currency format"
        },
        {
            "input": "100",
            "expected": "100",
            "name": "Large number unchanged"
        },
        {
            "input": "123-456-789",
            "expected": "123-456-789",
            "name": "Code with hyphens preserved"
        },
    ]
    
    all_passed = True
    for test in test_cases:
        result = format_for_voice(test["input"])
        passed = result == test["expected"]
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} {test['name']}")
        print(f"     Input:    '{test['input']}'")
        print(f"     Expected: '{test['expected']}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 6 PASSED: All edge cases handled correctly")
    else:
        print("\n❌ TEST 6 FAILED: Some edge cases incorrect")
    
    return all_passed


def test_preserve_important_codes():
    """Test that important codes/IDs are preserved."""
    print("\n" + "="*60)
    print("TEST 7: Preserve Codes and IDs")
    print("="*60)
    
    test_cases = [
        ("Batch ID: ABEBE-2025-001", "Batch ID: ABEBE-2025-001"),
        ("GTIN: 00614141852251", "GTIN: 00614141852251"),
        ("Tracking: ABC-123-XYZ-456", "Tracking: ABC-123-XYZ-456"),
        ("Token ID: 12345", "Token ID: 12345"),
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        result = format_for_voice(input_text)
        passed = result == expected
        status = "✅" if passed else "❌"
        
        print(f"\n  {status} Input:    '{input_text}'")
        print(f"     Expected: '{expected}'")
        print(f"     Got:      '{result}'")
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 7 PASSED: Codes and IDs preserved")
    else:
        print("\n❌ TEST 7 FAILED: Some codes altered incorrectly")
    
    assert all_passed, "Some codes were altered incorrectly"


if __name__ == "__main__":
    print("="*60)
    print("VOICE FORMATTING HELPER TESTS")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("Currency Formatting", test_currency_formatting()))
    results.append(("Units Formatting", test_units_formatting()))
    results.append(("Ordinals Formatting", test_ordinals_formatting()))
    results.append(("Small Numbers", test_small_numbers_formatting()))
    results.append(("Complex Messages", test_complex_messages()))
    results.append(("Edge Cases", test_edge_cases()))
    results.append(("Preserve Codes", test_preserve_important_codes()))
    
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
        print("\nVoice formatting helper is working correctly!")
        print("TTS output will now be more natural and voice-friendly.")
        print("\nConversions implemented:")
        print("  • Currency symbols → spelled out amounts")
        print("  • Units (kg, %, etc.) → full words")
        print("  • Ordinals (1st, 2nd) → words (first, second)")
        print("  • Small numbers → spelled out")
        print("  • Codes and IDs preserved")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)
