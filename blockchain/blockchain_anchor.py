#!/usr/bin/env python3
"""
Blockchain Anchoring Module

Anchors EPCIS events to Base Sepolia blockchain after IPFS pinning.
Integrates with deployed EPCISEventAnchor smart contract.

Flow:
1. EPCIS event created → hash generated
2. Event pinned to IPFS → CID stored
3. Event hash anchored to blockchain → tx hash stored
4. Database updated with blockchain confirmation

Updated: December 18, 2025
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Add parent to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class BlockchainAnchor:
    """Manages blockchain anchoring of EPCIS events"""
    
    def __init__(self):
        """Initialize Web3 connection and contract"""
        
        # Load configuration
        self.rpc_url = os.getenv('BASE_SEPOLIA_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY_SEP')
        self.contract_address = os.getenv('EPCIS_EVENT_ANCHOR_ADDRESS')
        
        if not all([self.rpc_url, self.private_key, self.contract_address]):
            raise ValueError(
                "Missing required environment variables: "
                "BASE_SEPOLIA_RPC_URL, PRIVATE_KEY_SEP, EPCIS_EVENT_ANCHOR_ADDRESS"
            )
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.rpc_url}")
        
        # Load account
        self.account = Account.from_key(self.private_key)
        
        # Load contract ABI
        abi_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'blockchain_abis',
            'EPCISEventAnchor.json'
        )
        
        with open(abi_path, 'r') as f:
            contract_json = json.load(f)
            # Extract just the ABI array (file has {"abi": [...]})
            abi = contract_json.get('abi', contract_json)
        
        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=abi
        )
        
        logger.info("BlockchainAnchor initialized  chain=%s  account=%s  contract=%s",
                    self.w3.eth.chain_id, self.account.address, self.contract_address)
    
    def anchor_event(
        self,
        batch_id: str,
        event_hash: str,
        ipfs_cid: Optional[str] = None,
        event_type: str = "ObjectEvent",
        location: str = "",
        submitter: str = ""
    ) -> Optional[str]:
        """
        Anchor EPCIS event to blockchain.
        
        Args:
            batch_id: Coffee batch identifier (e.g., "FARM-001")
            event_hash: Keccak256 hash of event (0x...)
            ipfs_cid: IPFS CID where full event is stored
            event_type: EPCIS event type
            location: Event location
            submitter: DID or address of submitter
        
        Returns:
            Transaction hash if successful, None if failed
        """
        try:
            # Ensure hash has 0x prefix
            if not event_hash.startswith('0x'):
                event_hash = '0x' + event_hash
            
            # Convert hash to bytes32
            event_hash_bytes = Web3.to_bytes(hexstr=event_hash)
            
            # Prepare metadata
            metadata = (
                event_type,
                location,
                ipfs_cid or "",
                submitter
            )
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            
            # Estimate gas
            gas_estimate = self.contract.functions.anchorEvent(
                event_hash_bytes,
                batch_id,
                event_type
            ).estimate_gas({
                'from': self.account.address
            })
            
            # Build transaction
            tx = self.contract.functions.anchorEvent(
                event_hash_bytes,
                batch_id,
                event_type
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': int(gas_estimate * 1.2),  # 20% buffer
                'maxFeePerGas': self.w3.eth.gas_price * 2,
                'maxPriorityFeePerGas': self.w3.to_wei(0.001, 'gwei'),
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign transaction
            signed_tx = self.account.sign_transaction(tx)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            logger.info("Anchor tx sent  batch=%s  hash=%s  tx=%s", batch_id, event_hash[:10], tx_hash_hex)

            # Wait for on-chain confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] != 1:
                logger.error("Anchor tx reverted  tx=%s  batch=%s", tx_hash_hex, batch_id)
                return None

            logger.info("Anchor confirmed  block=%s  gas=%s", receipt['blockNumber'], receipt['gasUsed'])
            return tx_hash_hex

        except Exception as e:
            logger.exception("Blockchain anchoring failed  batch=%s", batch_id)
            return None
    
    def get_batch_info(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """
        Query batch information from blockchain.
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            Dict with batch info or None if not found
        """
        try:
            from database import get_db
            from database.models import EPCISEvent, CoffeeBatch
            
            # Step 1: Query database to get event_hash for this batch
            with get_db() as db:
                # Find the batch first
                batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
                if not batch:
                    logger.warning("Batch %s not found in database", batch_id)
                    return None
                
                # Find the most recent EPCIS event for this batch
                event = db.query(EPCISEvent).filter(
                    EPCISEvent.batch_id == batch.id
                ).order_by(EPCISEvent.created_at.desc()).first()
                
                if not event or not event.event_hash:
                    logger.warning("No event hash found for batch %s", batch_id)
                    return None
                
                # Step 2: Query blockchain using event_hash
                event_hash_bytes = bytes.fromhex(event.event_hash)
                try:
                    result = self.contract.functions.getEventMetadata(event_hash_bytes).call()
                except Exception as contract_error:
                    # Handle contract revert (event not found on blockchain)
                    error_msg = str(contract_error)
                    if 'EventNotFound' in error_msg or 'revert' in error_msg.lower():
                        logger.info("Event hash %s not found on blockchain (batch not anchored yet)", event.event_hash)
                        return {
                            'batch_id': batch_id,
                            'event_hash': event.event_hash,
                            'event_type': event.event_type,
                            'blockchain_verified': False,
                            'status': 'NOT_ANCHORED'
                        }
                    raise
                
                # Unpack result: (batchId, eventType, timestamp, submitter, exists)
                batch_id_onchain, event_type, timestamp, submitter, exists = result
                
                if not exists:
                    logger.info("Event hash %s not found on blockchain (exists=false)", event.event_hash)
                    return {
                        'batch_id': batch_id,
                        'event_hash': event.event_hash,
                        'event_type': event_type,
                        'blockchain_verified': False,
                        'status': 'NOT_ANCHORED'
                    }
                
                return {
                    'batch_id': batch_id,
                    'event_hash': event.event_hash,
                    'event_type': event_type,
                    'timestamp': timestamp,
                    'submitter': submitter,
                    'ipfs_cid': event.ipfs_cid or None,
                    'blockchain_verified': True
                }
            
        except Exception as e:
            logger.exception("Failed to query batch %s", batch_id)
            return None
    
    def verify_event_hash(self, batch_id: str, event_hash: str) -> bool:
        """
        Verify event hash matches what's on blockchain.
        
        Args:
            batch_id: Batch identifier
            event_hash: Expected event hash
        
        Returns:
            True if hash matches blockchain, False otherwise
        """
        try:
            batch_info = self.get_batch_info(batch_id)
            if not batch_info:
                return False
            
            # Normalize hashes for comparison
            stored_hash = batch_info['event_hash']
            if not event_hash.startswith('0x'):
                event_hash = '0x' + event_hash
            
            return stored_hash.lower() == event_hash.lower()
            
        except Exception as e:
            logger.exception("Hash verification failed  batch=%s", batch_id)
            return False


# ── Singleton ────────────────────────────────────────────
_anchor: Optional[BlockchainAnchor] = None


def get_blockchain_anchor() -> BlockchainAnchor:
    """Get or create the singleton BlockchainAnchor instance."""
    global _anchor
    if _anchor is None:
        _anchor = BlockchainAnchor()
    return _anchor


def anchor_event_to_blockchain(
    batch_id: str,
    event_hash: str,
    ipfs_cid: Optional[str] = None,
    event_type: str = "ObjectEvent",
    location: str = "",
    submitter: str = ""
) -> Optional[str]:
    """
    Convenience function to anchor event to blockchain.
    Uses the singleton BlockchainAnchor instance.

    Returns:
        Transaction hash or None
    """
    try:
        anchor = get_blockchain_anchor()
        return anchor.anchor_event(
            batch_id=batch_id,
            event_hash=event_hash,
            ipfs_cid=ipfs_cid,
            event_type=event_type,
            location=location,
            submitter=submitter
        )
    except Exception as e:
        logger.exception("Anchoring failed  batch=%s", batch_id)
        return None


if __name__ == '__main__':
    """Test blockchain anchoring"""
    
    print("=" * 60)
    print("Testing Blockchain Anchoring")
    print("=" * 60)
    print()
    
    # Initialize
    anchor = BlockchainAnchor()
    
    # Test event
    test_batch_id = "TEST-BATCH-001"
    test_hash = "0x" + "a" * 64  # Dummy hash
    test_ipfs_cid = "QmTest123..."
    
    print("Testing event anchoring...")
    print(f"  Batch: {test_batch_id}")
    print(f"  Hash: {test_hash[:20]}...")
    print()
    
    # Anchor event
    tx_hash = anchor.anchor_event(
        batch_id=test_batch_id,
        event_hash=test_hash,
        ipfs_cid=test_ipfs_cid,
        event_type="ObjectEvent",
        location="Addis Ababa",
        submitter="did:key:test"
    )
    
    if tx_hash:
        print()
        print("✅ Test successful!")
        print(f"   View on BaseScan: https://sepolia.basescan.org/tx/{tx_hash}")
    else:
        print()
        print("❌ Test failed")
