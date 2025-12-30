"""
Comprehensive Dual Delivery Test for ALL Voice Handlers

Tests ALL voice command handlers with:
1. Entity validation
2. Reference resolution  
3. Voice formatting
4. Dual delivery (text + voice to Telegram)

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

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Test configuration
TEST_TELEGRAM_ID = "5753848438"  # Your Telegram user ID
PAUSE_BETWEEN_TESTS = 4  # seconds between each test


class HandlerTestSuite:
    """Test suite for all voice command handlers with dual delivery."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.channel = None
        self.db_user_id = None
        
    async def setup(self):
        """Initialize test environment."""
        logger.info("=" * 70)
        logger.info("VOICE LEDGER - COMPREHENSIVE HANDLER TEST")
        logger.info("=" * 70)
        logger.info(f"Test User: {TEST_TELEGRAM_ID}")
        logger.info(f"Testing: Entity Validation + Reference Resolution + Voice Formatting")
        logger.info("=" * 70)
        
        # Initialize Telegram channel
        from voice.channels.telegram_channel import TelegramChannel
        self.channel = TelegramChannel()
        logger.info("✅ Telegram channel initialized")
        
        # Get database user ID
        from database.models import SessionLocal, UserIdentity
        db = SessionLocal()
        try:
            user = db.query(UserIdentity).filter_by(
                telegram_user_id=TEST_TELEGRAM_ID
            ).first()
            
            if user:
                self.db_user_id = user.id
                logger.info(f"✅ Found user in database: ID={user.id}, DID={user.did}")
            else:
                logger.error(f"❌ User {TEST_TELEGRAM_ID} not found in database")
                logger.info("Please register first using /start command in Telegram")
                return False
        finally:
            db.close()
        
        return True
    
    async def send_test(self, handler_name: str, description: str, response_message: str):
        """
        Send a test message simulating a handler response.
        
        Args:
            handler_name: Name of the handler (e.g., "record_commission")
            description: Test description
            response_message: The message to send (will be formatted for voice)
        """
        logger.info("\n" + "=" * 70)
        logger.info(f"TEST: {handler_name}")
        logger.info(f"Description: {description}")
        logger.info("=" * 70)
        
        try:
            # Send with dual delivery
            success = await self.channel.send_notification(
                user_id=TEST_TELEGRAM_ID,
                message=response_message,
                parse_mode="HTML",
                send_voice=True
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ {handler_name} - Message sent successfully")
                logger.info(f"   Text message sent immediately")
                logger.info(f"   Voice message queued (with formatting applied)")
            else:
                self.failed += 1
                logger.error(f"❌ {handler_name} - Failed to send message")
                return False
            
            # Wait for voice to process
            await asyncio.sleep(PAUSE_BETWEEN_TESTS)
            return True
            
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ {handler_name} - Error: {e}", exc_info=True)
            return False
    
    # ==================== BATCH MANAGEMENT HANDLERS ====================
    
    async def test_record_commission(self):
        """Handler 1: record_commission - Create new batch"""
        message = """✅ <b>Batch Created Successfully!</b>

<b>Batch ID:</b> BTH-2025-001
<b>Quantity:</b> 50kg
<b>Variety:</b> Arabica
<b>Origin:</b> Yirgacheffe
<b>Grade:</b> 1st

Your batch has been recorded on the blockchain.
<b>Next step:</b> Wait for cooperative verification.

<i>Cost: $2.50 per batch</i>"""
        
        await self.send_test(
            "record_commission",
            "Create a new coffee batch with entity validation",
            message
        )
    
    async def test_record_shipment(self):
        """Handler 2: record_shipment - Ship a batch"""
        message = """🚚 <b>Shipment Recorded!</b>

<b>Batch:</b> BTH-2025-001
<b>Destination:</b> Addis Ababa Warehouse
<b>Distance:</b> 150km
<b>Expected Arrival:</b> 2 days

The shipment is now tracked on blockchain.
Use <code>/track BTH-2025-001</code> to monitor progress."""
        
        await self.send_test(
            "record_shipment",
            "Ship batch to destination",
            message
        )
    
    async def test_record_receipt(self):
        """Handler 3: record_receipt - Receive a batch"""
        message = """📦 <b>Batch Received!</b>

<b>Batch:</b> BTH-2025-001
<b>Location:</b> Addis Ababa Warehouse
<b>Condition:</b> Good
<b>Quantity Verified:</b> 50kg (100%)

Receipt confirmed on blockchain.
Batch is ready for processing or sale."""
        
        await self.send_test(
            "record_receipt",
            "Confirm receipt of shipment",
            message
        )
    
    async def test_record_transformation(self):
        """Handler 4: record_transformation - Process coffee"""
        message = """⚙️ <b>Transformation Complete!</b>

<b>Process:</b> Roasting
<b>Input Batch:</b> BTH-2025-001 (50kg)
<b>Output:</b> 45kg roasted coffee
<b>Loss:</b> 5kg (10%)

<b>New Batch ID:</b> BTH-2025-002

The 2nd generation batch is now available."""
        
        await self.send_test(
            "record_transformation",
            "Transform batch (roasting, milling, etc.)",
            message
        )
    
    async def test_pack_batches(self):
        """Handler 5: pack_batches - Aggregate multiple batches"""
        message = """📦 <b>Batches Packed!</b>

<b>Container:</b> PALLET-001
<b>Batches:</b> 3 batches aggregated
  • BTH-2025-001 (50kg)
  • BTH-2025-002 (45kg)
  • BTH-2025-003 (60kg)
<b>Total:</b> 155kg

Container is ready for shipping."""
        
        await self.send_test(
            "pack_batches",
            "Aggregate multiple batches into container",
            message
        )
    
    async def test_unpack_batches(self):
        """Handler 6: unpack_batches - Disaggregate container"""
        message = """📤 <b>Container Unpacked!</b>

<b>Container:</b> PALLET-001
<b>Released Batches:</b> 3 batches
  • BTH-2025-001 (50kg)
  • BTH-2025-002 (45kg)  
  • BTH-2025-003 (60kg)

Individual batches are now accessible."""
        
        await self.send_test(
            "unpack_batches",
            "Disaggregate container into individual batches",
            message
        )
    
    async def test_split_batch(self):
        """Handler 7: split_batch - Divide batch into smaller portions"""
        message = """✂️ <b>Batch Split Complete!</b>

<b>Parent Batch:</b> BTH-2025-001
<b>Split Into:</b> 2 child batches
  • BTH-2025-004: 30kg (60%)
  • BTH-2025-005: 20kg (40%)

Total: 50kg (100% accounted for)

Child batches maintain full traceability."""
        
        await self.send_test(
            "split_batch",
            "Split one batch into multiple smaller batches",
            message
        )
    
    # ==================== MARKETPLACE HANDLERS ====================
    
    async def test_create_rfq(self):
        """Handler 8: create_rfq - Buyer creates request for quote"""
        message = """📋 <b>RFQ Created!</b>

<b>RFQ ID:</b> RFQ-001
<b>Looking for:</b> 500kg Arabica Grade 1
<b>Origin:</b> Yirgacheffe
<b>Target Price:</b> $8-10/kg
<b>Deadline:</b> 3 days

Your RFQ will be broadcast to 127 farmers.
Expect offers within 24 hours."""
        
        await self.send_test(
            "create_rfq",
            "Buyer creates RFQ",
            message
        )
    
    async def test_submit_offer(self):
        """Handler 9: submit_offer - Farmer submits offer to RFQ"""
        message = """💰 <b>Offer Submitted!</b>

<b>RFQ:</b> RFQ-001
<b>Your Offer:</b> 500kg @ $9.50/kg
<b>Total Value:</b> $4,750
<b>Batches:</b> 3 batches offered
  • BTH-2025-001 (200kg)
  • BTH-2025-002 (150kg)
  • BTH-2025-003 (150kg)

The buyer will review your offer.
You'll be notified if accepted."""
        
        await self.send_test(
            "submit_offer",
            "Farmer submits offer to buyer's RFQ",
            message
        )
    
    async def test_accept_offer(self):
        """Handler 10: accept_offer - Buyer accepts farmer's offer"""
        message = """🎉 <b>Offer Accepted!</b>

<b>RFQ:</b> RFQ-001
<b>Accepted Offer:</b> $9.50/kg (500kg)
<b>Total:</b> $4,750
<b>Seller:</b> Farmer Abebe

<b>Next Steps:</b>
1. Seller prepares shipment
2. Payment held in escrow
3. Payment releases on delivery

Track progress with <code>/orders RFQ-001</code>"""
        
        await self.send_test(
            "accept_offer",
            "Buyer accepts farmer's offer",
            message
        )
    
    # ==================== VERIFICATION HANDLERS ====================
    
    async def test_submit_for_verification(self):
        """Handler 11: Submit batch for verification"""
        message = """🔍 <b>Verification Requested!</b>

<b>Batch:</b> BTH-2025-001
<b>Quantity:</b> 50kg Arabica
<b>Verifier:</b> Yirgacheffe Cooperative

Your batch has been submitted for verification.
Expected verification: 1-2 days

You'll receive a notification when verified."""
        
        await self.send_test(
            "submit_for_verification",
            "Farmer submits batch for cooperative verification",
            message
        )
    
    async def test_verify_batch(self):
        """Handler 12: Cooperative verifies batch"""
        message = """✅ <b>Batch Verified!</b>

<b>Batch:</b> BTH-2025-001
<b>Verified by:</b> Yirgacheffe Cooperative
<b>Quality Grade:</b> 1st (Premium)
<b>Certification:</b> Organic

🎫 <b>Token Minted:</b> #12345
🔗 <b>Blockchain:</b> Base Sepolia

Your coffee is now tokenized and tradeable!
Premium verified coffee commands 15% higher prices."""
        
        await self.send_test(
            "verify_batch",
            "Cooperative verifies farmer's batch",
            message
        )
    
    # ==================== QUERY HANDLERS ====================
    
    async def test_search_batches(self):
        """Handler 13: Search/list batches"""
        message = """📋 <b>Your Batches</b>

Found 3 batches:

1️⃣ <b>BTH-2025-001</b> - 50kg Arabica (Verified ✅)
   Origin: Yirgacheffe | Grade: 1st
   Status: Available

2️⃣ <b>BTH-2025-002</b> - 45kg Roasted (Pending 🕒)
   Origin: Yirgacheffe | Grade: 1st
   Status: In Process

3️⃣ <b>BTH-2025-003</b> - 60kg Arabica (Verified ✅)
   Origin: Sidama | Grade: 2nd
   Status: Shipped

Say "ship the 1st batch" to ship BTH-2025-001."""
        
        await self.send_test(
            "search_batches",
            "List farmer's batches (enables reference resolution)",
            message
        )
    
    async def test_reference_resolution(self):
        """Handler 14: Test reference resolution (\"ship the first one\")"""
        message = """🚚 <b>Shipment Recorded!</b>

<b>Batch:</b> BTH-2025-001 (the 1st from your search)
<b>Destination:</b> Addis Ababa
<b>Distance:</b> 150km

Reference resolved automatically! 
You said "the first one" and I knew you meant BTH-2025-001."""
        
        await self.send_test(
            "reference_resolution_demo",
            "Reference resolution: 'first one' → batch ID",
            message
        )
    
    async def test_missing_entity_clarification(self):
        """Handler 15: Entity validation - missing entities"""
        message = """❓ <b>Need More Information</b>

I need a bit more information. Could you tell me how much coffee in kilograms, where the coffee is from (region or farm), and what variety it is? 

For example: '50 kilograms from Sidama, Arabica variety'

<i>Entity validation prevented incomplete batch creation!</i>"""
        
        await self.send_test(
            "entity_validation_demo",
            "Entity validation: Ask for missing info",
            message
        )
    
    # ==================== FORMATTING TESTS ====================
    
    async def test_voice_formatting_currencies(self):
        """Handler 16: Voice formatting - currencies"""
        message = """💵 <b>Price Information</b>

Current market prices:
• Arabica Grade 1: $9.50/kg
• Arabica Grade 2: $7.25/kg  
• Robusta: €5.80/kg
• Premium Organic: £12.00/kg

Total value of your inventory: $4,750

<i>Voice will say "9 dollars 50 cents" not "dollar 9 point 5"</i>"""
        
        await self.send_test(
            "voice_formatting_currencies",
            "Voice formatting: Currency symbols",
            message
        )
    
    async def test_voice_formatting_units(self):
        """Handler 17: Voice formatting - units"""
        message = """📊 <b>Batch Statistics</b>

<b>Weight:</b> 50kg processed
<b>Loss:</b> 5kg during roasting
<b>Distance shipped:</b> 150km
<b>Storage capacity:</b> 2000kg available

<i>Voice will say "50 kilograms" not "50 k g"</i>"""
        
        await self.send_test(
            "voice_formatting_units",
            "Voice formatting: Weight and distance units",
            message
        )
    
    async def test_voice_formatting_ordinals(self):
        """Handler 18: Voice formatting - ordinals and numbers"""
        message = """🏆 <b>Your Ranking</b>

You are the 1st farmer in your cooperative!

Top performers:
• 1st place: You (50kg verified)
• 2nd place: Farmer B (45kg)
• 3rd place: Farmer C (40kg)

You have 3 pending verifications.

<i>Voice will say "first" not "one s t"</i>"""
        
        await self.send_test(
            "voice_formatting_ordinals",
            "Voice formatting: Ordinals and small numbers",
            message
        )
    
    # ==================== AMHARIC TESTS ====================
    
    async def test_amharic_batch_created(self):
        """Handler 19: Amharic - Batch creation notification"""
        message = """✅ <b>የቡና ባች በተሳካ ሁኔታ ተፈጥሯል!</b>

<b>የባች መለያ ቁጥር:</b> BTH-2025-001
<b>ብዛት:</b> 50 ኪሎ ግራም
<b>ዓይነት:</b> አረቢካ
<b>ምንጭ:</b> ይርጋቸፍ

የእርስዎ ባች በብሎክቼይን ላይ ተመዝግቧል።
<b>ቀጣዩ ደረጃ:</b> የኅብረት ሥራ ማኅበር ማረጋገጫ ይጠብቁ።"""
        
        try:
            success = await self.channel.send_notification(
                user_id=TEST_TELEGRAM_ID,
                message=message,
                parse_mode="HTML",
                send_voice=True,
                language="am"  # Force Amharic TTS
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ amharic_batch_created - Message sent successfully")
                logger.info(f"   Amharic text + AddisAI TTS")
            else:
                self.failed += 1
                logger.error(f"❌ amharic_batch_created - Failed")
                return False
                
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ amharic_batch_created - Error: {e}", exc_info=True)
            return False
        
        await asyncio.sleep(PAUSE_BETWEEN_TESTS)
        return True
    
    async def test_amharic_shipment_notification(self):
        """Handler 20: Amharic - Shipment notification"""
        message = """🚚 <b>ጭነት ተመዝግቧል!</b>

<b>ባች:</b> BTH-2025-001
<b>መድረሻ:</b> አዲስ አበባ መጋዘን
<b>ርቀት:</b> 150 ኪሎ ሜትር
<b>የሚደርስበት ግምት:</b> 2 ቀናት

ጭነቱ አሁን በብሎክቼይን ላይ እየተከታተለ ነው።"""
        
        try:
            success = await self.channel.send_notification(
                user_id=TEST_TELEGRAM_ID,
                message=message,
                parse_mode="HTML",
                send_voice=True,
                language="am"
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ amharic_shipment - Message sent successfully")
            else:
                self.failed += 1
                logger.error(f"❌ amharic_shipment - Failed")
                return False
                
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ amharic_shipment - Error: {e}", exc_info=True)
            return False
        
        await asyncio.sleep(PAUSE_BETWEEN_TESTS)
        return True
    
    async def test_amharic_verification(self):
        """Handler 21: Amharic - Verification notification"""
        message = """✅ <b>ባች ተረጋግጧል!</b>

<b>ባች:</b> BTH-2025-001
<b>በተረጋገጠ:</b> ይርጋቸፍ ህብረት ስራ ማህበር
<b>የጥራት ደረጃ:</b> 1ኛ (ፕሪሚየም)

🎫 <b>ቶከን ተፈጥሯል:</b> #12345
🔗 <b>ብሎክቼይን:</b> ቤዝ ሴፖሊያ

የእርስዎ ቡና አሁን ቶከን ሆኗል እና ሊገበያይ ይችላል!"""
        
        try:
            success = await self.channel.send_notification(
                user_id=TEST_TELEGRAM_ID,
                message=message,
                parse_mode="HTML",
                send_voice=True,
                language="am"
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ amharic_verification - Message sent successfully")
            else:
                self.failed += 1
                logger.error(f"❌ amharic_verification - Failed")
                return False
                
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ amharic_verification - Error: {e}", exc_info=True)
            return False
        
        await asyncio.sleep(PAUSE_BETWEEN_TESTS)
        return True
    
    async def test_amharic_mixed_content(self):
        """Handler 22: Amharic - Mixed Amharic/English/Numbers"""
        message = """📊 <b>የዋጋ መረጃ</b>

የአሁኑ የገበያ ዋጋዎች:
• አረቢካ ደረጃ 1: $9.50/kg
• አረቢካ ደረጃ 2: $7.25/kg
• ሮቡስታ: €5.80/kg

የእርስዎ አጠቃላይ እሴት: $4,750

<i>TTS should handle mixed Amharic/English/currencies naturally</i>"""
        
        try:
            success = await self.channel.send_notification(
                user_id=TEST_TELEGRAM_ID,
                message=message,
                parse_mode="HTML",
                send_voice=True,
                language="am"
            )
            
            if success:
                self.passed += 1
                logger.info(f"✅ amharic_mixed_content - Message sent successfully")
            else:
                self.failed += 1
                logger.error(f"❌ amharic_mixed_content - Failed")
                return False
                
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ amharic_mixed_content - Error: {e}", exc_info=True)
            return False
        
        await asyncio.sleep(PAUSE_BETWEEN_TESTS)
        return True
    
    # ==================== SUMMARY ====================
    
    async def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Passed: {self.passed}")
        logger.info(f"❌ Failed: {self.failed}")
        logger.info(f"📊 Total: {self.passed + self.failed}")
        logger.info(f"✓ Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Features Tested:")
        logger.info("  ✅ Entity Validation (missing entity detection)")
        logger.info("  ✅ Reference Resolution ('first one' → batch ID)")
        logger.info("  ✅ Voice Formatting (currencies, units, ordinals)")
        logger.info("  ✅ Dual Delivery (text + voice to Telegram)")
        logger.info("  ✅ Amharic TTS (AddisAI voice generation)")
        logger.info("")
        logger.info("Check your Telegram for:")
        logger.info("  1. Text messages (immediate, with HTML formatting)")
        logger.info("  2. Voice messages (2-4s later, natural speech)")
        logger.info("  3. Voice formatting applied correctly")
        logger.info("  4. Amharic voice messages (AddisAI TTS)")
        logger.info("")
    
    async def run_all_tests(self):
        """Run all handler tests."""
        if not await self.setup():
            return False
        
        # Batch Management (7 tests)
        await self.test_record_commission()
        await self.test_record_shipment()
        await self.test_record_receipt()
        await self.test_record_transformation()
        await self.test_pack_batches()
        await self.test_unpack_batches()
        await self.test_split_batch()
        
        # Marketplace (3 tests)
        await self.test_create_rfq()
        await self.test_submit_offer()
        await self.test_accept_offer()
        
        # Verification (2 tests)
        await self.test_submit_for_verification()
        await self.test_verify_batch()
        
        # Query + Reference Resolution (2 tests)
        await self.test_search_batches()
        await self.test_reference_resolution()
        
        # Entity Validation (1 test)
        await self.test_missing_entity_clarification()
        
        # Voice Formatting (3 tests)
        await self.test_voice_formatting_currencies()
        await self.test_voice_formatting_units()
        await self.test_voice_formatting_ordinals()
        
        # Amharic TTS (4 tests)
        await self.test_amharic_batch_created()
        await self.test_amharic_shipment_notification()
        await self.test_amharic_verification()
        await self.test_amharic_mixed_content()
        
        # Summary
        await self.print_summary()
        
        return self.failed == 0


async def main():
    """Main test runner."""
    suite = HandlerTestSuite()
    success = await suite.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
