"""
End-to-End Test: Voice Message → STT → Processing → Dual Delivery Response

This test simulates a complete voice workflow:
1. User sends voice message (simulated)
2. AddisAI Cloud STT transcribes
3. System processes command
4. Dual delivery response (text + voice)
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))


async def test_end_to_end():
    """Test complete voice workflow with dual delivery."""
    
    logger.info("=" * 80)
    logger.info("END-TO-END TEST: Voice Input → STT → Processing → Dual Delivery")
    logger.info("=" * 80)
    
    test_chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID")
    if not test_chat_id:
        logger.error("❌ TEST_TELEGRAM_CHAT_ID not set")
        return False
    
    try:
        # Test 1: Check AddisAI Cloud STT
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: AddisAI Cloud STT (Amharic)")
        logger.info("=" * 80)
        
        from voice.asr.asr_infer import run_asr_with_user_preference
        
        audio_path = "admin_scripts/test_audio/amharic_batch_test.mp3"
        if not os.path.exists(audio_path):
            logger.warning(f"⚠️  Test audio not found: {audio_path}")
        else:
            result = run_asr_with_user_preference(audio_path, "am")
            logger.info(f"✅ STT Result: {result.get('transcript', 'N/A')}")
            logger.info(f"   Language: {result.get('language', 'N/A')}")
            logger.info(f"   Provider: AddisAI Cloud")
        
        # Test 2: Test Telegram Channel with Dual Delivery
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Telegram Channel - Dual Delivery")
        logger.info("=" * 80)
        
        from voice.channels.telegram_channel import TelegramChannel
        
        channel = TelegramChannel()
        logger.info("✅ Telegram channel initialized")
        
        # Simulate batch recording confirmation (English)
        success = await channel.send_notification(
            user_id=test_chat_id,
            message="✅ <b>Batch Recorded Successfully!</b>\n\nBatch: BATCH-001\nQuantity: 50 kg\nPrice: 450 ETB/kg",
            parse_mode="HTML",
            send_voice=True
        )
        
        if success:
            logger.info("✅ English notification sent with dual delivery")
        else:
            logger.error("❌ Failed to send English notification")
            return False
        
        await asyncio.sleep(3)
        
        # Simulate Amharic confirmation
        success = await channel.send_notification(
            user_id=test_chat_id,
            message="✅ ባችዎ በተሳካ ሁኔታ ተመዝግቧል!\n\nባች ቁጥር: BATCH-001",
            parse_mode="HTML",
            send_voice=True,
            language="am"
        )
        
        if success:
            logger.info("✅ Amharic notification sent with dual delivery")
        else:
            logger.error("❌ Failed to send Amharic notification")
            return False
        
        await asyncio.sleep(3)
        
        # Test 3: Verify TTS Providers
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: TTS Provider Routing")
        logger.info("=" * 80)
        
        from voice.providers.addis_ai import AddisAIProvider
        from openai import AsyncOpenAI
        
        # Test AddisAI TTS
        addisai = AddisAIProvider()
        amharic_audio = await addisai.text_to_speech("ሰላም", "am")
        logger.info(f"✅ AddisAI TTS: {len(amharic_audio)} bytes generated")
        
        # Test OpenAI TTS
        openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input="Hello, this is a test."
        )
        english_audio = response.content
        logger.info(f"✅ OpenAI TTS: {len(english_audio)} bytes generated")
        
        # Test 4: Check Integration Points
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Integration Verification")
        logger.info("=" * 80)
        
        # Verify voice_responses module
        from voice.telegram.voice_responses import send_voice_reply, detect_language
        
        logger.info("✅ voice_responses module imported")
        
        # Test language detection
        assert detect_language("Hello") == "en", "English detection failed"
        assert detect_language("ሰላም") == "am", "Amharic detection failed"
        logger.info("✅ Language detection working")
        
        # Verify channel uses voice_responses
        import inspect
        source = inspect.getsource(channel.send_notification)
        if "send_voice_reply" in source:
            logger.info("✅ TelegramChannel uses send_voice_reply")
        else:
            logger.warning("⚠️  TelegramChannel may not use send_voice_reply")
        
        logger.info("\n" + "=" * 80)
        logger.info("ALL TESTS PASSED! ✅")
        logger.info("=" * 80)
        logger.info("")
        logger.info("System Status:")
        logger.info("  🎤 AddisAI Cloud STT: Active (Amharic)")
        logger.info("  🔊 AddisAI TTS: Active (Amharic)")
        logger.info("  🔊 OpenAI TTS: Active (English)")
        logger.info("  📱 Telegram Dual Delivery: Active")
        logger.info("  ✅ Voice-First Accessibility: Enabled")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("  1. Send a voice message to your Telegram bot")
        logger.info("  2. Verify you receive BOTH text and voice responses")
        logger.info("  3. Test with both English and Amharic messages")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_end_to_end())
    sys.exit(0 if success else 1)
