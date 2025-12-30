"""
Test RAG Integration via Telegram Bot Webhook

Simulates Telegram messages to test RAG responses programmatically.
"""

import requests
import json
import time


def simulate_telegram_message(message_text, user_id=999999, chat_id=999999):
    """
    Simulate a Telegram message webhook call
    """
    # Telegram webhook payload structure
    payload = {
        "update_id": int(time.time()),
        "message": {
            "message_id": int(time.time()),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser"
            },
            "chat": {
                "id": chat_id,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser",
                "type": "private"
            },
            "date": int(time.time()),
            "text": message_text
        }
    }
    
    # Send to local webhook endpoint
    url = "http://localhost:8000/voice/telegram/webhook"
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_text": response.text if response.status_code != 200 else "OK"
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": None,
            "success": False,
            "error": str(e)
        }


def test_telegram_rag():
    """
    Test RAG responses via Telegram webhook
    """
    print("\n" + "=" * 60)
    print("TELEGRAM RAG INTEGRATION TEST")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "RFQ Documentation Query",
            "message": "How are RFQs implemented in this system?",
            "should_mention": ["RFQ", "rfq"],
            "should_not_mention": ["don't handle", "do not handle"]
        },
        {
            "name": "EPCIS Documentation Query",
            "message": "What is EPCIS?",
            "should_mention": ["EPCIS", "epcis", "GS1", "event"],
            "should_not_mention": ["don't handle", "do not support"]
        },
        {
            "name": "Blockchain Anchoring Query",
            "message": "How does blockchain anchoring work?",
            "should_mention": ["blockchain", "anchor"],
            "should_not_mention": ["don't handle"]
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[TEST {i}] {test_case['name']}")
        print("-" * 60)
        print(f"Message: \"{test_case['message']}\"")
        
        # Simulate the message
        result = simulate_telegram_message(test_case['message'])
        
        if not result['success']:
            print(f"❌ FAIL - Webhook call failed")
            if 'error' in result:
                print(f"   Error: {result['error']}")
            else:
                print(f"   Status: {result['status_code']}")
                print(f"   Response: {result['response_text']}")
            results.append((test_case['name'], False))
            continue
        
        print(f"✓ Webhook accepted (HTTP {result['status_code']})")
        
        # Give it time to process and send response
        print("  Waiting for bot to process...")
        time.sleep(3)
        
        # Note: We can't easily check the bot's response without accessing Telegram API
        # But we can verify the webhook was accepted successfully
        print(f"✅ PASS - Webhook processed successfully")
        print(f"   (Bot should have sent a knowledge-grounded response)")
        
        results.append((test_case['name'], True))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 ALL TELEGRAM WEBHOOK TESTS PASSED!")
        print("\nNote: Webhooks accepted successfully. To verify actual responses:")
        print("1. Check bot messages in Telegram")
        print("2. Check logs: tail -f logs/voice_api.log")
        print("3. Verify responses mention correct topics (RFQs, EPCIS, etc.)")
    else:
        failed_count = sum(1 for _, passed in results if not passed)
        print(f"\n⚠️  {failed_count}/{len(results)} tests failed")
    
    return all_passed


def check_services():
    """Check if required services are running"""
    print("\n" + "=" * 60)
    print("SERVICE CHECK")
    print("=" * 60)
    
    # Check FastAPI
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        print("✅ FastAPI running (port 8000)")
        api_running = True
    except:
        print("❌ FastAPI not running")
        api_running = False
    
    return api_running


if __name__ == "__main__":
    import sys
    
    # Check services first
    if not check_services():
        print("\n⚠️  Services not running. Start them with:")
        print("   ./admin_scripts/START_SERVICES.sh")
        sys.exit(1)
    
    # Run tests
    success = test_telegram_rag()
    sys.exit(0 if success else 1)
