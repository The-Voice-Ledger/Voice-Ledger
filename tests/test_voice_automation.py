"""
Automated Voice Prioritization Test

Actually triggers voice processing flows through the production API
and monitors responses in Telegram.
"""

import asyncio
import os
import sys
from pathlib import Path
import time
import tempfile
import requests
from pydub import AudioSegment
from pydub.generators import Sine

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


class AutomatedVoiceTest:
    """Automated test that triggers actual voice flows via production API"""
    
    def __init__(self):
        self.test_user_id = '5753848438'  # Your Telegram ID
        self.api_base_url = 'http://localhost:8000'
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.api_key = os.getenv('VOICE_LEDGER_API_KEY')
        
    def generate_dummy_audio(self, duration_ms: int = 3000) -> bytes:
        """Generate a dummy audio file (silent OGG)"""
        # Generate silent audio
        audio = AudioSegment.silent(duration=duration_ms, frame_rate=48000)
        
        # Export to OGG format (Telegram voice format)
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            audio.export(f.name, format='ogg', codec='libopus')
            with open(f.name, 'rb') as audio_file:
                audio_data = audio_file.read()
            os.unlink(f.name)
        
        return audio_data
        
    async def send_test_notification(self, message: str):
        """Send notification to user"""
        await self.bot.send_message(
            chat_id=self.test_user_id,
            text=message,
            parse_mode='Markdown'
        )
    
    async def simulate_voice_message(self, transcript: str, test_name: str):
        """Simulate a voice message through the production API"""
        print(f"\n{'='*70}")
        print(f"🎤 {test_name}")
        print(f"{'='*70}")
        print(f"Transcript: \"{transcript}\"")
        print(f"\nSending to production API...")
        
        # Use the process-command endpoint with transcript
        response = requests.post(
            f"{self.api_base_url}/voice/process-command",
            json={
                'transcript': transcript,
                'language': 'en',
                'metadata': {
                    'user_id': self.test_user_id,
                    'channel': 'telegram',
                    'username': 'Manu_Acho'
                }
            },
            headers={'X-API-Key': self.api_key} if self.api_key else {}
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"✅ Task queued: {task_id}")
            print(f"⏳ Processing asynchronously...")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   {response.text}")
            return None
        
        # Wait for processing
        await asyncio.sleep(3)
        
        print(f"\n📱 Check your Telegram for responses!")
        print(f"{'='*70}\n")
        
        return task_id
    
    async def test_batch_creation(self):
        """Test 1: Batch creation flow"""
        print("\n🧪 TEST 1: BATCH CREATION FLOW")
        print("="*70)
        
        await self.send_test_notification(
            "🧪 **TEST 1 STARTING: Batch Creation**\n\n"
            "Watch for:\n"
            "❌ 'Voice received' → NO voice\n"
            "❌ 'Task ID' → NO voice\n"
            "✅ Questions → WITH voice\n"
            "✅ Confirmation → WITH voice"
        )
        
        await asyncio.sleep(2)
        
        await self.simulate_voice_message(
            "I harvested 100 kilograms of coffee from Sidama",
            "Batch Creation"
        )
        
        print("✅ Expected in Telegram:")
        print("   • 'Voice received' (TEXT ONLY - no voice)")
        print("   • 'Task ID' (TEXT ONLY - no voice)")
        print("   • Follow-up questions (WITH VOICE)")
    
    async def test_rfq_creation_initial(self):
        """Test 2: RFQ creation - initial message"""
        print("\n🧪 TEST 2: RFQ CREATION FLOW")
        print("="*70)
        
        await self.send_test_notification(
            "🧪 **TEST 2 STARTING: RFQ Creation**\n\n"
            "Watch for:\n"
            "❌ 'Voice received' → NO voice\n"
            "❌ 'RFQ Preview' → NO voice\n"
            "✅ 'What grade?' → WITH voice\n"
            "✅ Other questions → WITH voice\n"
            "✅ Summary → WITH voice"
        )
        
        await asyncio.sleep(2)
        
        await self.simulate_voice_message(
            "I want to buy 1000 kilograms of Sidama coffee",
            "RFQ Creation - Initial"
        )
        
        print("✅ Expected in Telegram:")
        print("   • 'Voice received' (TEXT ONLY - no voice)")
        print("   • RFQ Preview (TEXT ONLY - no voice)")
        print("   • 'What grade?' question (WITH VOICE)")
        
        print("\n⏳ Now respond via voice in Telegram:")
        print("   🎤 Say: 'Grade 1'")
        print("   🎤 Say: 'Washed'")
        print("   🎤 Say: 'Djibouti'")
        print("   🎤 Say: '30 days'")
        print("   🎤 Say: 'yes ready to broadcast'")
    
    async def run_full_test(self):
        """Run complete test suite"""
        print("\n" + "="*70)
        print("🚀 AUTOMATED VOICE PRIORITIZATION TEST")
        print("="*70)
        
        print("\nℹ️  This test will:")
        print("   1. Send actual voice commands through production API")
        print("   2. Trigger real Telegram responses")
        print("   3. You'll see messages in @voice_ledger_bot")
        print("\n⚠️  Make sure services are running:")
        print("   • Celery worker")
        print("   • FastAPI server")
        print("   • ngrok tunnel")
        
        # Check API is reachable
        try:
            response = requests.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                print("\n✅ API is reachable")
            else:
                print(f"\n❌ API returned {response.status_code}")
        except Exception as e:
            print(f"\n❌ Cannot reach API: {e}")
            print("   Run: ./admin_scripts/START_SERVICES.sh")
            return
        
        input("\n⏸️  Press ENTER to start Test 1 (Batch Creation)...")
        await self.test_batch_creation()
        
        print("\n⏳ Waiting 10 seconds for responses...")
        await asyncio.sleep(10)
        
        input("\n⏸️  Press ENTER to start Test 2 (RFQ Creation)...")
        await self.test_rfq_creation_initial()
        
        print("\n⏳ Waiting 10 seconds for initial responses...")
        await asyncio.sleep(10)
        
        print("\n" + "="*70)
        print("✅ AUTOMATED TESTS TRIGGERED")
        print("="*70)
        
        print("\n📱 Check your Telegram @voice_ledger_bot")
        print("\n🔍 VALIDATION CHECKLIST:")
        print("\n   System Notifications (NO VOICE):")
        print("   ❌ 'Voice received! Processing...'")
        print("   ❌ 'Task ID: ...'")
        print("   ❌ 'RFQ Preview' with extracted data")
        print("   ❌ Error messages")
        
        print("\n   Conversational Content (WITH VOICE):")
        print("   ✅ 'What grade are you looking for?'")
        print("   ✅ 'Which processing method?'")
        print("   ✅ 'Where should it be delivered?'")
        print("   ✅ 'When do you need it delivered?'")
        print("   ✅ 'RFQ Summary - Please Confirm'")
        print("   ✅ Batch confirmation messages")
        
        print("\n💡 Continue the RFQ flow via voice in Telegram to complete testing")
        print("   Then check each message to verify voice delivery!")
        
        await self.send_test_notification(
            "✅ **TESTS COMPLETE**\n\n"
            "Review each message above:\n"
            "• System notifications should be TEXT ONLY\n"
            "• Questions/content should have VOICE\n\n"
            "Report validation results!"
        )


async def main_async():
    """Run tests"""
    tester = AutomatedVoiceTest()
    await tester.run_full_test()


def main():
    """Run tests"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
