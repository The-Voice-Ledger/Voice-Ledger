"""
Integration Test: Entity Validation in Voice Commands

Tests that entity validation is properly integrated into the voice command
execution flow, catching missing entities and providing helpful feedback.

This test models the dual delivery test structure - proper async/database setup.
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice.command_integration import execute_voice_command, VoiceCommandError
from database.connection import SessionLocal


# Test user credentials
TEST_USER_TELEGRAM_ID = 5753848438
TEST_USER_DID = "did:key:ztwN6mn4C5HnRiIJOLxGbXR-Q90pw4yiTG9i9iIgVXz8"


def test_validation_missing_entity():
    """Test that validation catches missing required entities."""
    logger.info("=" * 60)
    logger.info("TEST 1: Validation Catches Missing Entity")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Try to create batch without origin (required field)
        logger.info("Attempting to execute command with missing 'origin' entity...")
        
        try:
            result = execute_voice_command(
                db=db,
                intent="record_commission",
                entities={"quantity": 50, "product": "Arabica"},  # Missing origin
                user_id=None,
                user_did=TEST_USER_DID
            )
            
            # Should not reach here
            logger.error("❌ TEST 1 FAILED: Should have raised VoiceCommandError")
            return False
            
        except VoiceCommandError as e:
            error_msg = str(e)
            logger.info(f"✅ VoiceCommandError raised as expected")
            logger.info(f"\nError message:")
            logger.info(f"{error_msg}")
            
            # Verify error message is helpful
            if "need more information" not in error_msg.lower():
                logger.error("❌ TEST 1 FAILED: Error should mention needing more info")
                return False
            
            if "origin" not in error_msg.lower() and "farm" not in error_msg.lower() and "location" not in error_msg.lower():
                logger.error("❌ TEST 1 FAILED: Error should mention the missing entity")
                return False
            
            if "example" not in error_msg.lower():
                logger.error("❌ TEST 1 FAILED: Error should include an example")
                return False
            
            logger.info("✅ TEST 1 PASSED: Validation caught missing entity with helpful message")
            return True
    
    finally:
        db.close()


def test_validation_multiple_missing():
    """Test validation with multiple missing required entities."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Multiple Missing Entities")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        logger.info("Attempting shipment without batch_id and destination...")
        
        try:
            result = execute_voice_command(
                db=db,
                intent="record_shipment",
                entities={"carrier": "Ethiopian Shipping"},  # Missing batch_id, destination
                user_id=None,
                user_did=TEST_USER_DID
            )
            
            logger.error("❌ TEST 2 FAILED: Should have raised VoiceCommandError")
            return False
            
        except VoiceCommandError as e:
            error_msg = str(e)
            logger.info(f"✅ VoiceCommandError raised as expected")
            logger.info(f"\nError message:")
            logger.info(f"{error_msg}")
            
            # Should mention both missing entities
            has_batch = "batch" in error_msg.lower()
            has_destination = "destination" in error_msg.lower() or "where" in error_msg.lower()
            
            if not has_batch:
                logger.error("❌ TEST 2 FAILED: Should mention missing batch_id")
                return False
            
            if not has_destination:
                logger.error("❌ TEST 2 FAILED: Should mention missing destination")
                return False
            
            logger.info("✅ TEST 2 PASSED: Validation caught multiple missing entities")
            return True
    
    finally:
        db.close()


def test_validation_empty_values():
    """Test that validation treats empty strings and lists as missing."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Empty Values Treated as Missing")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Test empty string
        logger.info("Testing empty string for 'origin'...")
        
        try:
            result = execute_voice_command(
                db=db,
                intent="record_commission",
                entities={"quantity": 50, "origin": ""},  # Empty string
                user_id=None,
                user_did=TEST_USER_DID
            )
            
            logger.error("❌ TEST 3a FAILED: Should have rejected empty string")
            return False
            
        except VoiceCommandError as e:
            logger.info(f"✅ Empty string correctly rejected: {str(e)[:80]}...")
        
        # Test empty list
        logger.info("\nTesting empty list for 'batch_ids'...")
        
        try:
            result = execute_voice_command(
                db=db,
                intent="pack_batches",
                entities={"batch_ids": []},  # Empty list
                user_id=None,
                user_did=TEST_USER_DID
            )
            
            logger.error("❌ TEST 3b FAILED: Should have rejected empty list")
            return False
            
        except VoiceCommandError as e:
            logger.info(f"✅ Empty list correctly rejected: {str(e)[:80]}...")
        
        logger.info("✅ TEST 3 PASSED: Empty values correctly treated as missing")
        return True
    
    finally:
        db.close()


def test_validation_complete_entities():
    """Test that validation passes with all required entities present."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Complete Entities Pass Validation")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        logger.info("Attempting receipt with all required entities...")
        
        try:
            # Use record_receipt which only requires batch_id
            # This should pass validation (handler might fail for other reasons)
            message, result = execute_voice_command(
                db=db,
                intent="record_receipt",
                entities={"batch_id": "TEST-BATCH-123"},  # All required entities present
                user_id=None,
                user_did=TEST_USER_DID
            )
            
            # If we get here, validation passed
            logger.info(f"✅ Validation passed (command execution started)")
            logger.info(f"Note: Handler may fail (batch not found), but validation succeeded")
            logger.info("✅ TEST 4 PASSED: Complete entities pass validation")
            return True
            
        except VoiceCommandError as e:
            error_msg = str(e)
            
            # Check if error is from validation or from handler
            if "need more information" in error_msg.lower():
                # This is a validation error - test failed
                logger.error(f"❌ TEST 4 FAILED: Validation incorrectly rejected complete entities")
                logger.error(f"Error: {error_msg}")
                return False
            else:
                # This is from the handler (e.g., batch not found) - validation passed
                logger.info(f"✅ Validation passed (handler failed for other reasons)")
                logger.info(f"Handler error: {error_msg[:100]}...")
                logger.info("✅ TEST 4 PASSED: Complete entities pass validation")
                return True
    
    finally:
        db.close()


def test_clarification_quality():
    """Test that clarification messages are clear and voice-friendly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Clarification Message Quality")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        test_cases = [
            {
                "intent": "record_commission",
                "entities": {"quantity": 50},  # Missing origin
                "expected_keywords": ["origin", "farm", "location", "example"],
                "name": "Commission with missing origin"
            },
            {
                "intent": "split_batch",
                "entities": {"parent_batch_id": "ABC-123"},  # Missing splits
                "expected_keywords": ["split", "how", "quantities", "example"],
                "name": "Split with missing quantities"
            }
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            logger.info(f"\nTesting: {test_case['name']}")
            
            try:
                execute_voice_command(
                    db=db,
                    intent=test_case["intent"],
                    entities=test_case["entities"],
                    user_id=None,
                    user_did=TEST_USER_DID
                )
                
                logger.error(f"❌ Should have raised error for: {test_case['name']}")
                all_passed = False
                continue
                
            except VoiceCommandError as e:
                error_msg = str(e)
                
                # Check message quality
                if len(error_msg) < 50:
                    logger.error(f"❌ Message too short (< 50 chars): {len(error_msg)}")
                    all_passed = False
                    continue
                
                if len(error_msg) > 500:
                    logger.warning(f"⚠️  Message quite long (> 500 chars): {len(error_msg)}")
                
                # Check for expected keywords
                keywords_found = [kw for kw in test_case["expected_keywords"] 
                                if kw.lower() in error_msg.lower()]
                
                logger.info(f"  Message length: {len(error_msg)} chars")
                logger.info(f"  Keywords found: {keywords_found} / {test_case['expected_keywords']}")
                logger.info(f"  Preview: {error_msg[:120]}...")
                
                if len(keywords_found) < 2:
                    logger.error(f"❌ Should contain at least 2 keywords, found: {len(keywords_found)}")
                    all_passed = False
                else:
                    logger.info(f"  ✅ Clear and helpful message")
        
        if all_passed:
            logger.info("\n✅ TEST 5 PASSED: All clarification messages are clear and helpful")
        else:
            logger.error("\n❌ TEST 5 FAILED: Some messages need improvement")
        
        return all_passed
    
    finally:
        db.close()


def test_various_intents():
    """Test validation across different intent types."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Validation Across Multiple Intent Types")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        test_cases = [
            {
                "name": "Transformation without process_type",
                "intent": "record_transformation",
                "entities": {"batch_id": "ABC-123"},  # Missing process_type
                "should_fail": True
            },
            {
                "name": "Unpack without container_id",
                "intent": "unpack_batches",
                "entities": {},  # Missing container_id
                "should_fail": True
            },
            {
                "name": "Receipt with complete data",
                "intent": "record_receipt",
                "entities": {"batch_id": "ABC-123"},  # Complete
                "should_fail": False  # Validation should pass (handler may fail)
            }
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            logger.info(f"\n  Testing: {test_case['name']}")
            
            try:
                message, result = execute_voice_command(
                    db=db,
                    intent=test_case["intent"],
                    entities=test_case["entities"],
                    user_id=None,
                    user_did=TEST_USER_DID
                )
                
                if test_case["should_fail"]:
                    logger.error(f"    ❌ Should have failed validation")
                    all_passed = False
                else:
                    logger.info(f"    ✅ Validation passed as expected")
                
            except VoiceCommandError as e:
                error_msg = str(e)
                
                if test_case["should_fail"]:
                    # Check if it's a validation error
                    if "need more information" in error_msg.lower():
                        logger.info(f"    ✅ Failed validation as expected")
                    else:
                        logger.info(f"    ✅ Failed (handler error after validation)")
                else:
                    # Should not have failed validation
                    if "need more information" in error_msg.lower():
                        logger.error(f"    ❌ Should not have failed validation")
                        all_passed = False
                    else:
                        logger.info(f"    ✅ Validation passed (handler failed for other reasons)")
        
        if all_passed:
            logger.info("\n✅ TEST 6 PASSED: Validation works correctly across intent types")
        else:
            logger.error("\n❌ TEST 6 FAILED: Some validations incorrect")
        
        return all_passed
    
    finally:
        db.close()


def run_all_tests():
    """Run all entity validation integration tests."""
    logger.info("=" * 60)
    logger.info("ENTITY VALIDATION INTEGRATION TESTS")
    logger.info("=" * 60)
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(("Missing Entity", test_validation_missing_entity()))
    results.append(("Multiple Missing", test_validation_multiple_missing()))
    results.append(("Empty Values", test_validation_empty_values()))
    results.append(("Complete Entities", test_validation_complete_entities()))
    results.append(("Clarification Quality", test_clarification_quality()))
    results.append(("Various Intents", test_various_intents()))
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED!")
        logger.info("\nEntity validation framework is working correctly!")
        logger.info("Voice commands now validate required entities before execution.")
        logger.info("Users get helpful clarification questions when information is missing.")
        return True
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
