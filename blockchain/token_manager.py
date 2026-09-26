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
import logging
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
        
        logger.info("CoffeeBatchTokenManager initialized  chain=%s  wallet=%s  contract=%s",
                    self.w3.eth.chain_id, self.account.address, self.contract_address)
        
        # Verify wallet is the contract owner — logs a warning if not so we know
        # before attempting any mint that will revert with OwnableUnauthorizedAccount.
        try:
            owner = self.contract.functions.owner().call()
            if owner.lower() != self.account.address.lower():
                logger.warning(
                    "WALLET IS NOT CONTRACT OWNER — minting will revert!  "
                    "wallet=%s  contract_owner=%s  contract=%s  "
                    "Fix: call transferOwnership(%s) from the owner account, "
                    "or update PRIVATE_KEY_SEP in .env to the owner's key.",
                    self.account.address, owner, self.contract_address,
                    self.account.address,
                )
            else:
                logger.info("Ownership confirmed  owner=%s", owner)
        except Exception as e:
            logger.warning("Could not verify contract ownership: %s", e)
        
        # Ensure the contract is approved to burn tokens held by this wallet.
        # mintContainer burns child tokens via _burnFrom which requires
        # isApprovedForAll(wallet, contract) == True.
        # This is a one-time setup; the call is skipped if already approved.
        try:
            already_approved = self.contract.functions.isApprovedForAll(
                self.account.address,
                Web3.to_checksum_address(self.contract_address),
            ).call()
            if not already_approved:
                logger.info(
                    "Setting approval: wallet %s → contract %s (needed for mintContainer burns)",
                    self.account.address, self.contract_address,
                )
                nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
                tx = self.contract.functions.setApprovalForAll(
                    Web3.to_checksum_address(self.contract_address), True
                ).build_transaction({
                    'chainId': self.w3.eth.chain_id,
                    'gas': 60000,
                    'gasPrice': int(self.w3.eth.gas_price * 1.2),
                    'nonce': nonce,
                })
                signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                if receipt['status'] == 1:
                    logger.info("setApprovalForAll confirmed  tx=%s", tx_hash.hex())
                    # Wait 1s for the node to index the new approval state
                    # before any subsequent estimate_gas calls use it.
                    import time as _time
                    _time.sleep(1)
                else:
                    logger.warning("setApprovalForAll reverted  tx=%s", tx_hash.hex())
            else:
                logger.debug("Contract already approved to burn tokens for wallet %s", self.account.address)
        except Exception as e:
            logger.warning("Could not set approval for contract burns: %s", e)
    
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
            
            # Pre-mint guard: check if this batch_id is already on-chain.
            # This catches BatchIdAlreadyExists without wasting gas on a reverted tx.
            try:
                existing_token_id = self.contract.functions.getTokenIdByBatchId(batch_id).call()
                if existing_token_id and existing_token_id != 0:
                    logger.info(
                        "Batch %s already has token ID %s on-chain — skipping mint",
                        batch_id, existing_token_id,
                    )
                    return existing_token_id
            except Exception as pre_check_exc:
                # getTokenIdByBatchId may revert with BatchIdNotFound — that's fine,
                # it means the batch doesn't exist yet and we should proceed.
                logger.debug(
                    "Pre-mint check for batch %s: %s (proceeding with mint)",
                    batch_id, pre_check_exc,
                )
            
            # Prepare metadata JSON
            metadata_json = json.dumps(metadata, separators=(',', ':'))
            
            # Convert kg to grams for smart contract (uint256 precision)
            quantity_grams = int(quantity_kg * 1000)
            
            # Build transaction — estimate gas dynamically so large metadata
            # strings don't hit the hardcoded 500k ceiling.
            nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            gas_price = self.w3.eth.gas_price

            mint_fn = self.contract.functions.mintBatch(
                Web3.to_checksum_address(recipient),
                quantity_grams,
                batch_id,
                metadata_json,
                ipfs_cid
            )

            try:
                estimated_gas = mint_fn.estimate_gas({'from': self.account.address})
                gas_limit = int(estimated_gas * 1.3)  # 30% buffer for safety
                logger.debug("Gas estimate for mintBatch: %d  limit: %d", estimated_gas, gas_limit)
            except Exception as est_exc:
                # If estimation itself fails the call would revert — log and bail early
                logger.error(
                    "Gas estimation failed for mintBatch  batch=%s  error=%s  "
                    "(tx would revert — not sending)",
                    batch_id, est_exc,
                )
                return None

            tx = mint_fn.build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': gas_limit,
                'gasPrice': int(gas_price * 1.2),
                'nonce': nonce,
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info("Mint tx sent: %s - waiting for confirmation", tx_hash.hex())
            
            # Wait for receipt (30 second timeout)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            
            if receipt['status'] == 1:
                logger.info("Batch token minted  batch=%s  qty=%skg  ipfs=%s  tx=%s",
                            batch_id, quantity_kg, ipfs_cid, tx_hash.hex())
                
                # Query the token ID by batch_id (with retry for propagation delay)
                import time
                for attempt in range(3):
                    try:
                        token_id = self.contract.functions.getTokenIdByBatchId(batch_id).call()
                        logger.info("Token ID resolved: %s", token_id)
                        return token_id
                    except Exception as e:
                        if attempt < 2:
                            logger.debug("Retrying token ID query (attempt %d/3)", attempt + 2)
                            time.sleep(2)
                        else:
                            logger.warning("Could not query token ID after 3 attempts: %s  tx=%s",
                                           e, tx_hash.hex())
                            return None
            else:
                # Fetch the revert reason
                revert_reason = "unknown"
                # Decode known custom errors from raw revert data before trying eth_call
                raw_revert = None
                try:
                    raw_revert = self.w3.eth.get_transaction_receipt(tx_hash)
                except Exception:
                    pass

                # OwnableUnauthorizedAccount(address) → selector 0x118cdaa7
                OWNABLE_UNAUTHORIZED = "118cdaa7"
                # BatchIdAlreadyExists(string) → selector from ABI
                BATCH_EXISTS = "BatchIdAlreadyExists"

                try:
                    # Decode from tx receipt logs or raw revert payload
                    reason_data = ""
                    if isinstance(raw_revert, dict):
                        reason_data = str(raw_revert)
                    # Try eth_call replay
                    for block_id in (receipt["blockNumber"], "latest"):
                        try:
                            self.w3.eth.call(
                                {
                                    "to": self.contract.address,
                                    "from": self.account.address,
                                    "data": tx["data"],
                                    "gas": tx.get("gas", 500000),
                                },
                                block_identifier=block_id,
                            )
                            if block_id == "latest":
                                revert_reason = (
                                    "call succeeded at 'latest' — state changed "
                                    "(likely BatchIdAlreadyExists from prior mint)"
                                )
                            break
                        except Exception as call_exc:
                            msg = str(call_exc)
                            if "block not found" in msg or "-32001" in msg or "-32002" in msg:
                                continue
                            # Decode known custom error selectors
                            if OWNABLE_UNAUTHORIZED in msg:
                                try:
                                    # Extract address from ABI-encoded error payload
                                    hex_data = msg.split("0x")[-1].replace("'", "").strip()
                                    addr_hex = hex_data[-40:]  # last 20 bytes
                                    revert_reason = (
                                        f"OwnableUnauthorizedAccount: wallet 0x{addr_hex} "
                                        f"is not the contract owner. "
                                        f"Run: check who owns {self.contract_address} on BaseScan "
                                        f"and call transferOwnership({self.account.address}) from that account."
                                    )
                                except Exception:
                                    revert_reason = (
                                        "OwnableUnauthorizedAccount — your wallet is not the "
                                        "contract owner. Check PRIVATE_KEY_SEP in .env."
                                    )
                            else:
                                revert_reason = msg
                            break
                except Exception as outer_exc:
                    revert_reason = str(outer_exc)
                logger.error(
                    "Mint tx reverted  tx=%s  batch=%s  reason=%s",
                    tx_hash.hex(), batch_id, revert_reason,
                )
                return None
                
        except Exception as e:
            logger.exception("Failed to mint batch token  batch=%s", batch_id)
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
            
            # Pre-flight: check if container_id already exists on-chain.
            # mintContainer burns children THEN checks the container ID —
            # if it already exists the burn is irreversible but the mint fails.
            try:
                existing_container_token = self.contract.functions.getTokenIdByBatchId(
                    container_id
                ).call()
                if existing_container_token and existing_container_token != 0:
                    logger.info(
                        "Container %s already has token ID %s on-chain — "
                        "skipping mintContainer (already minted).",
                        container_id, existing_container_token,
                    )
                    return existing_container_token
            except Exception as pre_exc:
                # BatchIdNotFound is expected — container doesn't exist yet, proceed.
                logger.debug(
                    "Container %s pre-check: %s (expected — proceeding with mint)",
                    container_id, pre_exc,
                )

            # Ensure the contract is approved to burn our tokens before estimating gas.
            # We re-check here (not just at init) in case the approval TX from __init__
            # hasn't propagated to the node's simulation state yet.
            try:
                approved = self.contract.functions.isApprovedForAll(
                    self.account.address,
                    Web3.to_checksum_address(self.contract_address),
                ).call()
                logger.info(
                    "Approval check: isApprovedForAll(%s, %s) = %s",
                    self.account.address, self.contract_address, approved,
                )

                # Also verify each child token still has a balance — tokens
                # burned in a previous attempt will have balance=0 and will
                # cause ERC1155MissingApprovalForAll or InsufficientBalance.
                for tid, holder in zip(child_token_ids, checksum_holders):
                    try:
                        bal = self.contract.functions.balanceOf(holder, tid).call()
                        logger.info("  token %s  holder %s  balance=%s", tid, holder, bal)
                        if bal == 0:
                            logger.error(
                                "Token %s has balance=0 for holder %s — "
                                "it was burned in a previous (failed) mintContainer attempt. "
                                "The batch DB record still has token_id set but the token "
                                "no longer exists on-chain. "
                                "Cannot pack these batches into a container.",
                                tid, holder,
                            )
                            return None
                    except Exception as bal_exc:
                        logger.warning("Could not check balance for token %s: %s", tid, bal_exc)

                if not approved:
                    logger.info(
                        "Approval not yet active — sending setApprovalForAll before mintContainer"
                    )
                    import time as _time
                    nonce_ap = self.w3.eth.get_transaction_count(self.account.address, 'pending')
                    tx_ap = self.contract.functions.setApprovalForAll(
                        Web3.to_checksum_address(self.contract_address), True
                    ).build_transaction({
                        'chainId': self.w3.eth.chain_id,
                        'gas': 60000,
                        'gasPrice': int(self.w3.eth.gas_price * 1.2),
                        'nonce': nonce_ap,
                    })
                    signed_ap = self.w3.eth.account.sign_transaction(tx_ap, self.private_key)
                    tx_hash_ap = self.w3.eth.send_raw_transaction(signed_ap.raw_transaction)
                    receipt_ap = self.w3.eth.wait_for_transaction_receipt(tx_hash_ap, timeout=60)
                    if receipt_ap['status'] == 1:
                        logger.info("setApprovalForAll confirmed (pre-mint)  tx=%s", tx_hash_ap.hex())
                        # Give the node 1 second to index the new state before estimate_gas
                        _time.sleep(1)
                    else:
                        logger.warning("setApprovalForAll reverted (pre-mint)  tx=%s", tx_hash_ap.hex())
            except Exception as ap_exc:
                logger.warning("Pre-mint approval check failed: %s", ap_exc)

            # Build transaction — estimate gas dynamically (container minting
            # burns N child tokens + stores metadata, so gas scales with inputs)
            nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            gas_price = self.w3.eth.gas_price

            mint_fn = self.contract.functions.mintContainer(
                Web3.to_checksum_address(recipient),
                quantity_grams,
                container_id,
                metadata_json,
                ipfs_cid,
                child_token_ids,
                checksum_holders
            )

            try:
                estimated_gas = mint_fn.estimate_gas({'from': self.account.address})
                gas_limit = int(estimated_gas * 1.3)
                logger.debug(
                    "Gas estimate for mintContainer: %d  limit: %d  children: %d",
                    estimated_gas, gas_limit, len(child_token_ids),
                )
            except Exception as est_exc:
                logger.error(
                    "Gas estimation failed for mintContainer  id=%s  children=%s  error=%s  "
                    "(tx would revert — not sending)",
                    container_id, child_token_ids, est_exc,
                )
                return None

            tx = mint_fn.build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': gas_limit,
                'gasPrice': int(gas_price * 1.2),
                'nonce': nonce,
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info("Container mint tx sent: %s - burning %d child tokens %s", 
                        tx_hash.hex(), len(child_token_ids), child_token_ids)
            
            # Wait for receipt (60 second timeout for more complex tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                logger.info("Container token minted  id=%s  qty=%skg  children=%d  tx=%s",
                            container_id, quantity_kg, len(child_token_ids), tx_hash.hex())
                
                # Query the container token ID by container_id (with retry)
                import time
                for attempt in range(3):
                    try:
                        token_id = self.contract.functions.getTokenIdByBatchId(container_id).call()
                        logger.info("Container Token ID: %s", token_id)
                        
                        # Verify it's actually a container
                        is_container = self.contract.functions.isContainer(token_id).call()
                        if is_container:
                            logger.debug("Verified as container token")
                        
                        return token_id
                    except Exception as e:
                        if attempt < 2:
                            logger.debug("Retrying token ID query (attempt %d/3)", attempt + 2)
                            time.sleep(2)
                        else:
                            logger.warning("Could not query container token ID after 3 attempts: %s  tx=%s",
                                           e, tx_hash.hex())
                            return None
            else:
                revert_reason = "unknown"
                try:
                    for block_id in (receipt["blockNumber"], "latest"):
                        try:
                            self.w3.eth.call(
                                {
                                    "to": self.contract.address,
                                    "from": self.account.address,
                                    "data": tx["data"],
                                    "gas": tx.get("gas", gas_limit),
                                },
                                block_identifier=block_id,
                            )
                            if block_id == "latest":
                                revert_reason = (
                                    "call succeeded at 'latest' — state changed "
                                    "(child tokens may already be burned)"
                                )
                            break
                        except Exception as call_exc:
                            msg = str(call_exc)
                            if "block not found" in msg or "-32001" in msg or "-32002" in msg:
                                continue
                            if "118cdaa7" in msg:
                                revert_reason = (
                                    "OwnableUnauthorizedAccount — wallet is not the contract owner"
                                )
                            else:
                                revert_reason = msg
                            break
                except Exception as outer_exc:
                    revert_reason = str(outer_exc)
                logger.error(
                    "Container mint tx reverted  tx=%s  id=%s  children=%s  reason=%s",
                    tx_hash.hex(), container_id, child_token_ids, revert_reason,
                )
                return None
                
        except Exception as e:
            logger.exception("Failed to mint container token  id=%s", container_id)
            return None
    
    def remint_batch_recovery(
        self,
        recipient: str,
        quantity_kg: float,
        original_batch_id: str,
        metadata: Dict[str, Any],
        ipfs_cid: str,
    ) -> Optional[int]:
        """
        Re-mint a batch token using a recovery suffix when the original token
        was burned in a failed mintContainer attempt.

        The contract prevents reusing the same batch_id (BatchIdAlreadyExists),
        so recovery mints use a suffixed ID: "{batch_id}_R1", "_R2", etc.
        The DB is updated to store the recovery token ID.

        Returns: new token_id, or None if failed.
        """
        for attempt in range(1, 4):  # try _R1, _R2, _R3
            recovery_id = f"{original_batch_id}_R{attempt}"
            try:
                # Check if this recovery ID is already taken
                existing = self.contract.functions.getTokenIdByBatchId(recovery_id).call()
                if existing and existing != 0:
                    logger.info("Recovery ID %s already used (token %s), trying next", recovery_id, existing)
                    continue
            except Exception:
                pass  # BatchIdNotFound — this ID is free, use it

            token_id = self.mint_batch(
                recipient=recipient,
                quantity_kg=quantity_kg,
                batch_id=recovery_id,
                metadata={**metadata, "recovery_of": original_batch_id, "recovery_attempt": attempt},
                ipfs_cid=ipfs_cid,
            )
            if token_id:
                logger.info(
                    "Recovery mint successful: %s → token %s (recovery_id=%s)",
                    original_batch_id, token_id, recovery_id,
                )
                return token_id
            logger.warning("Recovery mint failed for %s, trying next suffix", recovery_id)

        logger.error("All recovery mint attempts failed for %s", original_batch_id)
        return None
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
                'created_at': metadata[4],
                'exists': metadata[5],
                'is_aggregated': metadata[6],
                'child_token_ids': list(metadata[7])
            }
            
        except Exception as e:
            logger.exception("Failed to query batch metadata  token_id=%s", token_id)
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
            logger.exception("Failed to query balance  owner=%s  token_id=%s", owner, token_id)
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
