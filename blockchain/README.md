# Voice Ledger Smart Contracts

**Version**: v1.6 - Post-Verification Token Minting  
**Last Deployment**: December 21, 2025  
**Network**: Base Sepolia (Chain ID 84532)  
**Status**: ✅ Production-ready (testnet)

---

## Overview

Smart contracts for the Voice Ledger coffee traceability system, featuring:
- ✅ EPCIS event anchoring for immutable traceability
- ✅ ERC-1155 batch tokens minted AFTER cooperative verification
- ✅ Aggregation with lineage tracking (`mintContainer`, `burnBatch`)
- ✅ Custodial model (cooperative owns tokens, farmer tracked off-chain)

---

## Deployed Contracts (Base Sepolia)

### EPCISEventAnchor
**Address**: `0xf8b7c8a3692fa1d3bddf8079696cdb32e10241a7`  
**Purpose**: Anchor EPCIS event hashes on-chain for tamper-proof audit trail

**Key Functions**:
- `anchorEvent(bytes32 eventHash, string batchId, string eventType)` - Anchor event hash
- `anchorAggregation(...)` - Anchor aggregation with merkle root
- `getEvent(string batchId)` - Query event by batch ID

### CoffeeBatchToken (ERC-1155)
**Address**: `0xf2d21673c16086c22b432518b4e41d52188582f2`  
**Purpose**: Tokenize verified coffee batches as ERC-1155 tokens

**Key Functions**:
- `mintBatch(...)` - Mint individual batch (called after verification)
- `mintContainer(...)` - Aggregate multiple batches, burn children
- `burnBatch(uint256 tokenId, uint256 amount)` - Burn at consumption
- `getTokenIdByBatchId(string)` - Query token ID by batch string
- `getChildTokenIds(uint256)` - Get lineage for containers
- `getBatchMetadata(uint256)` - Query on-chain batch data

**Features (v1.6)**:
- ✅ Post-verification minting (integrated with `verification_handler.py`)
- ✅ Tokens minted with verified quantity (not farmer's claim)
- ✅ Aggregation lineage tracking with `childTokenIds[]`
- ✅ IPFS CID per token for recursive DPP generation

### SettlementContract
**Address**: `0x16e6db0f637ec7d83066227d5cbfabd1dcb5623b`  
**Purpose**: Record settlement information for payment rails

**Key Functions**:
- `settleCommissioning(uint256 batchId, address recipient, uint256 amount)`

---

## Development with Foundry

Foundry is a blazing fast, portable and modular toolkit for Ethereum application development written in Rust.

Foundry consists of:

- **Forge**: Ethereum testing framework (like Truffle, Hardhat and DappTools).
- **Cast**: Swiss army knife for interacting with EVM smart contracts, sending transactions and getting chain data.
- **Anvil**: Local Ethereum node, akin to Ganache, Hardhat Network.
- **Chisel**: Fast, utilitarian, and verbose solidity REPL.

### Documentation

https://book.getfoundry.sh/

### Build

```shell
forge build
```

### Test

```shell
forge test -vv
```

**Current Status**: 65/65 tests passing ✅

### Deploy

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

```shell
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --broadcast \
  --verify \
  --via-ir
```

### Gas Snapshots

```shell
forge snapshot
```

---

## Integration

### Token Minting Flow

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

### Python Integration

**Token Manager** (`blockchain/token_manager.py`):
```python
from blockchain.token_manager import mint_batch_token

token_id = mint_batch_token(
    recipient=os.getenv('COOPERATIVE_WALLET_ADDRESS'),
    quantity_kg=145.0,  # Verified quantity
    batch_id="TEST_YEHA_20251221_115841",
    metadata={'origin': 'Yirgacheffe', 'quality': 85},
    ipfs_cid="QmbPaGGqrp2jLBEH841XPDzNsiAmbdvB9Xu9z81bbLfeTp"
)
```

**Verification Handler** (`voice/telegram/verification_handler.py`):
- Token minting integrated into `_process_verification()` (lines 390-450)
- Mints AFTER cooperative scans QR and approves
- Uses `verified_quantity` (not farmer's claimed quantity)
- Stores `token_id` in `CoffeeBatch` database record

### Testing

**Unit Tests** (Foundry):
```bash
forge test -vv
```

**Integration Test** (Python):
```bash
cd /Users/manu/Voice-Ledger
source venv/bin/activate
source .env
python test_token_minting_flow.py
```

Expected: 6/6 steps passing ✅

---

## Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment instructions and post-deployment verification
- [AGGREGATION_MERKLE_PROOF_IMPLEMENTATION.md](AGGREGATION_MERKLE_PROOF_IMPLEMENTATION.md) - Aggregation with merkle proofs
- [SMART_CONTRACT_READINESS_ASSESSMENT.md](SMART_CONTRACT_READINESS_ASSESSMENT.md) - Feature assessment
- [Lab 13: Post-Verification Token Minting](../documentation/labs/LABS_13_Post_Verification_Token_Minting.md) - Complete implementation guide

---

## Deployment History

### v1.6 - December 21, 2025
- **Features**: Post-verification token minting, aggregation functions
- **Gas Used**: 4,641,311
- **Cost**: 0.000006502 ETH
- **Tests**: 65/65 passing (Foundry) + integration test
- **Changes**:
  - Added `getTokenIdByBatchId()` function
  - Enhanced `BatchMetadata` with aggregation fields
  - Token minting moved to verification handler
  - Database integration with `token_id` column

### v1.5 - December 18, 2025
- **Features**: Aggregation with Merkle proofs
- **Note**: Missing `getTokenIdByBatchId()` (required redeployment)

---

**Last Updated**: December 21, 2025  
**Maintainers**: Voice Ledger Development Team
