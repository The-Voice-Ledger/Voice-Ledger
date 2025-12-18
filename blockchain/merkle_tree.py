"""
Merkle Tree Implementation for Voice Ledger
Provides cryptographic proof of batch inclusion in container aggregations
"""

import hashlib
from typing import List, Tuple
from eth_utils import keccak


def compute_merkle_root(leaf_hashes: List[bytes]) -> bytes:
    """
    Compute merkle root from list of leaf hashes.
    Uses binary merkle tree structure (pads to power of 2).
    
    Args:
        leaf_hashes: List of 32-byte hashes (one per batch)
        
    Returns:
        32-byte merkle root
        
    Example:
        >>> b0 = keccak(text="batch-0")
        >>> b1 = keccak(text="batch-1")
        >>> root = compute_merkle_root([b0, b1])
    """
    if len(leaf_hashes) == 0:
        return bytes(32)
    
    if len(leaf_hashes) == 1:
        return leaf_hashes[0]
    
    # Pad to power of 2 by duplicating last element
    current_level = leaf_hashes.copy()
    while len(current_level) & (len(current_level) - 1):
        current_level.append(current_level[-1])
    
    # Build tree bottom-up
    while len(current_level) > 1:
        next_level = []
        
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            
            # Hash concatenation (matches Solidity: keccak256(abi.encodePacked(left, right)))
            combined = keccak(left + right)
            next_level.append(combined)
        
        current_level = next_level
    
    return current_level[0]


def generate_merkle_proof(leaf_hashes: List[bytes], target_index: int) -> List[bytes]:
    """
    Generate merkle proof for a specific leaf.
    Returns array of sibling hashes from leaf to root.
    
    Args:
        leaf_hashes: All leaf hashes in the tree
        target_index: Index of the leaf to prove (0-based)
        
    Returns:
        List of sibling hashes (proof path)
        
    Example:
        >>> leaves = [keccak(text=f"batch-{i}") for i in range(4)]
        >>> proof = generate_merkle_proof(leaves, 0)
        >>> # proof[0] = sibling at level 0, proof[1] = sibling at level 1, etc.
    """
    if target_index >= len(leaf_hashes):
        raise ValueError(f"Target index {target_index} out of range (max: {len(leaf_hashes)-1})")
    
    if len(leaf_hashes) == 0:
        return []
    
    if len(leaf_hashes) == 1:
        return []
    
    # Pad to power of 2
    current_level = leaf_hashes.copy()
    while len(current_level) & (len(current_level) - 1):
        current_level.append(current_level[-1])
    
    # Build proof by collecting siblings
    proof = []
    index = target_index
    
    while len(current_level) > 1:
        next_level = []
        
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            
            # If this pair contains our target, save the sibling
            if i == index or i + 1 == index:
                if index % 2 == 0:
                    # Target is left child, save right sibling
                    proof.append(right)
                else:
                    # Target is right child, save left sibling
                    proof.append(left)
            
            # Hash and move to next level
            combined = keccak(left + right)
            next_level.append(combined)
        
        # Update index for next level
        index = index // 2
        current_level = next_level
    
    return proof


def verify_merkle_proof(
    leaf_hash: bytes,
    proof: List[bytes],
    merkle_root: bytes,
    index: int
) -> bool:
    """
    Verify a merkle proof off-chain (for testing).
    Matches the on-chain verification logic in EPCISEventAnchor.sol
    
    Args:
        leaf_hash: Hash of the batch data
        proof: Array of sibling hashes
        merkle_root: Expected root hash
        index: Position of leaf in tree (0-based)
        
    Returns:
        True if proof is valid
        
    Example:
        >>> leaves = [keccak(text=f"batch-{i}") for i in range(4)]
        >>> root = compute_merkle_root(leaves)
        >>> proof = generate_merkle_proof(leaves, 0)
        >>> verify_merkle_proof(leaves[0], proof, root, 0)
        True
    """
    computed_hash = leaf_hash
    
    for sibling in proof:
        if index % 2 == 0:
            # Current node is left child
            computed_hash = keccak(computed_hash + sibling)
        else:
            # Current node is right child
            computed_hash = keccak(sibling + computed_hash)
        
        index = index // 2
    
    return computed_hash == merkle_root


def get_tree_info(leaf_count: int) -> Tuple[int, int]:
    """
    Get merkle tree information for a given number of leaves.
    
    Args:
        leaf_count: Number of leaves in the tree
        
    Returns:
        (padded_size, tree_height)
        
    Example:
        >>> get_tree_info(3)
        (4, 2)  # Pads to 4 leaves, height 2
    """
    if leaf_count == 0:
        return (0, 0)
    
    # Pad to next power of 2
    padded = leaf_count
    while padded & (padded - 1):
        padded += 1
    
    # Calculate height
    height = 0
    temp = padded
    while temp > 1:
        temp //= 2
        height += 1
    
    return (padded, height)


# Example usage and testing
if __name__ == "__main__":
    print("Merkle Tree Implementation Test")
    print("=" * 50)
    
    # Test 1: Two batches
    print("\n1. Two Batches")
    b0 = keccak(text="batch-0")
    b1 = keccak(text="batch-1")
    
    root = compute_merkle_root([b0, b1])
    print(f"Root: {root.hex()}")
    
    proof0 = generate_merkle_proof([b0, b1], 0)
    print(f"Proof for batch-0: {[p.hex() for p in proof0]}")
    
    valid = verify_merkle_proof(b0, proof0, root, 0)
    print(f"Verification: {'✓ Valid' if valid else '✗ Invalid'}")
    
    # Test 2: Four batches
    print("\n2. Four Batches")
    leaves = [keccak(text=f"batch-{i}") for i in range(4)]
    
    root = compute_merkle_root(leaves)
    print(f"Root: {root.hex()}")
    
    for i in range(4):
        proof = generate_merkle_proof(leaves, i)
        valid = verify_merkle_proof(leaves[i], proof, root, i)
        print(f"Batch {i}: {'✓ Valid' if valid else '✗ Invalid'} (proof length: {len(proof)})")
    
    # Test 3: Odd number (3 batches - pads to 4)
    print("\n3. Three Batches (padded to 4)")
    leaves = [keccak(text=f"batch-{i}") for i in range(3)]
    
    padded_size, height = get_tree_info(len(leaves))
    print(f"Tree info: {len(leaves)} leaves → {padded_size} padded, height {height}")
    
    root = compute_merkle_root(leaves)
    print(f"Root: {root.hex()}")
    
    for i in range(len(leaves)):
        proof = generate_merkle_proof(leaves, i)
        valid = verify_merkle_proof(leaves[i], proof, root, i)
        print(f"Batch {i}: {'✓ Valid' if valid else '✗ Invalid'}")
    
    # Test 4: Invalid proof
    print("\n4. Invalid Proof Test")
    leaves = [keccak(text=f"batch-{i}") for i in range(2)]
    root = compute_merkle_root(leaves)
    
    fake_leaf = keccak(text="fake-batch")
    proof = generate_merkle_proof(leaves, 0)
    valid = verify_merkle_proof(fake_leaf, proof, root, 0)
    print(f"Fake batch verification: {'✓ Valid' if valid else '✗ Invalid (expected)'}")
    
    print("\n" + "=" * 50)
    print("All tests complete!")
