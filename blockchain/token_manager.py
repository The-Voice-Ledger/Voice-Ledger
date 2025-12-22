#!/usr/bin/env python3
"""
CoffeeBatchToken Manager - Mints batch tokens during commission events

Integrates with existing IPFS+blockchain flow.
Cooperative custodial model: tokens minted to cooperative wallet, 
farmer tracked as originator in database.

Flow:
1. Farmer commissions batch via voice → PostgreSQL + IPFS + blockchain event
2. This module mints batch token to cooperative wallet (custodian)
3. Token ID stored in batch record (batch.token_id)
4. Farmer remains owner in database (batch.created_by_user_id)
5. On-chain: cooperative owns token for aggregation/transfers
6. Off-chain: farmer credited in database for settlement

Updated: December 21, 2025
"""

import os
import sys
import json
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class CoffeeBatchTokenManager:
    """Manages batch token minting during farmer commission"""
    
    def __init__(self):
        """Initialize Web3 connection and contract"""
        
        self.rpc_url = os.getenv('BASE_SEPOLIA_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY_SEP')
        self.contract_address = os.getenv('COFFEE_BATCH_TOKEN_ADDRESS')
        
        if not all([self.rpc_url, self.private_key, self.contract_address]):
            raise ValueError(
                "Missing required environment variables: "
                "BASE_SEPOLIA_RPC_URL, PRIVATE_KEY_SEP, COFFEE_BATCH_TOKEN_ADDRESS"
            )
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.rpc_url}")
        
        # Load account (cooperative wallet)
        self.account = Account.from_key(self.private_key)
        
        # Load contract ABI
        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'blockchain_abis',
            'CoffeeBatchToken.json'
        )
        
        try:
            with open(abi_path, 'r') as f:
                contract_data = json.load(f)
                # Handle both array ABI and {abi: [...]} format
                abi = contract_data if isinstance(contract_data, list) else contract_data.get('abi', contract_data)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"CoffeeBatchToken ABI not found at {abi_path}. "
                "Run: forge build && python blockchain/extract_abis.py"
            )
        
        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=abi
        )
        
        print(f"✓ CoffeeBatchTokenManager initialized")
        print(f"  Chain ID: {self.w3.eth.chain_id}")
        print(f"  Cooperative wallet: {self.account.address}")
        print(f"  Token contract: {self.contract_address}")
    
    def mint_batch(
        self,
        recipient: str,
        quantity_kg: float,
        batch_id: str,
        metadata: Dict[str, Any],
        ipfs_cid: str
    ) -> Optional[int]:
        """
        Mint batch token to cooperative wallet (custodian).
        
        Args:
            recipient: Cooperative wallet address (receives token)
            quantity_kg: Batch quantity in kilograms
            batch_id: Unique batch identifier (e.g., "FARM_YEHA_1735305600_ABC123")
            metadata: Batch metadata dict:
                - variety: Coffee variety
                - origin: Farm location
                - processing_method: Washed/Natural/Honey
                - quality_grade: A/B/C
                - farmer_did: Farmer's DID
                - gtin: GS1 GTIN
                - gln: GS1 GLN
            ipfs_cid: IPFS CID of commission event
        
        Returns:
            Token ID (uint256) if successful, None if failed
        """
        try:
            # Validate inputs
            if quantity_kg <= 0:
                raise ValueError(f"Invalid quantity: {quantity_kg} kg")
            
            # Validate IPFS CID (CIDv0 starts with Qm, CIDv1 starts with bafy)
            if not ipfs_cid or not (ipfs_cid.startswith('Qm') or ipfs_cid.startswith('bafy')):
                raise ValueError(f"Invalid IPFS CID: {ipfs_cid}")
            
            # Prepare metadata JSON
            metadata_json = json.dumps(metadata, separators=(',', ':'))
            
            # Convert kg to grams for smart contract (uint256 precision)
            quantity_grams = int(quantity_kg * 1000)
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')  # Use pending nonce
            gas_price = self.w3.eth.gas_price
            
            tx = self.contract.functions.mintBatch(
                Web3.to_checksum_address(recipient),
                quantity_grams,
                batch_id,
                metadata_json,
                ipfs_cid
            ).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 500000,
                'gasPrice': int(gas_price * 1.2),  # Add 20% buffer for gas price
                'nonce': nonce,
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            print(f"  Transaction sent: {tx_hash.hex()}")
            print(f"  Waiting for confirmation...")
            
            # Wait for receipt (30 second timeout)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            
            if receipt['status'] == 1:
                # mintBatch returns the token ID - parse it from logs or call balanceOf
                # Since we just minted, the token ID is the next sequential ID
                # Get total supply or use a different method
                print(f"✓ Batch token minted successfully!")
                print(f"  Batch ID: {batch_id}")
                print(f"  Quantity: {quantity_kg} kg")
                print(f"  IPFS CID: {ipfs_cid}")
                print(f"  TX hash: {tx_hash.hex()}")
                
                # Query the token ID by batch_id (with retry for propagation delay)
                import time
                for attempt in range(3):
                    try:
                        token_id = self.contract.functions.getTokenIdByBatchId(batch_id).call()
                        print(f"  Token ID: {token_id}")
                        return token_id
                    except Exception as e:
                        if attempt < 2:
                            print(f"  Retrying token ID query (attempt {attempt + 2}/3)...")
                            time.sleep(2)
                        else:
                            print(f"⚠ Couldn't query token ID after {attempt + 1} attempts: {e}")
                            print(f"  Token was minted successfully - check Base Sepolia explorer")
                            print(f"  TX: https://sepolia.basescan.org/tx/{tx_hash.hex()}")
                            return None
            else:
                print(f"❌ Token minting transaction failed")
                print(f"  TX hash: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            print(f"❌ Failed to mint batch token: {e}")
            return None
    
    def mint_container(
        self,
        recipient: str,
        quantity_kg: float,
        container_id: str,
        metadata: Dict[str, Any],
        ipfs_cid: str,
        child_token_ids: list[int],
        child_holders: list[str]
    ) -> Optional[int]:
        """
        Mint an aggregated container token from multiple child batches.
        Burns child tokens and creates new parent container token.
        
        Args:
            recipient: Cooperative wallet address receiving container token
            quantity_kg: Total quantity in kg (sum of children)
            container_id: SSCC or unique container identifier
            metadata: Container metadata dict:
                - container_type: pallet/container/truck
                - child_count: Number of child batches
                - aggregation_date: ISO 8601 timestamp
                - location_gln: Where aggregation occurred
            ipfs_cid: IPFS CID of aggregation event
            child_token_ids: Array of child batch token IDs to burn
            child_holders: Array of addresses holding child tokens (parallel to child_token_ids)
        
        Returns:
            Container token ID (uint256) if successful, None if failed
        """
        try:
            # Validate inputs
            if quantity_kg <= 0:
                raise ValueError(f"Invalid quantity: {quantity_kg} kg")
            
            if not child_token_ids or len(child_token_ids) < 2:
                raise ValueError("Need at least 2 child tokens to create container")
            
            if len(child_token_ids) != len(child_holders):
                raise ValueError(f"Mismatch: {len(child_token_ids)} tokens but {len(child_holders)} holders")
            
            # Validate IPFS CID
            if not ipfs_cid or not (ipfs_cid.startswith('Qm') or ipfs_cid.startswith('bafy')):
                raise ValueError(f"Invalid IPFS CID: {ipfs_cid}")
            
            # Prepare metadata JSON
            metadata_json = json.dumps(metadata, separators=(',', ':'))
            
            # Convert kg to grams
            quantity_grams = int(quantity_kg * 1000)
            
            # Convert holders to checksum addresses
            checksum_holders = [Web3.to_checksum_address(h) for h in child_holders]
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            gas_price = self.w3.eth.gas_price
            
            tx = self.contract.functions.mintContainer(
                Web3.to_checksum_address(recipient),
                quantity_grams,
                container_id,
                metadata_json,
                ipfs_cid,
                child_token_ids,
                checksum_holders
            ).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 800000,  # Higher gas for container (burns + mint)
                'gasPrice': int(gas_price * 1.2),
                'nonce': nonce,
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            print(f"  Container minting transaction sent: {tx_hash.hex()}")
            print(f"  Burning {len(child_token_ids)} child tokens...")
            
            # Wait for receipt (60 second timeout for more complex tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                print(f"✓ Container token minted successfully!")
                print(f"  Container ID: {container_id}")
                print(f"  Total Quantity: {quantity_kg} kg")
                print(f"  Child batches burned: {len(child_token_ids)}")
                print(f"  IPFS CID: {ipfs_cid}")
                print(f"  TX hash: {tx_hash.hex()}")
                
                # Query the container token ID by container_id (with retry)
                import time
                for attempt in range(3):
                    try:
                        token_id = self.contract.functions.getTokenIdByBatchId(container_id).call()
                        print(f"  Container Token ID: {token_id}")
                        
                        # Verify it's actually a container
                        is_container = self.contract.functions.isContainer(token_id).call()
                        if is_container:
                            print(f"  ✓ Verified as container token")
                        
                        return token_id
                    except Exception as e:
                        if attempt < 2:
                            print(f"  Retrying token ID query (attempt {attempt + 2}/3)...")
                            time.sleep(2)
                        else:
                            print(f"⚠ Couldn't query token ID after {attempt + 1} attempts: {e}")
                            print(f"  Container was minted successfully - check Base Sepolia explorer")
                            print(f"  TX: https://sepolia.basescan.org/tx/{tx_hash.hex()}")
                            return None
            else:
                print(f"❌ Container minting transaction failed")
                print(f"  TX hash: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            print(f"❌ Failed to mint container token: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_batch_metadata(self, token_id: int) -> Optional[Dict[str, Any]]:
        """
        Query batch metadata from smart contract.
        
        Args:
            token_id: Token ID to query
        
        Returns:
            Dict with batch metadata or None if failed
        """
        try:
            metadata = self.contract.functions.getBatchMetadata(token_id).call()
            
            return {
                'batch_id': metadata[0],
                'quantity': metadata[1],
                'metadata_json': metadata[2],
                'ipfs_cid': metadata[3],
                'is_aggregated': metadata[4],
                'child_token_ids': list(metadata[5])
            }
            
        except Exception as e:
            print(f"❌ Failed to query batch {token_id}: {e}")
            return None
    
    def get_batch_balance(self, owner: str, token_id: int) -> int:
        """
        Query token balance for owner.
        
        Args:
            owner: Wallet address
            token_id: Token ID
        
        Returns:
            Balance (in grams)
        """
        try:
            balance = self.contract.functions.balanceOf(
                Web3.to_checksum_address(owner),
                token_id
            ).call()
            return balance
            
        except Exception as e:
            print(f"❌ Failed to query balance: {e}")
            return 0

# Global instance (singleton pattern)
_token_manager = None

def get_token_manager() -> CoffeeBatchTokenManager:
    """Get singleton token manager instance"""
    global _token_manager
    if _token_manager is None:
        _token_manager = CoffeeBatchTokenManager()
    return _token_manager

def mint_batch_token(
    recipient: str,
    quantity_kg: float,
    batch_id: str,
    metadata: Dict[str, Any],
    ipfs_cid: str
) -> Optional[int]:
    """
    Convenience function to mint batch token.
    
    Args:
        recipient: Cooperative wallet address
        quantity_kg: Batch quantity in kg
        batch_id: Unique batch identifier
        metadata: Batch metadata dict
        ipfs_cid: IPFS CID of commission event
    
    Returns:
        Token ID if successful, None if failed
    """
    manager = get_token_manager()
    return manager.mint_batch(recipient, quantity_kg, batch_id, metadata, ipfs_cid)

def mint_container_token(
    recipient: str,
    quantity_kg: float,
    container_id: str,
    metadata: Dict[str, Any],
    ipfs_cid: str,
    child_token_ids: list[int],
    child_holders: list[str]
) -> Optional[int]:
    """
    Convenience function to mint container token.
    
    Args:
        recipient: Cooperative wallet address
        quantity_kg: Total container quantity in kg
        container_id: SSCC or unique container identifier
        metadata: Container metadata dict
        ipfs_cid: IPFS CID of aggregation event
        child_token_ids: Array of child batch token IDs to burn
        child_holders: Array of addresses holding child tokens
    
    Returns:
        Container token ID if successful, None if failed
    """
    manager = get_token_manager()
    return manager.mint_container(
        recipient, quantity_kg, container_id, metadata,
        ipfs_cid, child_token_ids, child_holders
    )

# CLI testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Mint coffee batch token')
    parser.add_argument('--recipient', required=True, help='Recipient wallet address')
    parser.add_argument('--quantity', type=float, required=True, help='Quantity in kg')
    parser.add_argument('--batch-id', required=True, help='Unique batch ID')
    parser.add_argument('--ipfs-cid', required=True, help='IPFS CID of event')
    parser.add_argument('--variety', default='Arabica', help='Coffee variety')
    parser.add_argument('--origin', default='Yeha', help='Origin location')
    
    args = parser.parse_args()
    
    metadata = {
        'variety': args.variety,
        'origin': args.origin,
        'processing_method': 'Washed',
        'quality_grade': 'A',
        'farmer_did': 'did:test:farmer001',
        'gtin': '00000000000000',
        'gln': '0000000000000'
    }
    
    token_id = mint_batch_token(
        recipient=args.recipient,
        quantity_kg=args.quantity,
        batch_id=args.batch_id,
        metadata=metadata,
        ipfs_cid=args.ipfs_cid
    )
    
    if token_id:
        print(f"\n✅ Success! Token ID: {token_id}")
    else:
        print(f"\n❌ Failed to mint token")
        sys.exit(1)
