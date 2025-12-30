"""
End-to-End Test: Voice Prioritization for Batch Creation & RFQ Generation

Tests that:
1. System notifications are text-only (no voice)
2. Conversational content includes voice
3. Multi-turn conversations work correctly
4. Confirmations accept natural language

Usage:
    python tests/test_voice_prioritization.py
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot, Update
from telegram.error import TelegramError
from dotenv import load_dotenv
from database.connection import SessionLocal
from database.models import UserIdentity

load_dotenv()


class VoiceOutputValidator:
    """Validates voice output in Telegram messages"""
    
    def __init__(self, bot: Bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self.message_log: List[Dict[str, Any]] = []
        
    async def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages sent to user (text and voice)"""
        # Note: Telegram doesn't allow bots to read messages, so we'll track via mock
        # In real testing, we monitor by user observation or webhook logs
        return self.message_log[-count:]
    
    def log_message(self, message_type: str, content: str, has_voice: bool):
        """Log a message for validation"""
        self.message_log.append({
            'type': message_type,
            'content': content,
            'has_voice': has_voice,
            'timestamp': time.time()
        })


class TestVoicePrioritization:
    """End-to-end test for voice prioritization"""
    
    def __init__(self):
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.test_user_id = '5753848438'  # Manu's Telegram ID
        self.validator = VoiceOutputValidator(self.bot, self.test_user_id)
        self.db = SessionLocal()
        
    async def setup(self):
        """Setup test environment"""
        print("\n" + "="*70)
        print("🧪 VOICE PRIORITIZATION TEST")
        print("="*70)
        
        # Verify user exists and has both roles configured
        user = self.db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == self.test_user_id
        ).first()
        
        if not user:
            print("❌ Test user not found in database")
            return False
            
        full_name = f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip()
        print(f"\n✅ Test User: {full_name or 'User ' + str(user.id)}")
        print(f"   Role: {user.role}")
        print(f"   Organization: {user.organization_id}")
        print(f"   Approved: {user.is_approved}")
        
        return True
    
    async def send_notification(self, message: str, test_name: str):
        """Send test notification to user"""
        await self.bot.send_message(
            chat_id=self.test_user_id,
            text=message,
            parse_mode='Markdown'
        )
        print(f"\n📤 {test_name}")
        print(f"   Message sent to Telegram")
    
    async def test_batch_creation_flow(self):
        """Test batch creation with voice prioritization"""
        print("\n" + "-"*70)
        print("TEST 1: Batch Creation Flow (as Farmer)")
        print("-"*70)
        
        await self.send_notification(
            "🧪 **TEST 1: Batch Creation**\n\n"
            "🎤 Send voice message:\n"
            "*\"I harvested 100 kilograms of coffee from Sidama\"*\n\n"
            "✅ Expected:\n"
            "• 'Voice received' → NO voice (system notification)\n"
            "• 'Task ID' → NO voice (system notification)\n"
            "• Questions about variety/grade → WITH voice (conversational)\n"
            "• Batch confirmation → WITH voice (conversational)\n\n"
            "⏱️ Wait 10 seconds for response...",
            "Batch Creation Test"
        )
        
        print("\n📊 Validation Points:")
        print("   1. System notifications (voice received, task ID) should be text-only")
        print("   2. Follow-up questions should include voice")
        print("   3. Final confirmation should include voice")
        
        # Wait for user to complete flow
        await asyncio.sleep(30)
        
    async def test_rfq_creation_flow(self):
        """Test RFQ creation with voice prioritization"""
        print("\n" + "-"*70)
        print("TEST 2: RFQ Multi-turn Flow (as Buyer)")
        print("-"*70)
        
        await self.send_notification(
            "🧪 **TEST 2: RFQ Creation**\n\n"
            "🎤 Send voice message:\n"
            "*\"I want to buy 1000 kilograms of Sidama coffee\"*\n\n"
            "✅ Expected:\n"
            "• 'Voice received' → NO voice (system notification)\n"
            "• RFQ Preview → NO voice (data display)\n"
            "• 'What grade?' → WITH voice (question)\n"
            "• 'Where deliver?' → WITH voice (question)\n"
            "• 'When needed?' → WITH voice (question)\n"
            "• Summary → WITH voice (conversational)\n\n"
            "Then say: *'yes'* or *'yes ready to broadcast'*\n\n"
            "⏱️ Wait for each response...",
            "RFQ Creation Test"
        )
        
        print("\n📊 Validation Points:")
        print("   1. System notification (voice received) should be text-only")
        print("   2. Preview should be text-only (data display)")
        print("   3. ALL questions should include voice")
        print("   4. Summary should include voice")
        print("   5. Confirmation should accept 'yes' variants")
        
        # Wait for user to complete flow
        await asyncio.sleep(60)
        
    async def test_natural_language_dates(self):
        """Test natural language date parsing"""
        print("\n" + "-"*70)
        print("TEST 3: Natural Language Date Parsing")
        print("-"*70)
        
        await self.send_notification(
            "🧪 **TEST 3: Natural Language Dates**\n\n"
            "When asked for deadline, try these:\n\n"
            "🎤 Voice options:\n"
            "• *\"30 days\"*\n"
            "• *\"February 15th\"*\n"
            "• *\"in 2 months\"*\n"
            "• *\"March 2025\"*\n"
            "• *\"2025-03-15\"* (standard format)\n\n"
            "All should be accepted!\n\n"
            "⏱️ Test during next RFQ creation...",
            "Date Parsing Test"
        )
        
        print("\n📊 Validation Points:")
        print("   1. Relative dates: '30 days', '2 months'")
        print("   2. Natural dates: 'February 15th', 'March 2025'")
        print("   3. Standard format: 'YYYY-MM-DD'")
        
        await asyncio.sleep(10)
        
    async def test_confirmation_acceptance(self):
        """Test confirmation with various affirmative phrases"""
        print("\n" + "-"*70)
        print("TEST 4: Confirmation Phrase Acceptance")
        print("-"*70)
        
        await self.send_notification(
            "🧪 **TEST 4: Confirmation Acceptance**\n\n"
            "When confirming RFQ, these should ALL work:\n\n"
            "✅ Accepted phrases:\n"
            "• *\"yes\"*\n"
            "• *\"yes ready to broadcast\"*\n"
            "• *\"confirm\"*\n"
            "• *\"okay\"*\n"
            "• *\"sure\"*\n"
            "• *\"proceed\"*\n\n"
            "❌ Cancel phrases:\n"
            "• *\"no\"*\n"
            "• *\"cancel\"*\n"
            "• *\"stop\"*\n\n"
            "⏱️ Test during confirmation step...",
            "Confirmation Test"
        )
        
        print("\n📊 Validation Points:")
        print("   1. Any affirmative keyword should confirm")
        print("   2. Any cancel keyword should abort")
        print("   3. Unclear responses should ask again")
        
        await asyncio.sleep(10)
        
    async def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("📋 TEST SUMMARY")
        print("="*70)
        
        print("\n✅ Tests Configured:")
        print("   1. Batch Creation Flow")
        print("   2. RFQ Multi-turn Flow")
        print("   3. Natural Language Dates")
        print("   4. Confirmation Acceptance")
        
        print("\n📱 Manual Validation Required:")
        print("   • Check Telegram for voice messages vs text-only")
        print("   • Verify system notifications have NO voice")
        print("   • Verify questions/content HAVE voice")
        print("   • Confirm all flows complete successfully")
        
        print("\n🎯 Success Criteria:")
        print("   ✓ System notifications are text-only")
        print("   ✓ Conversational content includes voice")
        print("   ✓ Multi-turn RFQ flow completes")
        print("   ✓ Natural language dates work")
        print("   ✓ 'Yes' variants accepted for confirmation")
        
        print("\n" + "="*70)
        
    async def run_all_tests(self):
        """Run all tests"""
        if not await self.setup():
            return
            
        try:
            # Test 1: Batch creation
            await self.test_batch_creation_flow()
            
            # Test 2: RFQ creation
            await self.test_rfq_creation_flow()
            
            # Test 3: Date parsing
            await self.test_natural_language_dates()
            
            # Test 4: Confirmation
            await self.test_confirmation_acceptance()
            
            # Summary
            await self.print_summary()
            
            # Final notification
            await self.send_notification(
                "✅ **ALL TESTS SENT**\n\n"
                "Please complete the flows above and verify:\n"
                "1. Voice output is correct for each message type\n"
                "2. Multi-turn conversations work\n"
                "3. Confirmations accept natural language\n\n"
                "Report any issues!",
                "Test Complete"
            )
            
        finally:
            self.db.close()


async def main():
    """Run tests"""
    tester = TestVoicePrioritization()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
