# Voice Ledger Smart Contract Deployment Guide

**Last Updated**: December 21, 2025  
**Latest Deployment**: v1.6 with Post-Verification Token Minting  
**Network**: Base Sepolia (Chain ID: 84532)

## 📋 Overview

This guide covers deploying the Voice Ledger smart contracts to Base Sepolia testnet with the latest v1.6 features including:
- ✅ Post-verification token minting (tokens only created after cooperative approval)
- ✅ Aggregation features (`mintContainer`, `burnBatch`, lineage tracking)
- ✅ `getTokenIdByBatchId()` for querying tokens by string batch ID
- ✅ IR optimizer enabled for gas efficiency

## 🔧 Prerequisites

- Foundry installed (`forge --version`)
- `.env` file configured with:
  - `BASE_SEPOLIA_RPC_URL`
  - `PRIVATE_KEY_SEP`
  - `BASESCAN_API_KEY`

## 📦 Contracts to Deploy

1. **EPCISEventAnchor** - Anchors EPCIS event hashes on-chain for immutable traceability
2. **CoffeeBatchToken** - ERC-1155 tokens representing coffee batches
3. **SettlementContract** - Handles automatic settlement after batch creation

## 🚀 Deployment Commands

### Test Compilation
```bash
cd blockchain
forge build
```

### Deploy to Base Sepolia (with verification)
```bash
source ../.env

forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --broadcast \
  --verify \
  --verifier etherscan \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY \
  -vvvv
```

### Deploy to Local Anvil (for testing)
```bash
# Terminal 1: Start Anvil
anvil

# Terminal 2: Deploy
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url http://127.0.0.1:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast \
  -vvvv
```

## 📝 Post-Deployment

After deployment, add the contract addresses to your `.env` file:

```bash
# Deployed Contract Addresses (Base Sepolia - December 21, 2025 - v1.6 with Aggregation)
EPCIS_EVENT_ANCHOR_ADDRESS=0xf8b7c8a3692fa1d3bddf8079696cdb32e10241a7
COFFEE_BATCH_TOKEN_ADDRESS=0xf2d21673c16086c22b432518b4e41d52188582f2
SETTLEMENT_CONTRACT_ADDRESS=0x16e6db0f637ec7d83066227d5cbfabd1dcb5623b
```

**Current Deployment Details**:
- ✅ Deployed: December 21, 2025 at 11:27 AM
- ✅ Gas Used: 4,641,311 total
- ✅ Cost: 0.000006502 ETH
- ✅ All 65 Foundry tests passing
- ✅ Integration test verified end-to-end flow
- ⏳ Basescan verification pending (API rate limited)

## 🔍 Verify Deployment

### Check on BaseScan
- Visit https://sepolia.basescan.org/
- Search for each contract address
- Verify the "Contract" tab shows verified source code

### Test Contracts
```bash
# Read EPCISEventAnchor role
cast call $EPCIS_EVENT_ANCHOR_ADDRESS "requiredRole()(string)" --rpc-url $BASE_SEPOLIA_RPC_URL

# Check CoffeeBatchToken URI
cast call $COFFEE_BATCH_TOKEN_ADDRESS "uri(uint256)(string)" 1 --rpc-url $BASE_SEPOLIA_RPC_URL
```

## 🎯 Integration with Backend

After deployment, update these files:

### ✅ Already Integrated (v1.6):

1. **`blockchain/token_manager.py`** (NEW)
   - `CoffeeBatchTokenManager` class for Web3 interactions
   - `mint_batch()` - Mints token with verified quantity
   - `get_batch_metadata()` - Queries on-chain batch data
   - Uses `getTokenIdByBatchId()` for reliable token ID retrieval

2. **`voice/telegram/verification_handler.py`**
   - Token minting integrated into `_process_verification()`
   - Mints AFTER cooperative scans QR and approves
   - Uses `verified_quantity` (not farmer's claimed quantity)
   - Stores `token_id` in `CoffeeBatch` database record
   - Graceful error handling (verification succeeds even if minting fails)

3. **`voice/command_integration.py`**
   - Token minting REMOVED from commission handler
   - Comment explains tokens mint post-verification
   - Prevents unverified batches from getting on-chain representation

4. **`database/models.py`**
   - Added `token_id` column to `CoffeeBatch` table (BigInteger, nullable, indexed)
   - Links PostgreSQL batch record to ERC-1155 token

### Flow Architecture:

```
1. Farmer creates batch → PENDING_VERIFICATION
   - PostgreSQL record created
   - IPFS commission event pinned
   - Blockchain event hash anchored
   - ❌ NO TOKEN MINTED

2. QR code sent to farmer

3. Cooperative scans QR, verifies actual quantity

4. Cooperative approves verification
   - Status → VERIFIED
   - Verification credential issued
   - Verification EPCIS event created
   - ✅ TOKEN MINTED (using verified quantity!)
   - Token ID stored in batch.token_id

5. On-chain token represents verified batch only
```

### Testing:

Run the integration test to verify the complete flow:
```bash
cd /Users/manu/Voice-Ledger
source venv/bin/activate
source .env
python test_token_minting_flow.py
```

Expected output:
- ✅ Step 1: Batch created (PENDING_VERIFICATION, no token)
- ✅ Step 2: Commission event → IPFS + blockchain
- ✅ Step 3: Confirmed no token before verification
- ✅ Step 4: Cooperative verifies (145kg verified vs 150kg claimed)
- ✅ Step 5: Token minted with verified quantity
- ✅ Step 6: All database fields updated correctly

## 🔐 Security Notes

- ✅ Keep `PRIVATE_KEY_SEP` secure (never commit to git)
- ✅ Use separate wallet for testnet vs mainnet
- ✅ Verify contract source code on BaseScan
- ✅ Test thoroughly on Base Sepolia before any mainnet deployment

## 📚 Contract Details

### EPCISEventAnchor
- **Purpose**: Store EPCIS event hashes on-chain
- **Key Function**: `anchorEvent(bytes32 eventHash, string batchId, string eventType)`
- **Events**: `EventAnchored(bytes32 eventHash, string batchId, string eventType, uint256 timestamp, address submitter)`

### CoffeeBatchToken (ERC-1155)
- **Purpose**: Mint tokenized coffee batches AFTER cooperative verification
- **Key Functions**: 
  - `mintBatch(address recipient, uint256 quantity, string batchId, string metadata, string ipfsCid)` - Mints individual batch
  - `mintContainer(...)` - Aggregates multiple batches, burns children
  - `burnBatch(uint256 tokenId, uint256 amount)` - Burns tokens at consumption
  - `getTokenIdByBatchId(string batchId)` - Query token ID by batch string
  - `getChildTokenIds(uint256 tokenId)` - Get lineage for aggregated containers
- **Standard**: OpenZeppelin ERC-1155 with custom aggregation logic
- **New Features (v1.6)**:
  - ✅ Post-verification minting (integrated with verification_handler.py)
  - ✅ Token minted with verified quantity, not farmer's claim
  - ✅ Custodial model: Cooperative wallet owns tokens
  - ✅ Aggregation lineage tracking with `childTokenIds[]`

### SettlementContract
- **Purpose**: Record settlement information
- **Key Function**: `settleCommissioning(uint256 batchId, address recipient, uint256 amount)`
- **Integration**: Future payment rail integration

## 🐛 Troubleshooting

### "Deployment failed: insufficient funds"
- Check wallet balance: `cast balance $PRIVATE_KEY_SEP --rpc-url $BASE_SEPOLIA_RPC_URL`
- Get Base Sepolia ETH from faucet: https://www.coinbase.com/faucets/base-ethereum-goerli-faucet

### "Verification failed"
- Retry verification: `forge verify-contract <address> <contract_name> --chain-id 84532 --etherscan-api-key $BASESCAN_API_KEY`
- Check BaseScan API status

### "RPC error"
- Verify `BASE_SEPOLIA_RPC_URL` is correct
- Check Alchemy dashboard for rate limits

---

## 📊 Deployment History

### v1.6 - December 21, 2025
- **Features**: Post-verification token minting, aggregation functions
- **Gas Used**: 4,641,311
- **Cost**: 0.000006502 ETH
- **Addresses**:
  - EPCISEventAnchor: `0xf8b7c8a3692fa1d3bddf8079696cdb32e10241a7`
  - CoffeeBatchToken: `0xf2d21673c16086c22b432518b4e41d52188582f2`
  - SettlementContract: `0x16e6db0f637ec7d83066227d5cbfabd1dcb5623b`
- **Tests**: 65/65 passing (Foundry) + integration test
- **Integration**: `token_manager.py`, `verification_handler.py` updated

### v1.5 - December 18, 2025
- **Features**: Aggregation with Merkle proofs
- **Note**: Missing `getTokenIdByBatchId()` function (required redeployment)

---

**Last Updated**: December 21, 2025  
**Network**: Base Sepolia (Chain ID: 84532)  
**Current Version**: v1.6 with Post-Verification Minting  
**Deployer**: Voice Ledger Development Team
