"""
Test Entity Validation Framework

Tests the new entity validation system that checks for required entities
before executing voice commands and generates helpful clarification questions.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.command_integration import (
    validate_entities, 
    generate_clarification_question,
    REQUIRED_ENTITIES
)


def test_validate_entities_all_present():
    """Test validation passes when all required entities are present."""
    print("\n" + "="*60)
    print("TEST 1: All required entities present")
    print("="*60)
    
    intent = "record_commission"
    entities = {
        "quantity": 50,
        "origin": "Abebe Farm",
        "product": "Arabica",
        "unit": "bags"
    }
    
    is_valid, missing = validate_entities(intent, entities)
    
    print(f"Intent: {intent}")
    print(f"Entities: {entities}")
    print(f"Is Valid: {is_valid}")
    print(f"Missing: {missing}")
    
    assert is_valid == True, "Should be valid with all required entities"
    assert len(missing) == 0, "Should have no missing entities"
    print("✅ PASSED: Validation accepts complete entities")


def test_validate_entities_missing_one():
    """Test validation fails when one required entity is missing."""
    print("\n" + "="*60)
    print("TEST 2: One required entity missing")
    print("="*60)
    
    intent = "record_commission"
    entities = {
        "quantity": 50,
        # Missing "origin"
        "product": "Arabica"
    }
    
    is_valid, missing = validate_entities(intent, entities)
    
    print(f"Intent: {intent}")
    print(f"Entities: {entities}")
    print(f"Is Valid: {is_valid}")
    print(f"Missing: {missing}")
    
    assert is_valid == False, "Should be invalid with missing entity"
    assert "origin" in missing, "Should identify 'origin' as missing"
    print("✅ PASSED: Validation catches missing entity")


def test_validate_entities_missing_multiple():
    """Test validation fails when multiple required entities are missing."""
    print("\n" + "="*60)
    print("TEST 3: Multiple required entities missing")
    print("="*60)
    
    intent = "record_shipment"
    entities = {
        "carrier": "Ethiopian Shipping"
        # Missing "batch_id" and "destination"
    }
    
    is_valid, missing = validate_entities(intent, entities)
    
    print(f"Intent: {intent}")
    print(f"Entities: {entities}")
    print(f"Is Valid: {is_valid}")
    print(f"Missing: {missing}")
    
    assert is_valid == False, "Should be invalid with missing entities"
    assert "batch_id" in missing, "Should identify 'batch_id' as missing"
    assert "destination" in missing, "Should identify 'destination' as missing"
    print("✅ PASSED: Validation catches multiple missing entities")


def test_validate_entities_empty_string():
    """Test validation treats empty strings as missing."""
    print("\n" + "="*60)
    print("TEST 4: Empty string treated as missing")
    print("="*60)
    
    intent = "record_commission"
    entities = {
        "quantity": 50,
        "origin": ""  # Empty string should be treated as missing
    }
    
    is_valid, missing = validate_entities(intent, entities)
    
    print(f"Intent: {intent}")
    print(f"Entities: {entities}")
    print(f"Is Valid: {is_valid}")
    print(f"Missing: {missing}")
    
    assert is_valid == False, "Should be invalid with empty string"
    assert "origin" in missing, "Should identify empty 'origin' as missing"
    print("✅ PASSED: Validation treats empty strings as missing")


def test_validate_entities_empty_list():
    """Test validation treats empty lists as missing."""
    print("\n" + "="*60)
    print("TEST 5: Empty list treated as missing")
    print("="*60)
    
    intent = "pack_batches"
    entities = {
        "batch_ids": []  # Empty list should be treated as missing
    }
    
    is_valid, missing = validate_entities(intent, entities)
    
    print(f"Intent: {intent}")
    print(f"Entities: {entities}")
    print(f"Is Valid: {is_valid}")
    print(f"Missing: {missing}")
    
    assert is_valid == False, "Should be invalid with empty list"
    assert "batch_ids" in missing, "Should identify empty 'batch_ids' as missing"
    print("✅ PASSED: Validation treats empty lists as missing")


def test_clarification_single_missing():
    """Test clarification question for single missing entity."""
    print("\n" + "="*60)
    print("TEST 6: Clarification for single missing entity")
    print("="*60)
    
    intent = "record_commission"
    missing = ["origin"]
    
    question = generate_clarification_question(intent, missing)
    
    print(f"Intent: {intent}")
    print(f"Missing: {missing}")
    print(f"\nGenerated Question:")
    print(question)
    
    assert "origin" in question.lower() or "farm" in question.lower() or "location" in question.lower(), \
        "Question should mention origin/farm/location"
    assert "example" in question.lower(), "Question should include an example"
    print("✅ PASSED: Generates helpful clarification")


def test_clarification_multiple_missing():
    """Test clarification question for multiple missing entities."""
    print("\n" + "="*60)
    print("TEST 7: Clarification for multiple missing entities")
    print("="*60)
    
    intent = "record_shipment"
    missing = ["batch_id", "destination"]
    
    question = generate_clarification_question(intent, missing)
    
    print(f"Intent: {intent}")
    print(f"Missing: {missing}")
    print(f"\nGenerated Question:")
    print(question)
    
    assert "batch" in question.lower(), "Question should mention batch"
    assert "destination" in question.lower() or "where" in question.lower(), \
        "Question should mention destination"
    print("✅ PASSED: Generates helpful clarification for multiple fields")


def test_required_entities_coverage():
    """Test that all intents have entity specifications."""
    print("\n" + "="*60)
    print("TEST 8: All intents have entity specifications")
    print("="*60)
    
    expected_intents = [
        "record_commission",
        "record_shipment", 
        "record_receipt",
        "record_transformation",
        "pack_batches",
        "aggregate_batches",
        "unpack_batches",
        "disaggregate_batches",
        "split_batch"
    ]
    
    print(f"Expected intents: {len(expected_intents)}")
    print(f"Defined specs: {len(REQUIRED_ENTITIES)}")
    
    for intent in expected_intents:
        assert intent in REQUIRED_ENTITIES, f"Missing spec for intent: {intent}"
        spec = REQUIRED_ENTITIES[intent]
        assert "required" in spec, f"Intent {intent} missing 'required' field"
        assert "optional" in spec, f"Intent {intent} missing 'optional' field"
        assert "description" in spec, f"Intent {intent} missing 'description' field"
        assert "example" in spec, f"Intent {intent} missing 'example' field"
        print(f"  ✓ {intent}: {len(spec['required'])} required, {len(spec['optional'])} optional")
    
    print("✅ PASSED: All intents have complete specifications")


def test_real_world_scenarios():
    """Test real-world voice command scenarios."""
    print("\n" + "="*60)
    print("TEST 9: Real-world voice command scenarios")
    print("="*60)
    
    scenarios = [
        {
            "name": "Incomplete commission command",
            "intent": "record_commission",
            "entities": {"quantity": 50},  # Missing origin
            "should_fail": True
        },
        {
            "name": "Complete commission command",
            "intent": "record_commission",
            "entities": {"quantity": 50, "origin": "Abebe Farm"},
            "should_fail": False
        },
        {
            "name": "Shipment without destination",
            "intent": "record_shipment",
            "entities": {"batch_id": "ABC-123"},  # Missing destination
            "should_fail": True
        },
        {
            "name": "Complete receipt command",
            "intent": "record_receipt",
            "entities": {"batch_id": "ABC-123"},
            "should_fail": False
        },
        {
            "name": "Split without quantities",
            "intent": "split_batch",
            "entities": {"parent_batch_id": "ABC-123"},  # Missing splits
            "should_fail": True
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n  Scenario {i}: {scenario['name']}")
        is_valid, missing = validate_entities(scenario["intent"], scenario["entities"])
        
        if scenario["should_fail"]:
            assert not is_valid, f"Should fail: {scenario['name']}"
            print(f"    ✓ Failed as expected. Missing: {missing}")
            
            # Generate and display clarification
            question = generate_clarification_question(scenario["intent"], missing)
            print(f"    Clarification: {question[:80]}...")
        else:
            assert is_valid, f"Should pass: {scenario['name']}"
            print(f"    ✓ Passed as expected")
    
    print("\n✅ PASSED: All real-world scenarios handled correctly")


if __name__ == "__main__":
    print("="*60)
    print("ENTITY VALIDATION FRAMEWORK TESTS")
    print("="*60)
    
    try:
        test_validate_entities_all_present()
        test_validate_entities_missing_one()
        test_validate_entities_missing_multiple()
        test_validate_entities_empty_string()
        test_validate_entities_empty_list()
        test_clarification_single_missing()
        test_clarification_multiple_missing()
        test_required_entities_coverage()
        test_real_world_scenarios()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✅")
        print("="*60)
        print("\nEntity validation framework is working correctly!")
        print("Voice commands now validate required entities before execution.")
        print("Users get helpful clarification questions when information is missing.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
