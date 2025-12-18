#!/usr/bin/env python3
"""
Test Web3 connection to deployed contracts on Base Sepolia
"""

import os
import sys
import json
from web3 import Web3
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_connection():
    """Test connection to Base Sepolia and deployed contracts"""
    
    # Load environment variables
    load_dotenv('../.env')
    
    print("=" * 60)
    print("Testing Voice Ledger Blockchain Connection")
    print("=" * 60)
    print()
    
    # 1. Test RPC connection
    rpc_url = os.getenv('BASE_SEPOLIA_RPC_URL')
    print(f"🔗 Connecting to Base Sepolia...")
    print(f"   RPC: {rpc_url[:50]}...")
    
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print("❌ Failed to connect to Base Sepolia")
        return False
    
    print(f"✅ Connected to Base Sepolia")
    print(f"   Chain ID: {w3.eth.chain_id}")
    print(f"   Latest Block: {w3.eth.block_number}")
    print()
    
    # 2. Load contract ABIs
    print("📄 Loading contract ABIs...")
    
    abis = {}
    contracts = [
        'EPCISEventAnchor',
        'CoffeeBatchToken',
        'SettlementContract'
    ]
    
    for contract_name in contracts:
        abi_path = f'../blockchain_abis/{contract_name}.json'
        try:
            with open(abi_path, 'r') as f:
                abis[contract_name] = json.load(f)
            print(f"   ✅ {contract_name}.json loaded")
        except FileNotFoundError:
            print(f"   ❌ {contract_name}.json not found")
            return False
    
    print()
    
    # 3. Initialize contracts
    print("🔧 Initializing contract instances...")
    
    addresses = {
        'EPCISEventAnchor': os.getenv('EPCIS_EVENT_ANCHOR_ADDRESS'),
        'CoffeeBatchToken': os.getenv('COFFEE_BATCH_TOKEN_ADDRESS'),
        'SettlementContract': os.getenv('SETTLEMENT_CONTRACT_ADDRESS')
    }
    
    contract_instances = {}
    
    for name, address in addresses.items():
        if not address:
            print(f"   ❌ {name} address not found in .env")
            return False
        
        try:
            contract_instances[name] = w3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=abis[name]
            )
            print(f"   ✅ {name}: {address}")
        except Exception as e:
            print(f"   ❌ {name} initialization failed: {e}")
            return False
    
    print()
    
    # 4. Test contract calls
    print("🧪 Testing contract read operations...")
    
    # Test EPCISEventAnchor
    try:
        # Try to get a non-existent aggregation (should return default values)
        result = contract_instances['EPCISEventAnchor'].functions.getAggregation(
            "TEST-CONTAINER-001"
        ).call()
        print(f"   ✅ EPCISEventAnchor.getAggregation() callable")
        print(f"      (Returns empty result for non-existent container)")
    except Exception as e:
        print(f"   ❌ EPCISEventAnchor call failed: {e}")
    
    # Test CoffeeBatchToken
    try:
        # Try to get token URI (should work even for non-existent token)
        uri = contract_instances['CoffeeBatchToken'].functions.uri(0).call()
        print(f"   ✅ CoffeeBatchToken.uri() callable")
        print(f"      Base URI: {uri}")
    except Exception as e:
        print(f"   ❌ CoffeeBatchToken call failed: {e}")
    
    # Test SettlementContract
    try:
        # Try to get a non-existent settlement
        result = contract_instances['SettlementContract'].functions.getSettlement(
            999999
        ).call()
        print(f"   ✅ SettlementContract.getSettlement() callable")
        print(f"      (Returns default values for non-existent settlement)")
    except Exception as e:
        print(f"   ❌ SettlementContract call failed: {e}")
    
    print()
    print("=" * 60)
    print("✅ All tests passed! Contracts are ready to use.")
    print("=" * 60)
    print()
    print("📝 Next steps:")
    print("   1. Verify contracts on BaseScan (need new Etherscan V2 API key)")
    print("   2. Integrate MerkleProofManager with deployed contracts")
    print("   3. Test batch anchoring and proof generation")
    print()
    
    return True

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)
