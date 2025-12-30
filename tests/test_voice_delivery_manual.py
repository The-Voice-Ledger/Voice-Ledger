#!/usr/bin/env python3
"""
Manual Voice Delivery Test

Tests voice prioritization by sending messages via Telegram Bot API
and observing which responses include voice.

Run this script, then manually check your Telegram to see which messages
have voice attachments.
"""

import os
import asyncio
import sys
from telegram import Bot
from telegram.error import TelegramError

# Environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TEST_USER_ID = int(os.getenv('TELEGRAM_USER_ID', '1299597653'))

async def send_test_message(bot: Bot, user_id: int, text: str):
    """Send a text message to trigger bot responses"""
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text
        )
        print(f"✅ Sent: {text}")
        return True
    except TelegramError as e:
        print(f"❌ Failed to send message: {e}")
        return False

async def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment")
        sys.exit(1)
    
    bot = Bot(token=BOT_TOKEN)
    
    print("="*70)
    print("🚀 VOICE DELIVERY TEST")
    print("="*70)
    print()
    print("This test will send text messages to your bot to trigger")
    print("the RFQ creation flow. Check which responses have voice.")
    print()
    print(f"📱 Messages will be sent to Telegram ID: {TEST_USER_ID}")
    print()
    print("="*70)
    print()
    
    # Test 1: Start RFQ Flow
    print("\n🧪 TEST 1: RFQ Creation")
    print("="*70)
    print()
    print("Sending initial RFQ command...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "I want to buy 1000 kilograms of Sidama coffee"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ❌ 'Voice received' → NO voice (system notification)")
    print("   ❌ 'Task ID' → NO voice (system notification)")
    print("   ❌ 'RFQ Preview' → NO voice (data display)")
    print("   ✅ Menu buttons shown")
    print()
    print("⏳ Click a menu option or wait 30 seconds...")
    
    await asyncio.sleep(30)
    
    # Test 2: Multi-turn clarification
    print("\n🧪 TEST 2: Multi-turn Clarification")
    print("="*70)
    print()
    print("Sending answer: 'Grade 1'...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "Grade 1"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ✅ Next question → WITH voice (conversational)")
    print()
    print("⏳ Waiting 10 seconds...")
    
    await asyncio.sleep(10)
    
    # Test 3: Continue flow
    print("\n🧪 TEST 3: Processing Method")
    print("="*70)
    print()
    print("Sending answer: 'Washed'...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "Washed"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ✅ Next question → WITH voice (conversational)")
    print()
    print("⏳ Waiting 10 seconds...")
    
    await asyncio.sleep(10)
    
    # Test 4: Location
    print("\n🧪 TEST 4: Delivery Location")
    print("="*70)
    print()
    print("Sending answer: 'Djibouti'...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "Djibouti"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ✅ Next question → WITH voice (conversational)")
    print()
    print("⏳ Waiting 10 seconds...")
    
    await asyncio.sleep(10)
    
    # Test 5: Deadline
    print("\n🧪 TEST 5: Delivery Deadline")
    print("="*70)
    print()
    print("Sending answer: '30 days'...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "30 days"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ✅ Summary → WITH voice (conversational)")
    print("   ✅ Confirmation prompt → WITH voice")
    print()
    print("⏳ Waiting 10 seconds...")
    
    await asyncio.sleep(10)
    
    # Test 6: Confirmation
    print("\n🧪 TEST 6: Confirmation")
    print("="*70)
    print()
    print("Sending answer: 'yes ready to broadcast'...")
    
    await send_test_message(
        bot,
        TEST_USER_ID,
        "yes ready to broadcast"
    )
    
    print()
    print("✅ Message sent!")
    print()
    print("📱 Check your Telegram bot now. Expected:")
    print("   ✅ Confirmation accepted (not cancelled!)")
    print("   ✅ Success message → WITH voice")
    print("   ✅ Broadcast count shown")
    print()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETE")
    print("="*70)
    print()
    print("🔍 VALIDATION CHECKLIST:")
    print()
    print("System Notifications (NO VOICE):")
    print("   ❌ 'Voice received! Processing...'")
    print("   ❌ 'Task ID: ...'")
    print("   ❌ 'RFQ Preview' with extracted data")
    print()
    print("Conversational Content (WITH VOICE):")
    print("   ✅ 'What grade are you looking for?'")
    print("   ✅ 'Which processing method?'")
    print("   ✅ 'Where should it be delivered?'")
    print("   ✅ 'When do you need it delivered?'")
    print("   ✅ 'Please review and confirm'")
    print("   ✅ 'RFQ successfully broadcasted'")
    print()
    print("Confirmation Acceptance:")
    print("   ✅ 'yes ready to broadcast' should be accepted (not cancelled)")
    print()

if __name__ == "__main__":
    asyncio.run(main())
