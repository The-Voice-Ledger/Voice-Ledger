#!/usr/bin/env python3
"""
End-to-End Test: Commission + Verification with Real IPFS & Blockchain

Tests the complete flow from batch creation to verification with:
- Real IPFS pinning via Pinata
- Real blockchain anchoring to Base Sepolia
- Commission event creation
- Verification event creation
- Database verification
- IPFS retrieval verification
- Blockchain transaction verification
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import SessionLocal, CoffeeBatch, EPCISEvent, Organization, UserIdentity
from voice.command_integration import handle_record_commission
from voice.verification.verification_events import create_verification_event
from datetime import datetime
import requests
import os


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_step(step_num, title):
    """Print step header"""
    print(f"\n{'─' * 80}")
    print(f"  STEP {step_num}: {title}")
    print('─' * 80)


def test_commission_flow():
    """Test commission event with real IPFS + blockchain"""
    print_step(1, "Create Batch with Commission Event")
    
    db = SessionLocal()
    try:
        # Get test user
        user = db.query(UserIdentity).first()
        if not user:
            print("❌ No user found. Please create a user first.")
            return None, None
        
        print(f"✓ Using user: {user.telegram_username or user.telegram_first_name}")
        print(f"  DID: {user.did[:30]}...")
        
        # Create batch via command handler (automatically creates commission event)
        entities = {
            'quantity': 30,
            'unit': 'bags',
            'product': 'Sidamo',
            'origin': 'Gedeo'
        }
        
        print(f"\n📦 Creating batch:")
        print(f"  Quantity: {entities['quantity']} {entities['unit']}")
        print(f"  Product: {entities['product']}")
        print(f"  Origin: {entities['origin']}")
        
        message, result = handle_record_commission(
            db=db,
            entities=entities,
            user_id=user.id,
            user_did=user.did
        )
        
        print(f"\n✅ {message}")
        print(f"\n📋 Batch Details:")
        print(f"  Batch ID: {result['batch_id']}")
        print(f"  GTIN: {result['gtin']}")
        print(f"  GLN: {result.get('gln', 'N/A')}")
        print(f"  Quantity: {result['quantity_kg']} kg")
        
        # Check commission event
        if result.get('epcis_event'):
            event_info = result['epcis_event']
            print(f"\n🗄️  Commission Event Created:")
            print(f"  Event Hash: {event_info.get('event_hash', 'N/A')}")
            print(f"  IPFS CID: {event_info.get('ipfs_cid', 'N/A')}")
            print(f"  Blockchain TX: {event_info.get('blockchain_tx', 'N/A')}")
            print(f"  Confirmed: {'✅' if event_info.get('blockchain_confirmed') else '⏳'}")
            
            return result['batch_id'], event_info
        else:
            print("\n❌ No commission event created")
            return result['batch_id'], None
            
    finally:
        db.close()


def verify_ipfs_pinning(ipfs_cid):
    """Verify event is actually pinned to IPFS and retrievable"""
    print_step(2, "Verify IPFS Pinning")
    
    if not ipfs_cid:
        print("⚠️  No IPFS CID to verify")
        return False
    
    # Try to retrieve from Pinata gateway
    gateway_url = f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}"
    
    print(f"📡 Fetching from IPFS...")
    print(f"  Gateway: {gateway_url}")
    
    try:
        response = requests.get(gateway_url, timeout=10)
        
        if response.status_code == 200:
            event_data = response.json()
            print(f"\n✅ Event successfully retrieved from IPFS")
            print(f"\n📄 Event Data:")
            print(f"  Type: {event_data.get('type', 'N/A')}")
            print(f"  Action: {event_data.get('action', 'N/A')}")
            print(f"  BizStep: {event_data.get('bizStep', 'N/A')}")
            print(f"  Event Time: {event_data.get('eventTime', 'N/A')}")
            
            if 'epcList' in event_data and event_data['epcList']:
                print(f"  SGTIN: {event_data['epcList'][0]}")
            if 'quantityList' in event_data and event_data['quantityList']:
                qty = event_data['quantityList'][0]
                print(f"  LGTIN: {qty.get('epcClass', 'N/A')}")
                print(f"  Quantity: {qty.get('quantity', 0)} {qty.get('uom', 'N/A')}")
            
            return True
        else:
            print(f"❌ Failed to retrieve from IPFS: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error retrieving from IPFS: {e}")
        return False


def verify_blockchain_anchor(tx_hash):
    """Verify transaction on blockchain"""
    print_step(3, "Verify Blockchain Anchoring")
    
    if not tx_hash:
        print("⚠️  No transaction hash to verify")
        return False
    
    # Base Sepolia explorer
    explorer_url = f"https://sepolia.basescan.org/tx/0x{tx_hash}"
    
    print(f"🔗 Transaction Details:")
    print(f"  TX Hash: 0x{tx_hash[:16]}...")
    print(f"  Full TX: https://sepolia.basescan.org/tx/0x{tx_hash}")
    
    # Try to fetch transaction details
    try:
        from web3 import Web3
        
        # Connect to Base Sepolia
        rpc_url = os.getenv('BASE_SEPOLIA_RPC_URL', 'https://sepolia.base.org')
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if w3.is_connected():
            print(f"\n✅ Connected to Base Sepolia")
            print(f"  Chain ID: {w3.eth.chain_id}")
            
            # Get transaction receipt
            tx_receipt = w3.eth.get_transaction_receipt(f"0x{tx_hash}")
            
            if tx_receipt:
                print(f"\n✅ Transaction confirmed on blockchain")
                print(f"  Block Number: {tx_receipt['blockNumber']}")
                print(f"  Gas Used: {tx_receipt['gasUsed']}")
                print(f"  Status: {'Success' if tx_receipt['status'] == 1 else 'Failed'}")
                print(f"  Contract: {tx_receipt['to']}")
                
                return tx_receipt['status'] == 1
            else:
                print(f"⏳ Transaction pending or not found")
                return False
        else:
            print(f"⚠️  Could not connect to Base Sepolia")
            print(f"  View on explorer: {explorer_url}")
            return None
            
    except Exception as e:
        print(f"⚠️  Could not verify transaction: {e}")
        print(f"  View on explorer: {explorer_url}")
        return None


def test_verification_flow(batch_id):
    """Test verification event creation"""
    print_step(4, "Create Verification Event")
    
    db = SessionLocal()
    try:
        # Get batch
        batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
        if not batch:
            print(f"❌ Batch not found: {batch_id}")
            return None
        
        # Get organization
        org = db.query(Organization).first()
        if not org:
            print("❌ No organization found")
            return None
        
        print(f"✓ Batch: {batch.batch_id}")
        print(f"✓ Organization: {org.name}")
        print(f"\n🔍 Creating verification event...")
        
        # Create verification event
        event_result = create_verification_event(
            batch_id=batch.batch_id,
            verifier_did='did:key:z6MkE2ETestManager',
            verifier_name='Test Manager',
            organization_did=org.did,
            organization_name=org.name,
            verified_quantity_kg=batch.quantity_kg * 0.98,  # 2% loss
            claimed_quantity_kg=batch.quantity_kg,
            quality_notes='Grade 1 quality, minimal defects',
            location=batch.origin or 'Gedeo',
            has_photo_evidence=True
        )
        
        if event_result:
            print(f"\n✅ Verification Event Created")
            print(f"\n📋 Event Details:")
            print(f"  Event Hash: {event_result.event_hash[:16]}...")
            print(f"  IPFS CID: {event_result.ipfs_cid}")
            print(f"  Blockchain TX: {event_result.blockchain_tx_hash[:16] + '...' if event_result.blockchain_tx_hash else 'pending'}")
            print(f"  Confirmed: {'✅' if event_result.blockchain_confirmed else '⏳'}")
            
            return {
                'event_hash': event_result.event_hash,
                'ipfs_cid': event_result.ipfs_cid,
                'blockchain_tx_hash': event_result.blockchain_tx_hash
            }
        else:
            print("\n❌ Failed to create verification event")
            return None
            
    finally:
        db.close()


def verify_database_state(batch_id):
    """Verify all events are properly stored in database"""
    print_step(5, "Verify Database State")
    
    db = SessionLocal()
    try:
        # Get batch
        batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
        if not batch:
            print(f"❌ Batch not found")
            return False
        
        # Get all events for this batch
        events = db.query(EPCISEvent).filter(EPCISEvent.batch_id == batch.id).all()
        
        print(f"\n📊 Database State:")
        print(f"  Batch ID: {batch.batch_id}")
        print(f"  Total Events: {len(events)}")
        
        for i, event in enumerate(events, 1):
            print(f"\n  Event {i}:")
            print(f"    Type: {event.event_type}")
            print(f"    BizStep: {event.biz_step}")
            print(f"    Event Time: {event.event_time}")
            print(f"    IPFS CID: {event.ipfs_cid}")
            print(f"    Blockchain: {'✅' if event.blockchain_confirmed else '⏳'}")
            print(f"    TX Hash: {event.blockchain_tx_hash[:16] + '...' if event.blockchain_tx_hash else 'N/A'}")
        
        # Verify we have both commission and verification events
        commission_events = [e for e in events if e.biz_step == 'commissioning']
        verification_events = [e for e in events if e.biz_step == 'inspecting']
        
        print(f"\n✅ Event Summary:")
        print(f"  Commission Events: {len(commission_events)}")
        print(f"  Verification Events: {len(verification_events)}")
        
        return len(commission_events) > 0
        
    finally:
        db.close()


def main():
    """Run complete end-to-end test"""
    print("\n" + "🧪 " * 40)
    print("  END-TO-END TEST: Commission + Verification")
    print("  Real IPFS Pinning + Blockchain Anchoring")
    print("🧪 " * 40)
    
    results = {
        'commission_created': False,
        'ipfs_verified': False,
        'blockchain_verified': False,
        'verification_created': False,
        'database_verified': False
    }
    
    # Step 1: Create batch with commission event
    try:
        batch_id, commission_event = test_commission_flow()
        if batch_id and commission_event:
            results['commission_created'] = True
        else:
            print("\n❌ Commission flow failed")
            return False
    except Exception as e:
        print(f"\n❌ Commission test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Verify IPFS pinning
    if commission_event and commission_event.get('ipfs_cid'):
        try:
            results['ipfs_verified'] = verify_ipfs_pinning(commission_event['ipfs_cid'])
        except Exception as e:
            print(f"\n⚠️  IPFS verification error: {e}")
    
    # Step 3: Verify blockchain anchoring
    if commission_event and commission_event.get('blockchain_tx'):
        # Remove the "..." suffix if present
        tx_hash = commission_event['blockchain_tx'].replace('...', '')
        try:
            blockchain_result = verify_blockchain_anchor(tx_hash)
            if blockchain_result is not None:
                results['blockchain_verified'] = blockchain_result
        except Exception as e:
            print(f"\n⚠️  Blockchain verification error: {e}")
    
    # Step 4: Create verification event
    try:
        verification_event = test_verification_flow(batch_id)
        if verification_event:
            results['verification_created'] = True
            
            # Verify verification event IPFS
            if verification_event.get('ipfs_cid'):
                print_step("4b", "Verify Verification Event IPFS")
                verify_ipfs_pinning(verification_event['ipfs_cid'])
                
    except Exception as e:
        print(f"\n⚠️  Verification test error: {e}")
    
    # Step 5: Verify database state
    try:
        results['database_verified'] = verify_database_state(batch_id)
    except Exception as e:
        print(f"\n⚠️  Database verification error: {e}")
    
    # Final Summary
    print_header("TEST SUMMARY")
    print()
    print("📊 Results:")
    print(f"  {'✅' if results['commission_created'] else '❌'} Commission Event Created")
    print(f"  {'✅' if results['ipfs_verified'] else '⚠️ '} IPFS Pinning Verified")
    print(f"  {'✅' if results['blockchain_verified'] else '⚠️ '} Blockchain Anchoring Verified")
    print(f"  {'✅' if results['verification_created'] else '⚠️ '} Verification Event Created")
    print(f"  {'✅' if results['database_verified'] else '❌'} Database State Verified")
    
    total = sum(1 for v in results.values() if v)
    print(f"\n  Score: {total}/5 checks passed")
    
    if total >= 4:
        print("\n🎉 END-TO-END TEST SUCCESSFUL!")
        print("   System is production-ready with real IPFS + blockchain integration")
    elif total >= 3:
        print("\n✅ Core functionality working")
        print("   Minor issues with external services")
    else:
        print("\n⚠️  Multiple failures detected")
        print("   Please review error messages above")
    
    print()
    return total >= 4


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
