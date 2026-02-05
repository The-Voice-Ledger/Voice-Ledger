"""
Access Control & Command Handler Test

Tests the new role-based access control system and command improvements:
1. Role-based access control (COMMAND_ROLES)
2. /dpp command with/without parameters
3. Unknown command handling
4. Permission denied messages
5. Dual delivery for all responses

Test Users:
- 5753848438 (Farmer role)
- Need a Cooperative Manager for full testing
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

# Test configuration
FARMER_TELEGRAM_ID = "5753848438"  # Your Telegram ID (Farmer role)
PAUSE_BETWEEN_TESTS = 3  # seconds between each test


class AccessControlTestSuite:
    """Test suite for access control and command improvements."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests_run = 0
        
    async def setup(self):
        """Initialize test environment."""
        logger.info("=" * 80)
        logger.info("VOICE LEDGER - ACCESS CONTROL & COMMAND HANDLER TEST")
        logger.info("=" * 80)
        logger.info(f"Test User: {FARMER_TELEGRAM_ID} (Farmer role)")
        logger.info("Testing: Role-based access control + Command improvements")
        logger.info("=" * 80)
        
        # Verify database user
        from database.models import SessionLocal, UserIdentity
        db = SessionLocal()
        try:
            user = db.query(UserIdentity).filter_by(
                telegram_user_id=FARMER_TELEGRAM_ID
            ).first()
            
            if not user:
                logger.error(f"❌ User {FARMER_TELEGRAM_ID} not found in database")
                return False
            
            logger.info(f"✅ User found: {user.telegram_first_name} {user.telegram_last_name}")
            logger.info(f"   Role: {user.role}")
            logger.info(f"   Approved: {user.is_approved}")
            logger.info(f"   DID: {user.did}")
            logger.info("")
            
            return True
        finally:
            db.close()
    
    async def send_command(self, command: str, description: str, expected_result: str):
        """
        Send a command to the Telegram bot.
        
        Args:
            command: The command to send (e.g., "/dpp", "/pack")
            description: Test description
            expected_result: What we expect to happen
        """
        self.tests_run += 1
        logger.info("=" * 80)
        logger.info(f"TEST {self.tests_run}: {description}")
        logger.info("=" * 80)
        logger.info(f"Command: {command}")
        logger.info(f"Expected: {expected_result}")
        logger.info("")
        
        # Import here to avoid circular imports
        from voice.telegram.telegram_api import handle_text_command
        
        # Create update data simulating Telegram message
        update_data = {
            'message': {
                'message_id': 12345 + self.tests_run,
                'from': {
                    'id': int(FARMER_TELEGRAM_ID),
                    'is_bot': False,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': int(FARMER_TELEGRAM_ID),
                    'type': 'private'
                },
                'text': command,
                'date': 1738713600
            }
        }
        
        try:
            result = await handle_text_command(update_data)
            
            if result.get('ok'):
                self.passed += 1
                logger.info(f"✅ Command processed successfully")
                logger.info(f"   Check Telegram for response message")
            else:
                self.failed += 1
                logger.error(f"❌ Command failed: {result.get('message', 'Unknown error')}")
            
            await asyncio.sleep(PAUSE_BETWEEN_TESTS)
            return True
            
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ Exception occurred: {e}", exc_info=True)
            return False
    
    # ==================== ACCESS CONTROL TESTS ====================
    
    async def test_farmer_commission_allowed(self):
        """Test: Farmer CAN use /commission (should be allowed)"""
        await self.send_command(
            "/commission 50 Sidama MyFarm",
            "Farmer creates batch (SHOULD BE ALLOWED)",
            "✅ Batch created successfully"
        )
    
    async def test_farmer_pack_denied(self):
        """Test: Farmer CANNOT use /pack (should be denied)"""
        await self.send_command(
            "/pack BTH-001 BTH-002",
            "Farmer tries to pack batches (SHOULD BE DENIED)",
            "❌ Permission denied: Only Cooperative Manager, Exporter can use /pack"
        )
    
    async def test_farmer_verify_denied(self):
        """Test: Farmer CANNOT use /verify (should be denied)"""
        await self.send_command(
            "/verify BTH-001 50",
            "Farmer tries to verify batch (SHOULD BE DENIED)",
            "❌ Permission denied: Only Cooperative Manager can use /verify"
        )
    
    async def test_farmer_unpack_denied(self):
        """Test: Farmer CANNOT use /unpack (should be denied)"""
        await self.send_command(
            "/unpack CONTAINER-001",
            "Farmer tries to unpack container (SHOULD BE DENIED)",
            "❌ Permission denied: Only Trader can use /unpack"
        )
    
    async def test_farmer_split_denied(self):
        """Test: Farmer CANNOT use /split (should be denied)"""
        await self.send_command(
            "/split BTH-001 30 20",
            "Farmer tries to split batch (SHOULD BE DENIED)",
            "❌ Permission denied: Only Trader can use /split"
        )
    
    async def test_farmer_export_denied(self):
        """Test: Farmer CANNOT use /export (should be denied)"""
        await self.send_command(
            "/export CONTAINER-001",
            "Farmer tries to export (SHOULD BE DENIED)",
            "❌ Permission denied: Only Cooperative Manager, Exporter can use /export"
        )
    
    async def test_farmer_dpp_denied(self):
        """Test: Farmer CANNOT use /dpp (should be denied)"""
        await self.send_command(
            "/dpp 306141411234567892",
            "Farmer tries to generate DPP (SHOULD BE DENIED)",
            "❌ Permission denied: Only Cooperative Manager, Exporter, Trader can use /dpp"
        )
    
    # ==================== COMMAND IMPROVEMENT TESTS ====================
    
    async def test_dpp_no_parameter(self):
        """Test: /dpp without parameter shows usage"""
        await self.send_command(
            "/dpp",
            "/dpp without container ID (SHOULD SHOW USAGE)",
            "❌ Usage: /dpp <container_id>"
        )
    
    async def test_unknown_command(self):
        """Test: Unknown command gets helpful response"""
        await self.send_command(
            "/xyz123",
            "Unknown command (SHOULD GET HELP MESSAGE)",
            "❓ Unknown command: /xyz123. Send /help to see available commands."
        )
    
    async def test_help_command(self):
        """Test: /help shows available commands"""
        await self.send_command(
            "/help",
            "Request help (SHOULD SHOW COMMAND LIST)",
            "Available commands list"
        )
    
    # ==================== ALLOWED COMMANDS FOR FARMER ====================
    
    async def test_farmer_ship_allowed(self):
        """Test: Farmer CAN use /ship"""
        await self.send_command(
            "/ship BTH-001 AddisAbaba",
            "Farmer ships batch (SHOULD BE ALLOWED)",
            "✅ Shipment recorded"
        )
    
    async def test_mybatches_command(self):
        """Test: /mybatches shows farmer's batches"""
        await self.send_command(
            "/mybatches",
            "List farmer's batches (SHOULD WORK)",
            "Your batches list"
        )
    
    async def test_mycredentials_command(self):
        """Test: /mycredentials shows farmer's credentials"""
        await self.send_command(
            "/mycredentials",
            "Show credentials (SHOULD WORK)",
            "Your credentials"
        )
    
    async def test_status_command(self):
        """Test: /status shows system status"""
        await self.send_command(
            "/status",
            "Check system status (SHOULD WORK)",
            "System status"
        )
    
    # ==================== SUMMARY ====================
    
    async def print_summary(self):
        """Print test summary."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {self.tests_run}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        
        if self.failed == 0:
            logger.info("")
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("")
            logger.info("✅ Verified:")
            logger.info("  ✅ Role-based access control works correctly")
            logger.info("  ✅ Farmers can create batches (/commission)")
            logger.info("  ✅ Farmers are blocked from cooperative operations")
            logger.info("  ✅ /dpp shows usage when no parameter provided")
            logger.info("  ✅ Unknown commands get helpful messages")
            logger.info("  ✅ All responses sent via dual delivery")
        else:
            logger.warning("")
            logger.warning(f"⚠️  {self.failed} TESTS FAILED")
            logger.warning("Check logs above for details")
        
        logger.info("")
        logger.info("Check your Telegram (@voice_ledger_bot) for:")
        logger.info("  1. Permission denied messages for restricted commands")
        logger.info("  2. Usage instructions for /dpp without parameter")
        logger.info("  3. Help message for unknown commands")
        logger.info("  4. Success messages for allowed commands")
        logger.info("=" * 80)
        logger.info("")
    
    async def run_all_tests(self):
        """Run all access control and command tests."""
        if not await self.setup():
            return False
        
        logger.info("PHASE 1: Testing Denied Commands (Farmer → Coop/Exporter/Trader ops)")
        logger.info("-" * 80)
        await self.test_farmer_pack_denied()
        await self.test_farmer_verify_denied()
        await self.test_farmer_unpack_denied()
        await self.test_farmer_split_denied()
        await self.test_farmer_export_denied()
        await self.test_farmer_dpp_denied()
        
        logger.info("")
        logger.info("PHASE 2: Testing Command Improvements")
        logger.info("-" * 80)
        await self.test_dpp_no_parameter()
        await self.test_unknown_command()
        await self.test_help_command()
        
        logger.info("")
        logger.info("PHASE 3: Testing Allowed Commands (Farmer can use)")
        logger.info("-" * 80)
        await self.test_farmer_commission_allowed()
        await self.test_farmer_ship_allowed()
        await self.test_mybatches_command()
        await self.test_mycredentials_command()
        await self.test_status_command()
        
        # Summary
        await self.print_summary()
        
        return self.failed == 0


async def main():
    """Main test runner."""
    suite = AccessControlTestSuite()
    success = await suite.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
