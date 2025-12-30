#!/usr/bin/env python3
"""
Test LAB 20 workflows via Telegram API simulation
Uses Emmanuel Acho's real Telegram user ID: 5753848438
"""

import asyncio
import sys
import time
sys.path.insert(0, '/Users/manu/Voice-Ledger')

from voice.telegram.telegram_api import process_natural_text_query
from database.models import SessionLocal, UserIdentity
from voice.workflows.state_machine import StateManager

# Emmanuel Acho's telegram user ID (Manu A)
TELEGRAM_USER_ID = 5753848438
MESSAGE_ID_COUNTER = 1000

def create_telegram_update(text: str) -> dict:
    """Create a properly formatted Telegram update dict"""
    global MESSAGE_ID_COUNTER
    MESSAGE_ID_COUNTER += 1
    
    return {
        'update_id': MESSAGE_ID_COUNTER,
        'message': {
            'message_id': MESSAGE_ID_COUNTER,
            'from': {
                'id': TELEGRAM_USER_ID,
                'is_bot': False,
                'first_name': 'Manu',
                'last_name': 'A',
                'username': 'manu_test'
            },
            'chat': {
                'id': TELEGRAM_USER_ID,
                'type': 'private'
            },
            'date': int(time.time()),
            'text': text
        }
    }

async def send_message(message: str):
    """Simulate sending a Telegram message"""
    print(f"\n{'='*60}")
    print(f"📱 YOU: {message}")
    print(f"{'='*60}")
    
    update_data = create_telegram_update(message)
    result = await process_natural_text_query(update_data)
    
    print(f"🤖 BOT: {result.get('message', 'No response')}")
    
    if result.get('audio_url'):
        print(f"🔊 Audio: {result['audio_url']}")
    
    return result

async def test_batch_recording():
    """Test the batch recording workflow"""
    print("\n" + "="*60)
    print("TEST 1: Batch Recording Workflow")
    print("="*60)
    
    # Clear any existing state
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    # Step 1: Trigger batch recording
    await send_message("I want to record a new batch")
    await asyncio.sleep(1)
    
    # Step 2: Provide weight
    await send_message("50kg")
    await asyncio.sleep(1)
    
    # Step 3: Provide grade
    await send_message("Grade A")
    await asyncio.sleep(1)
    
    # Step 4: Skip notes
    await send_message("skip")
    await asyncio.sleep(1)
    
    # Step 5: Confirm
    await send_message("confirm")
    await asyncio.sleep(1)
    
    print("\n✅ Batch recording workflow completed!")

async def test_shipment_tracking():
    """Test the shipment tracking workflow"""
    print("\n" + "="*60)
    print("TEST 2: Shipment Tracking Workflow")
    print("="*60)
    
    # Clear any existing state
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    # Step 1: Trigger shipment tracking
    await send_message("track my shipments")
    await asyncio.sleep(1)
    
    # Step 2: Select first shipment
    await send_message("1")
    await asyncio.sleep(1)
    
    # Step 3: Ask about location
    await send_message("where is it?")
    await asyncio.sleep(1)
    
    # Step 4: Ask about ETA
    await send_message("when will it arrive?")
    await asyncio.sleep(1)
    
    # Step 5: Go back
    await send_message("back")
    await asyncio.sleep(1)
    
    print("\n✅ Shipment tracking workflow completed!")

async def test_workflow_cancellation():
    """Test canceling a workflow mid-conversation"""
    print("\n" + "="*60)
    print("TEST 3: Workflow Cancellation")
    print("="*60)
    
    # Clear state
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    # Start batch recording
    await send_message("record batch")
    await asyncio.sleep(1)
    
    # Cancel mid-flow
    await send_message("cancel")
    await asyncio.sleep(1)
    
    # Verify we can start something else
    await send_message("Hello, how are you?")
    
    print("\n✅ Cancellation test completed!")

async def test_alternative_phrases():
    """Test alternative trigger phrases"""
    print("\n" + "="*60)
    print("TEST 4: Alternative Trigger Phrases")
    print("="*60)
    
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    # Test alternative batch recording phrases
    print("\n--- Testing 'log batch' ---")
    await send_message("log batch")
    await asyncio.sleep(1)
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    print("\n--- Testing 'record harvest' ---")
    await send_message("record harvest")
    await asyncio.sleep(1)
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    print("\n--- Testing 'where is my coffee' ---")
    await send_message("where is my coffee")
    await asyncio.sleep(1)
    StateManager.clear_user_state(TELEGRAM_USER_ID)
    
    print("\n✅ Alternative phrases test completed!")

async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 LAB 20 TELEGRAM TESTING - Emmanuel Acho (Manu A)")
    print(f"   Telegram User ID: {TELEGRAM_USER_ID}")
    print("="*70)
    
    # Verify user exists
    db = SessionLocal()
    user = db.query(UserIdentity).filter(
        UserIdentity.telegram_user_id == str(TELEGRAM_USER_ID)
    ).first()
    
    if user:
        print(f"✅ User found: {user.telegram_first_name} {user.telegram_last_name}")
        print(f"   Phone: {user.phone_number}")
        print(f"   Language: {user.preferred_language}")
    else:
        print(f"❌ User not found in database!")
        db.close()
        return
    
    db.close()
    
    try:
        # Run tests
        await test_batch_recording()
        await test_shipment_tracking()
        await test_workflow_cancellation()
        await test_alternative_phrases()
        
        print("\n" + "="*70)
        print("🎉 ALL TELEGRAM TESTS COMPLETED!")
        print("="*70)
        print("\nNext steps:")
        print("  1. Check logs/voice_api.log for any errors")
        print("  2. Test with actual Telegram app messages")
        print("  3. Try Amharic language support")
        print("  4. Update TODO document")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        StateManager.clear_user_state(TELEGRAM_USER_ID)

if __name__ == "__main__":
    asyncio.run(main())
