"""
Test dual delivery (text + voice) for Telegram responses.

This script tests the TrustVoice pattern implementation.
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
sys.path.insert(0, os.path.dirname(__file__))


async def test_dual_delivery():
    """Test dual delivery (text + voice) to Telegram."""
    
    logger.info("=" * 60)
    logger.info("Testing Telegram Dual Delivery (Text + Voice)")
    logger.info("=" * 60)
    
    # Get test chat ID from environment
    test_chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID")
    
    if not test_chat_id:
        logger.error("❌ TEST_TELEGRAM_CHAT_ID not set in .env")
        logger.info("Add your Telegram chat ID to .env:")
        logger.info("TEST_TELEGRAM_CHAT_ID=your_chat_id_here")
        logger.info("")
        logger.info("To get your chat ID, send a message to your bot and check:")
        logger.info("https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates")
        return False
    
    try:
        # Initialize Telegram channel
        from voice.channels.telegram_channel import TelegramChannel
        
        channel = TelegramChannel()
        logger.info(f"✅ Telegram channel initialized")
        
        # Test 1: English text + voice
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: English Dual Delivery")
        logger.info("=" * 60)
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message="✅ Hello! This is a test of dual delivery. You should receive both text and voice.",
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 1 PASSED: English message sent")
            logger.info("   Check Telegram: Text should arrive immediately, voice in ~2 seconds")
        else:
            logger.error("❌ TEST 1 FAILED: Failed to send English message")
            return False
        
        # Wait a bit for voice to generate
        await asyncio.sleep(3)
        
        # Test 2: Amharic text + voice
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Amharic Dual Delivery")
        logger.info("=" * 60)
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message="✅ ሰላም! ይህ የድርብ ትምህርት ሙከራ ነው። ጽሑፍ እና ድምጽ መቀበል አለብዎት።",
            parse_mode="HTML",
            send_voice=True,
            language="am"  # Force Amharic
        )
        
        if success:
            logger.info("✅ TEST 2 PASSED: Amharic message sent")
            logger.info("   Check Telegram: Text should arrive immediately, voice in ~2 seconds")
        else:
            logger.error("❌ TEST 2 FAILED: Failed to send Amharic message")
            return False
        
        # Wait for voice
        await asyncio.sleep(3)
        
        # Test 3: Text-only (disable voice)
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Text-Only (Voice Disabled)")
        logger.info("=" * 60)
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message="📝 This is a text-only message (voice disabled for testing).",
            parse_mode="HTML",
            send_voice=False  # Disable voice
        )
        
        if success:
            logger.info("✅ TEST 3 PASSED: Text-only message sent")
            logger.info("   Check Telegram: Only text should arrive")
        else:
            logger.error("❌ TEST 3 FAILED: Failed to send text-only message")
            return False
        
        await asyncio.sleep(2)
        
        # Test 4: Long message with formatting
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: Long Message with Formatting")
        logger.info("=" * 60)
        
        long_message = """
✅ <b>Batch Recorded Successfully!</b>

Batch Number: <code>BATCH-001</code>
Quantity: 50 kg
Quality: Grade A
Price: 450 ETB/kg

Your coffee batch has been recorded in the system. 
You can track it using the batch number above.

Thank you for using Voice Ledger! 🎉
"""
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=long_message.strip(),
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 4 PASSED: Long formatted message sent")
            logger.info("   Check Telegram: HTML formatting should work, voice should be clean")
        else:
            logger.error("❌ TEST 4 FAILED: Failed to send long message")
            return False
        
        await asyncio.sleep(3)
        
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Expected behavior:")
        logger.info("1. Text messages arrive immediately")
        logger.info("2. Voice messages follow ~2 seconds later")
        logger.info("3. Voice messages reply to text messages (threaded)")
        logger.info("4. HTML formatting removed in voice synthesis")
        logger.info("")
        logger.info("Check your Telegram to verify dual delivery works correctly!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_dual_delivery())
    sys.exit(0 if success else 1)
