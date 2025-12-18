"""
Merkle Proof Verification Utilities for Voice Ledger
Integrates merkle tree functionality with blockchain contracts
"""

from typing import List, Dict, Optional, Tuple
from eth_utils import keccak
from web3 import Web3
from web3.contract import Contract

from blockchain.merkle_tree import (
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof
)
from blockchain.batch_hasher import hash_batch_from_db_model


class MerkleProofManager:
    """
    Manager for creating and verifying merkle proofs for batch aggregations.
    """
    
    def __init__(
        self,
        web3: Web3,
        epcis_anchor_contract: Contract
    ):
        """
        Initialize the merkle proof manager.
        
        Args:
            web3: Web3 instance connected to blockchain
            epcis_anchor_contract: EPCISEventAnchor contract instance
        """
        self.web3 = web3
        self.epcis_anchor_contract = epcis_anchor_contract
    
    def create_aggregation_with_merkle_proof(
        self,
        container_id: str,
        child_batches: List,
        aggregation_event_data: dict
    ) -> Tuple[bytes, List[bytes], bytes]:
        """
        Create aggregation with merkle root for child batches.
        
        Args:
            container_id: Container batch ID
            child_batches: List of child CoffeeBatch database models
            aggregation_event_data: EPCIS aggregation event data
            
        Returns:
            (merkle_root, batch_hashes, aggregation_event_hash)
            
        Example:
            >>> container_id = "CONT-2025-001"
            >>> child_batches = [batch1, batch2, batch3]
            >>> event_data = {"type": "AggregationEvent", ...}
            >>> root, hashes, event_hash = manager.create_aggregation_with_merkle_proof(
            ...     container_id, child_batches, event_data
            ... )
        """
        # Hash each child batch
        batch_hashes = [hash_batch_from_db_model(batch) for batch in child_batches]
        
        # Compute merkle root
        merkle_root = compute_merkle_root(batch_hashes)
        
        # Hash aggregation event
        import json
        event_string = json.dumps(aggregation_event_data, sort_keys=True)
        aggregation_event_hash = keccak(text=event_string)
        
        return (merkle_root, batch_hashes, aggregation_event_hash)
    
    def anchor_aggregation_on_chain(
        self,
        container_id: str,
        merkle_root: bytes,
        child_batch_count: int,
        aggregation_event_hash: bytes,
        sender_address: str,
        private_key: str
    ) -> dict:
        """
        Anchor aggregation with merkle root on blockchain.
        
        Args:
            container_id: Container batch ID
            merkle_root: Computed merkle root
            child_batch_count: Number of child batches
            aggregation_event_hash: Hash of aggregation event
            sender_address: Address sending the transaction
            private_key: Private key for signing
            
        Returns:
            Transaction receipt dict
            
        Example:
            >>> receipt = manager.anchor_aggregation_on_chain(
            ...     "CONT-2025-001",
            ...     merkle_root,
            ...     3,
            ...     aggregation_event_hash,
            ...     cooperative_address,
            ...     cooperative_private_key
            ... )
        """
        # Build transaction
        tx = self.epcis_anchor_contract.functions.anchorAggregation(
            aggregation_event_hash,
            container_id,
            merkle_root,
            child_batch_count
        ).build_transaction({
            'from': sender_address,
            'nonce': self.web3.eth.get_transaction_count(sender_address),
            'gas': 300000,
            'gasPrice': self.web3.eth.gas_price
        })
        
        # Sign and send
        signed_tx = self.web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for confirmation
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        
        return receipt
    
    def generate_proof_for_batch(
        self,
        container_id: str,
        target_batch_index: int,
        all_batch_hashes: List[bytes]
    ) -> List[bytes]:
        """
        Generate merkle proof for a specific batch in a container.
        
        Args:
            container_id: Container batch ID
            target_batch_index: Index of the target batch (0-based)
            all_batch_hashes: All batch hashes in the container (in order)
            
        Returns:
            Merkle proof (array of sibling hashes)
            
        Example:
            >>> proof = manager.generate_proof_for_batch(
            ...     "CONT-2025-001",
            ...     0,  # First batch
            ...     [hash1, hash2, hash3]
            ... )
        """
        return generate_merkle_proof(all_batch_hashes, target_batch_index)
    
    def verify_batch_inclusion_on_chain(
        self,
        container_id: str,
        batch_hash: bytes,
        proof: List[bytes],
        batch_index: int
    ) -> bool:
        """
        Verify batch inclusion using on-chain contract.
        
        Args:
            container_id: Container batch ID
            batch_hash: Hash of the batch to verify
            proof: Merkle proof
            batch_index: Position of batch in tree
            
        Returns:
            True if batch was included in container
            
        Example:
            >>> is_included = manager.verify_batch_inclusion_on_chain(
            ...     "CONT-2025-001",
            ...     batch_hash,
            ...     proof,
            ...     0
            ... )
            >>> if is_included:
            ...     print("Batch was cryptographically verified!")
        """
        return self.epcis_anchor_contract.functions.verifyMerkleProof(
            container_id,
            batch_hash,
            proof,
            batch_index
        ).call()
    
    def get_aggregation_info(self, container_id: str) -> dict:
        """
        Get aggregation metadata from blockchain.
        
        Args:
            container_id: Container batch ID
            
        Returns:
            Dict with aggregation metadata
            
        Example:
            >>> info = manager.get_aggregation_info("CONT-2025-001")
            >>> print(f"Merkle root: {info['merkleRoot'].hex()}")
            >>> print(f"Child batches: {info['childBatchCount']}")
        """
        agg = self.epcis_anchor_contract.functions.getAggregation(container_id).call()
        
        return {
            'aggregationEventHash': agg[0],
            'merkleRoot': agg[1],
            'childBatchCount': agg[2],
            'timestamp': agg[3],
            'submitter': agg[4],
            'exists': agg[5]
        }


def verify_container_integrity(
    container_id: str,
    child_batches: List,
    merkle_proof_manager: MerkleProofManager
) -> Dict[str, bool]:
    """
    Verify integrity of all batches in a container.
    
    Args:
        container_id: Container batch ID
        child_batches: List of child batch database models
        merkle_proof_manager: MerkleProofManager instance
        
    Returns:
        Dict mapping batch_id to verification result
        
    Example:
        >>> results = verify_container_integrity(
        ...     "CONT-2025-001",
        ...     [batch1, batch2, batch3],
        ...     manager
        ... )
        >>> for batch_id, is_valid in results.items():
        ...     print(f"{batch_id}: {'✓' if is_valid else '✗'}")
    """
    results = {}
    
    # Get all batch hashes
    batch_hashes = [hash_batch_from_db_model(batch) for batch in child_batches]
    
    # Verify each batch
    for i, batch in enumerate(child_batches):
        batch_hash = batch_hashes[i]
        
        # Generate proof
        proof = merkle_proof_manager.generate_proof_for_batch(
            container_id,
            i,
            batch_hashes
        )
        
        # Verify on-chain
        is_valid = merkle_proof_manager.verify_batch_inclusion_on_chain(
            container_id,
            batch_hash,
            proof,
            i
        )
        
        results[batch.batch_id] = is_valid
    
    return results


# Example usage
if __name__ == "__main__":
    print("Merkle Proof Verification Utilities")
    print("=" * 50)
    print()
    print("This module provides:")
    print("  1. MerkleProofManager - Main class for proof operations")
    print("  2. create_aggregation_with_merkle_proof() - Create container with merkle root")
    print("  3. anchor_aggregation_on_chain() - Anchor to blockchain")
    print("  4. generate_proof_for_batch() - Generate proof for specific batch")
    print("  5. verify_batch_inclusion_on_chain() - Verify using smart contract")
    print("  6. verify_container_integrity() - Check all batches in container")
    print()
    print("Example workflow:")
    print()
    print("  # 1. Create aggregation")
    print("  root, hashes, event_hash = manager.create_aggregation_with_merkle_proof(")
    print("      container_id, child_batches, event_data")
    print("  )")
    print()
    print("  # 2. Anchor on blockchain")
    print("  receipt = manager.anchor_aggregation_on_chain(")
    print("      container_id, root, len(child_batches), event_hash, address, key")
    print("  )")
    print()
    print("  # 3. Later: verify a batch was included")
    print("  proof = manager.generate_proof_for_batch(container_id, 0, hashes)")
    print("  is_valid = manager.verify_batch_inclusion_on_chain(")
    print("      container_id, hashes[0], proof, 0")
    print("  )")
    print()
    print("=" * 50)
