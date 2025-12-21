"""
Test Lab 15 Telegram RFQ Commands
Quick validation of Telegram bot integration
"""

import sys
sys.path.append('/Users/manu/Voice-Ledger')

import asyncio
from voice.telegram.rfq_handler import (
    handle_rfq_command,
    handle_offers_command,
    handle_myoffers_command,
    handle_myrfqs_command
)

# Test user IDs (use the ones we created)
BUYER_USER_ID = 777001  # test_buyer
COOP_USER_ID = 888001  # test_coop_manager


async def test_buyer_flow():
    """Test buyer creates RFQ"""
    print("\n" + "="*60)
    print("TEST 1: Buyer RFQ Creation")
    print("="*60)
    
    # Start RFQ creation
    response = await handle_rfq_command(BUYER_USER_ID, "test_buyer")
    print(f"\n/rfq command response:")
    print(f"Message: {response['message'][:200]}...")
    print(f"Has keyboard: {'keyboard' in response}")
    
    # Check /myrfqs command
    response = await handle_myrfqs_command(BUYER_USER_ID, "test_buyer")
    print(f"\n/myrfqs command response:")
    print(f"Message: {response['message'][:200]}...")
    

async def test_cooperative_flow():
    """Test cooperative views and responds to RFQs"""
    print("\n" + "="*60)
    print("TEST 2: Cooperative Views RFQs")
    print("="*60)
    
    # View available RFQs
    response = await handle_offers_command(COOP_USER_ID, "test_coop_manager")
    print(f"\n/offers command response:")
    print(f"Message: {response['message'][:300]}...")
    print(f"Has keyboard: {'keyboard' in response}")
    
    # Check my offers
    response = await handle_myoffers_command(COOP_USER_ID, "test_coop_manager")
    print(f"\n/myoffers command response:")
    print(f"Message: {response['message'][:200]}...")


async def test_access_control():
    """Test role-based access control"""
    print("\n" + "="*60)
    print("TEST 3: Access Control")
    print("="*60)
    
    # Cooperative tries to create RFQ (should fail)
    response = await handle_rfq_command(COOP_USER_ID, "test_coop_manager")
    print(f"\nCooperative tries /rfq:")
    print(f"Message: {response['message'][:150]}...")
    print(f"Should be denied: {'Access Denied' in response['message']}")
    
    # Buyer tries to view offers (should fail)
    response = await handle_offers_command(BUYER_USER_ID, "test_buyer")
    print(f"\nBuyer tries /offers:")
    print(f"Message: {response['message'][:150]}...")
    print(f"Should be denied: {'Access Denied' in response['message']}")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("LAB 15: TELEGRAM RFQ INTEGRATION TESTS")
    print("="*60)
    print("\nTesting Telegram bot handlers for RFQ marketplace...")
    
    try:
        await test_buyer_flow()
        await test_cooperative_flow()
        await test_access_control()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED")
        print("="*60)
        print("\nNext Steps:")
        print("1. Start FastAPI server")
        print("2. Test via actual Telegram bot")
        print("3. Test complete buyer-to-cooperative flow")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
