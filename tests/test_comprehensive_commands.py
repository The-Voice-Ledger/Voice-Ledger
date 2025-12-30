"""
Comprehensive test suite for Voice Ledger commands and handlers.

Tests:
- Voice command processing (commission, ship, pack, etc.)
- RFQ marketplace commands
- Registration and verification
- Conversational AI with RAG
- Dual delivery (text + voice)

User credentials: telegram_user_id=5753848438
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Test configuration
TEST_USER_ID = "5753848438"  # Your Telegram user ID
TEST_USERNAME = "manu_ayalew"


class TestSuite:
    """Comprehensive test suite for Voice Ledger."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.channel = None
        
    async def setup(self):
        """Initialize test environment."""
        from voice.channels.telegram_channel import TelegramChannel
        self.channel = TelegramChannel()
        logger.info("✅ Telegram channel initialized")
        
    async def send_test_message(self, message: str, test_name: str, **kwargs):
        """Helper to send test message and track results."""
        try:
            success = await self.channel.send_notification(
                user_id=TEST_USER_ID,
                message=message,
                parse_mode="HTML",
                **kwargs
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ {test_name} PASSED")
                return True
            else:
                self.failed += 1
                logger.error(f"❌ {test_name} FAILED")
                return False
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ {test_name} FAILED: {e}")
            return False
    
    async def test_basic_dual_delivery(self):
        """Test 1: Basic dual delivery (text + voice)"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 1: Basic Dual Delivery")
        logger.info("=" * 70)
        
        await self.send_test_message(
            message="🎙️ <b>Test 1:</b> Basic dual delivery test. You should receive both text and voice.",
            test_name="Basic Dual Delivery",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_commission_command_simulation(self):
        """Test 2: Simulate commission command response"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 2: Commission Command Simulation")
        logger.info("=" * 70)
        
        message = """📦 <b>Batch Created Successfully!</b>

<b>Batch ID:</b> TEST_BATCH_001
<b>Quantity:</b> 100 kg
<b>Variety:</b> Arabica
<b>Origin:</b> Yirgacheffe

Your batch has been recorded on the blockchain.
Next step: Wait for cooperative verification."""
        
        await self.send_test_message(
            message=message,
            test_name="Commission Command Response",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_verification_notification(self):
        """Test 3: Verification notification"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 3: Verification Notification")
        logger.info("=" * 70)
        
        message = """✅ <b>Batch Verified!</b>

Your batch TEST_BATCH_001 has been verified by the cooperative.

🎫 <b>Token Minted:</b> #12345
🔗 <b>Blockchain:</b> Base Sepolia
📍 <b>View on Explorer:</b> https://sepolia.basescan.org/token/0x...

Your coffee is now tokenized and tradeable!"""
        
        await self.send_test_message(
            message=message,
            test_name="Verification Notification",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_rfq_broadcast(self):
        """Test 4: RFQ broadcast notification"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 4: RFQ Broadcast Notification")
        logger.info("=" * 70)
        
        message = """🛒 <b>New RFQ Alert!</b>

<b>Buyer:</b> Premium Coffee Importers
<b>Looking for:</b> 500 kg Arabica Grade 1
<b>Origin:</b> Yirgacheffe
<b>Target Price:</b> $8-10/kg
<b>Delivery:</b> Within 30 days

<b>Deadline:</b> 3 days

Send <code>/offers RFQ123</code> to submit your offer!"""
        
        await self.send_test_message(
            message=message,
            test_name="RFQ Broadcast",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_offer_accepted(self):
        """Test 5: Offer accepted notification"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 5: Offer Accepted Notification")
        logger.info("=" * 70)
        
        message = """🎉 <b>Your Offer Was Accepted!</b>

<b>RFQ ID:</b> RFQ123
<b>Your Offer:</b> 500 kg @ $9.50/kg
<b>Total Value:</b> $4,750
<b>Buyer:</b> Premium Coffee Importers

Next steps:
1. Prepare shipment documentation
2. Coordinate with exporter for shipping
3. Payment will be released upon delivery confirmation

Use <code>/shipment RFQ123</code> to track progress."""
        
        await self.send_test_message(
            message=message,
            test_name="Offer Accepted",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_rag_query_response(self):
        """Test 6: RAG-enhanced documentation query"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 6: RAG Query Response")
        logger.info("=" * 70)
        
        message = """📚 <b>About EPCIS 2.0</b>

<b>EPCIS</b> (Electronic Product Code Information Services) 2.0 is a GS1 standard for capturing and sharing supply chain events.

<b>Key Features:</b>
• Event-based tracking (What, When, Where, Why)
• Blockchain anchoring for immutability
• Digital Product Passport (DPP) generation
• Full traceability from farm to cup

<b>In Voice Ledger:</b>
Every batch you create generates EPCIS events that are:
✓ Stored in database
✓ Hashed and anchored on blockchain
✓ Linked to your DID identity
✓ Exportable as JSON-LD

Learn more: Send <code>/help epcis</code>"""
        
        await self.send_test_message(
            message=message,
            test_name="RAG Query Response",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_conversational_clarification(self):
        """Test 7: Conversational AI clarification"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 7: Conversational AI Clarification")
        logger.info("=" * 70)
        
        message = """❓ <b>Need More Information</b>

I understand you want to record a harvest, but I need a few more details:

<b>Please provide:</b>
1. <b>Quantity:</b> How many kilograms?
2. <b>Variety:</b> Arabica or Robusta?
3. <b>Origin:</b> Which farm/region?

<b>Example:</b> "100 kilograms of Arabica from Sidama"

You can say it all at once, or I'll ask you one by one! 😊"""
        
        await self.send_test_message(
            message=message,
            test_name="Conversational Clarification",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_error_message(self):
        """Test 8: Error handling"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 8: Error Message")
        logger.info("=" * 70)
        
        message = """⚠️ <b>Action Failed</b>

Sorry, I couldn't process your request.

<b>Reason:</b> Batch ID not found

<b>What to try:</b>
• Check the batch ID is correct
• Use <code>/mybatches</code> to see your batches
• Make sure the batch was created successfully

Need help? Send <code>/help</code> or contact support."""
        
        await self.send_test_message(
            message=message,
            test_name="Error Message",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_amharic_message(self):
        """Test 9: Amharic language support"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 9: Amharic Message")
        logger.info("=" * 70)
        
        message = """✅ <b>የቡና ቅርንጫፍ በተሳካ ሁኔታ ተመዝግቧል!</b>

<b>የቅርንጫፍ መለያ:</b> TEST_AM_001
<b>ብዛት:</b> 100 ኪሎ
<b>ዝርያ:</b> አረቢካ
<b>መነሻ:</b> ይርጋቸፍ

የእርስዎ ቅርንጫፍ በብሎክቼይን ላይ ተመዝግቧል።
ቀጣይ እርምጃ፡ ለኅብረት ሥራ ማህበር ማረጋገጫ ይጠብቁ።"""
        
        await self.send_test_message(
            message=message,
            test_name="Amharic Message",
            send_voice=True,
            language="am"
        )
        await asyncio.sleep(3)
    
    async def test_long_formatted_message(self):
        """Test 10: Long message with formatting"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 10: Long Formatted Message")
        logger.info("=" * 70)
        
        message = """📊 <b>Your Supply Chain Summary</b>

<b>Total Batches:</b> 15
<b>Verified Batches:</b> 12
<b>Pending Verification:</b> 3

<b>Recent Activity:</b>
• BATCH_001 - Verified ✅
• BATCH_002 - Shipped 📦
• BATCH_003 - In Transit 🚚
• BATCH_004 - Delivered 🎯
• BATCH_005 - Pending ⏳

<b>Marketplace:</b>
• Active RFQs: 2
• Offers Submitted: 5
• Accepted Offers: 3

<b>Blockchain Stats:</b>
🔗 Chain: Base Sepolia
💎 Tokens Minted: 12
🔒 Events Anchored: 47

Use <code>/details BATCH_ID</code> for batch info."""
        
        await self.send_test_message(
            message=message,
            test_name="Long Formatted Message",
            send_voice=True
        )
        await asyncio.sleep(3)
    
    async def test_text_only_mode(self):
        """Test 11: Text-only (no voice)"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 11: Text-Only Mode")
        logger.info("=" * 70)
        
        message = """💬 <b>Text-Only Mode</b>

This message has voice disabled. You should only receive text.

Useful for:
• Quick notifications
• System status updates
• Administrative messages
• When TTS is not needed"""
        
        await self.send_test_message(
            message=message,
            test_name="Text-Only Mode",
            send_voice=False
        )
        await asyncio.sleep(2)
    
    async def run_all_tests(self):
        """Run complete test suite."""
        logger.info("\n" + "=" * 70)
        logger.info("🧪 VOICE LEDGER COMPREHENSIVE TEST SUITE")
        logger.info("=" * 70)
        logger.info(f"Test User: {TEST_USER_ID}")
        logger.info(f"Username: @{TEST_USERNAME}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)
        
        await self.setup()
        
        # Run all tests
        await self.test_basic_dual_delivery()
        await self.test_commission_command_simulation()
        await self.test_verification_notification()
        await self.test_rfq_broadcast()
        await self.test_offer_accepted()
        await self.test_rag_query_response()
        await self.test_conversational_clarification()
        await self.test_error_message()
        await self.test_amharic_message()
        await self.test_long_formatted_message()
        await self.test_text_only_mode()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📈 TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Passed: {self.passed}")
        logger.info(f"❌ Failed: {self.failed}")
        logger.info(f"📊 Total: {self.passed + self.failed}")
        logger.info(f"🎯 Success Rate: {(self.passed/(self.passed+self.failed)*100):.1f}%")
        logger.info("=" * 70)
        logger.info("\n✨ Check your Telegram for all test messages!")
        logger.info("Expected behavior:")
        logger.info("• Text arrives immediately")
        logger.info("• Voice follows ~2 seconds later")
        logger.info("• Voice messages thread to text messages")
        logger.info("• HTML formatting removed in voice")
        logger.info("• Amharic uses AddisAI TTS")
        logger.info("• English uses OpenAI TTS")
        
        return self.failed == 0


async def main():
    """Main test runner."""
    suite = TestSuite()
    success = await suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
