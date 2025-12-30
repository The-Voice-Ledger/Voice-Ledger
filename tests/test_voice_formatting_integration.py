"""
Integration Test: Voice Formatting in Dual Delivery

Tests that format_for_voice() is properly integrated into the TTS pipeline
and produces more natural-sounding voice messages.
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


async def test_voice_formatting_integration():
    """Test that voice formatting is applied in real dual delivery."""
    
    logger.info("=" * 60)
    logger.info("Voice Formatting Integration Test")
    logger.info("=" * 60)
    
    # Get test chat ID from environment
    test_chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID")
    
    if not test_chat_id:
        logger.error("❌ TEST_TELEGRAM_CHAT_ID not set in .env")
        logger.info("Add your Telegram chat ID to .env:")
        logger.info("TEST_TELEGRAM_CHAT_ID=your_chat_id_here")
        return False
    
    try:
        # Initialize Telegram channel
        from voice.channels.telegram_channel import TelegramChannel
        
        channel = TelegramChannel()
        logger.info(f"✅ Telegram channel initialized")
        
        # Test 1: Batch confirmation with mixed formatting
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Batch Confirmation with Currency and Units")
        logger.info("=" * 60)
        
        message1 = "✅ Batch ABC-123 recorded: 50kg of Arabica coffee for $450 (Grade A, 95% quality)"
        
        logger.info(f"Original message: {message1}")
        logger.info("Expected voice: '50 kilograms', '450 dollars', '95 percent'")
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=message1,
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 1 sent - Check voice for natural pronunciation")
        else:
            logger.error("❌ TEST 1 FAILED")
            return False
        
        await asyncio.sleep(3)
        
        # Test 2: Payment notification with Ethiopian Birr
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Payment with Ethiopian Birr")
        logger.info("=" * 60)
        
        message2 = "💰 Payment received: 1500 ETB for 10kg. This is your 2nd payment today."
        
        logger.info(f"Original message: {message2}")
        logger.info("Expected voice: '1500 birr', '10 kilograms', 'second payment'")
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=message2,
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 2 sent - Check voice for 'birr' and 'second'")
        else:
            logger.error("❌ TEST 2 FAILED")
            return False
        
        await asyncio.sleep(3)
        
        # Test 3: Ranking with ordinals
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Ranking with Ordinals")
        logger.info("=" * 60)
        
        message3 = "🏆 Your batch is ranked 5th out of 20 submissions with 88% quality score."
        
        logger.info(f"Original message: {message3}")
        logger.info("Expected voice: 'fifth', 'twenty', '88 percent'")
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=message3,
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 3 sent - Check voice for 'fifth' instead of '5th'")
        else:
            logger.error("❌ TEST 3 FAILED")
            return False
        
        await asyncio.sleep(3)
        
        # Test 4: Shipment with small numbers
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: Small Numbers in Context")
        logger.info("=" * 60)
        
        message4 = "📦 Shipment of 3 batches totaling 150kg arrived. You have 1 pending verification."
        
        logger.info(f"Original message: {message4}")
        logger.info("Expected voice: 'three batches', '150 kilograms', 'one pending'")
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=message4,
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 4 sent - Check voice for 'three' and 'one'")
        else:
            logger.error("❌ TEST 4 FAILED")
            return False
        
        await asyncio.sleep(3)
        
        # Test 5: Complex message with HTML formatting
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: Complex HTML Message")
        logger.info("=" * 60)
        
        message5 = """✅ <b>Transaction Complete</b>

Batch: <code>ABEBE-2025-001</code>
Amount: 75kg @ $8.50/kg = $637.50
Quality: 92%
Status: 1st in queue

Your 3rd successful transaction this month!"""
        
        logger.info(f"Original message (with HTML):")
        logger.info(message5)
        logger.info("Expected voice: HTML stripped, '75 kilograms', '637.50 dollars', '92 percent', 'first in queue', 'third successful'")
        
        success = await channel.send_notification(
            user_id=test_chat_id,
            message=message5,
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ TEST 5 sent - Check voice for complex formatting")
        else:
            logger.error("❌ TEST 5 FAILED")
            return False
        
        await asyncio.sleep(3)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION TEST COMPLETE")
        logger.info("=" * 60)
        logger.info("\n✅ All 5 test messages sent successfully!")
        logger.info("\nPlease verify in Telegram that voice messages sound natural:")
        logger.info("  ✓ Currency symbols spoken as words (dollars, euros, birr)")
        logger.info("  ✓ Units spelled out (kilograms, percent)")
        logger.info("  ✓ Ordinals as words (first, second, third)")
        logger.info("  ✓ Small numbers spelled out (one, two, three)")
        logger.info("  ✓ Batch IDs and codes preserved")
        logger.info("  ✓ HTML formatting removed from voice")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_voice_formatting_integration())
    sys.exit(0 if success else 1)
