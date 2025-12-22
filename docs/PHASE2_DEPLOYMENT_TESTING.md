# Phase 2: Container Token Minting - Deployment & Testing Guide

**Status**: ✅ Implementation Complete  
**Date**: December 22, 2025  
**Etherscan API**: V2 (Unified Multi-chain)

---

## 🎯 Overview

Phase 2 adds blockchain container token minting to the `/pack` command, enabling full on-chain lineage tracking when batches are aggregated into containers.

### What's New

1. **Smart Contract**: `mintContainer()` function (already deployed v1.6)
2. **Python Wrapper**: `mint_container()` in `blockchain/token_manager.py`
3. **Integration**: `/pack` command now mints container tokens
4. **Database**: `container_token_id` field in `aggregation_relationships`

---

## ✅ Pre-Deployment Checklist

### 1. Smart Contract Tests (All Passing)

```bash
cd blockchain
forge test -vv
```

**Results**: ✅ 65/65 tests passing
- ✅ 7 aggregation tests (container minting, burning, lineage)
- ✅ 16 token tests (ERC-1155 functionality)
- ✅ 17 EPCIS anchor tests (event anchoring)
- ✅ 12 settlement tests
- ✅ 9 integration tests
- ✅ 4 deployment tests

### 2. Database Schema Updated

```bash
python scripts/add_container_token_id.py
```

**Result**: ✅ Column added with index

### 3. Code Changes

| File | Status | Description |
|------|--------|-------------|
| `blockchain/token_manager.py` | ✅ | Added `mint_container()` method (148 lines) |
| `blockchain/token_manager.py` | ✅ | Added `mint_container_token()` helper |
| `voice/command_integration.py` | ✅ | Integrated minting with `/pack` command |
| `database/models.py` | ✅ | Added `container_token_id` field |

---

## 🚀 Deployment (Etherscan V2 API)

### Step 1: Update Environment Variables

Add your Etherscan V2 API key to `.env`:

```bash
# Etherscan V2 API Key (unified multi-chain)
# Get yours at: https://etherscan.io/myapikey
ETHERSCAN_API_KEY=YOUR_V2_API_KEY_HERE
```

### Step 2: Verify Configuration

Check that you have:
- ✅ `BASE_SEPOLIA_RPC_URL` (Alchemy or other RPC)
- ✅ `PRIVATE_KEY_SEP` (deployer wallet private key)
- ✅ `ETHERSCAN_API_KEY` (V2 API key)
- ✅ Sufficient Base Sepolia ETH (get from [Coinbase Faucet](https://www.coinbase.com/faucets/base-ethereum-goerli-faucet))

### Step 3: Deploy Contracts

```bash
cd blockchain
./deploy_v2.sh
```

**What this does**:
1. Deploys `EPCISEventAnchor` contract
2. Deploys `CoffeeBatchToken` contract (with `mintContainer()`)
3. Deploys `SettlementContract` contract
4. Verifies all contracts on Etherscan (V2 API)

### Step 4: Update Contract Addresses

Copy the deployed addresses from the output and update `.env`:

```bash
EPCIS_EVENT_ANCHOR_ADDRESS=0x...
COFFEE_BATCH_TOKEN_ADDRESS=0x...
SETTLEMENT_CONTRACT_ADDRESS=0x...
```

### Step 5: Verify on Block Explorer

Visit Base Sepolia Etherscan:
```
https://sepolia.basescan.org/address/<COFFEE_BATCH_TOKEN_ADDRESS>
```

Check that `mintContainer()` function is visible in the contract ABI.

---

## 🧪 End-to-End Testing

### Test 1: Create Test Batches

```bash
# Create 3 test batches (via Telegram or API)
/commission 50kg Yirgacheffe Addis_Ababa
# Note batch ID: BATCH-001

/commission 60kg Sidamo Hawassa
# Note batch ID: BATCH-002

/commission 40kg Harrar Dire_Dawa
# Note batch ID: BATCH-003
```

### Test 2: Verify Batch Tokens

Check that each batch has a `token_id` in the database:

```python
from database import get_db
from database.crud import get_batch_by_batch_id

with get_db() as db:
    batch1 = get_batch_by_batch_id(db, "BATCH-001")
    batch2 = get_batch_by_batch_id(db, "BATCH-002")
    batch3 = get_batch_by_batch_id(db, "BATCH-003")
    
    print(f"Batch 1 Token ID: {batch1.token_id}")  # Should be integer
    print(f"Batch 2 Token ID: {batch2.token_id}")
    print(f"Batch 3 Token ID: {batch3.token_id}")
```

### Test 3: Pack into Container

```bash
# Pack batches into container
/pack BATCH-001 BATCH-002 BATCH-003 CONTAINER-2025-001
```

**Expected Output**:
```
✅ Packed 3 batches into container CONTAINER-2025-001 (Token ID: 4)

Event Hash: 0xabc123...
IPFS CID: QmXyz789...
Container Token ID: 4
```

### Test 4: Verify Container Token on Blockchain

```python
from blockchain.token_manager import get_token_manager

manager = get_token_manager()

# Get container metadata
container_token_id = 4
metadata = manager.get_batch_metadata(container_token_id)

print(f"Container ID: {metadata['batch_id']}")
print(f"Total Quantity: {metadata['quantity']} grams")
print(f"Is Container: {metadata['is_aggregated']}")
print(f"Child Tokens: {metadata['child_token_ids']}")
```

**Expected Output**:
```
Container ID: CONTAINER-2025-001
Total Quantity: 150000 grams  # 150 kg
Is Container: True
Child Tokens: [1, 2, 3]
```

### Test 5: Verify Child Tokens Burned

```python
# Check that original batch tokens are burned
batch1_balance = manager.get_batch_balance(holder_address, token_id=1)
batch2_balance = manager.get_batch_balance(holder_address, token_id=2)
batch3_balance = manager.get_batch_balance(holder_address, token_id=3)

print(f"Batch 1 Balance: {batch1_balance} (should be 0)")
print(f"Batch 2 Balance: {batch2_balance} (should be 0)")
print(f"Batch 3 Balance: {batch3_balance} (should be 0)")
```

### Test 6: Verify Database Record

```python
from database.models import AggregationRelationship

with get_db() as db:
    agg = db.query(AggregationRelationship).filter_by(
        parent_sscc="CONTAINER-2025-001"
    ).first()
    
    print(f"Container Token ID: {agg.container_token_id}")  # Should be 4
    print(f"Aggregated At: {agg.aggregated_at}")
    print(f"Is Active: {agg.is_active}")
```

### Test 7: Verify DPP Generation

```bash
# Generate DPP for container
curl http://localhost:8082/dpp/container/CONTAINER-2025-001
```

**Should return**:
```json
{
  "containerId": "CONTAINER-2025-001",
  "tokenId": 4,
  "quantity": 150,
  "unit": "kg",
  "childBatches": [
    {"batchId": "BATCH-001", "tokenId": 1, "quantity": 50},
    {"batchId": "BATCH-002", "tokenId": 2, "quantity": 60},
    {"batchId": "BATCH-003", "tokenId": 3, "quantity": 40}
  ],
  "blockchainProof": {
    "network": "Base Sepolia",
    "contractAddress": "0x...",
    "tokenId": 4,
    "isAggregated": true
  }
}
```

---

## 🔍 Troubleshooting

### Issue 1: Child Tokens Not Found

**Symptom**: `/pack` succeeds but no container token minted

**Causes**:
1. Batches don't have `token_id` (not minted during verification)
2. Batches created before token minting was implemented

**Solution**:
```python
# Check if batches have token IDs
from database.crud import get_batch_by_batch_id

with get_db() as db:
    for batch_id in ["BATCH-001", "BATCH-002", "BATCH-003"]:
        batch = get_batch_by_batch_id(db, batch_id)
        if not batch.token_id:
            print(f"❌ {batch_id} has no token_id - needs to be verified first")
```

### Issue 2: Wallet Address Not Found

**Symptom**: Warning "No wallet address for user, skipping blockchain minting"

**Cause**: User's `UserIdentity` record doesn't have `wallet_address` field

**Solution**:
```python
# Add wallet address to user
from database.models import UserIdentity

with get_db() as db:
    user = db.query(UserIdentity).filter_by(telegram_user_id=123456).first()
    user.wallet_address = "0xYourCooperativeWalletAddress"
    db.commit()
```

### Issue 3: Gas Estimation Failed

**Symptom**: Transaction fails with "gas estimation failed"

**Causes**:
1. Insufficient Base Sepolia ETH in wallet
2. Child tokens not owned by specified holders
3. One or more child tokens already burned

**Solution**:
```bash
# Check wallet balance
cast balance $COOPERATIVE_WALLET --rpc-url $BASE_SEPOLIA_RPC_URL

# Check token ownership
cast call $COFFEE_BATCH_TOKEN_ADDRESS \
  "balanceOf(address,uint256)" \
  $HOLDER_ADDRESS $TOKEN_ID \
  --rpc-url $BASE_SEPOLIA_RPC_URL
```

### Issue 4: Container Token ID Not Stored

**Symptom**: Container minted but `container_token_id` is NULL in database

**Cause**: Database transaction failed or not committed

**Solution**:
```python
# Manually update
from database.models import AggregationRelationship

with get_db() as db:
    agg = db.query(AggregationRelationship).filter_by(
        parent_sscc="CONTAINER-2025-001"
    ).first()
    agg.container_token_id = 4  # Token ID from blockchain
    db.commit()
```

---

## 📊 Deployment Command Comparison

### Old Command (Etherscan V1 - DEPRECATED)

```bash
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --broadcast \
  --verify \
  --verifier etherscan \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY \
  --via-ir
```

### New Command (Etherscan V2 - CURRENT)

```bash
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --broadcast \
  --verify \
  --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --via-ir
```

**Key Changes**:
- ✅ Unified endpoint: `https://api.etherscan.io/v2/api`
- ✅ Chain ID parameter: `?chainid=84532` (Base Sepolia)
- ✅ Single API key: Works across all 60+ chains
- ❌ Removed: `--verifier etherscan` (handled by URL)
- ❌ Removed: Chain-specific URLs (basescan.org)

---

## 📈 Success Metrics

After deployment, verify:

- ✅ All 65 smart contract tests passing
- ✅ Contracts verified on Base Sepolia Etherscan
- ✅ `/pack` command successfully mints container tokens
- ✅ Child tokens burned after aggregation
- ✅ Container tokens include lineage tracking
- ✅ Database stores `container_token_id`
- ✅ DPP includes blockchain proof

---

## 🚀 Next Steps (Phase 3)

With Phase 2 complete, the next priority is:

**Phase 3: PIN Setup Integration**
- Add PIN generation for cooperatives
- Secure wallet operations with PIN
- Phone/IVR authentication
- See `TODO_MARKETPLACE_COMPLETION.md` for details

---

## 📚 Related Documentation

- [Smart Contract README](blockchain/README.md)
- [Deployment Guide](blockchain/DEPLOYMENT_GUIDE.md)
- [Aggregation Implementation](blockchain/AGGREGATION_MERKLE_PROOF_IMPLEMENTATION.md)
- [Etherscan V2 Migration](https://docs.etherscan.io/v2-migration)
- [Marketplace Roadmap](TODO_MARKETPLACE_COMPLETION.md)

---

**Last Updated**: December 22, 2025  
**Implementation**: Complete ✅  
**Testing**: Ready for end-to-end validation 🧪  
**Deployment**: Awaiting V2 API key and contract deployment 🚀
