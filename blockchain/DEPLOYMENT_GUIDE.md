# Voice Ledger Smart Contract Deployment Guide

## 📋 Overview

This guide covers deploying the Voice Ledger smart contracts to Base Sepolia testnet.

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
# Voice Ledger Smart Contracts (Base Sepolia)
EPCIS_EVENT_ANCHOR_ADDRESS=0x... # Copy from deployment output
COFFEE_BATCH_TOKEN_ADDRESS=0x... # Copy from deployment output
SETTLEMENT_CONTRACT_ADDRESS=0x... # Copy from deployment output
```

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

1. **`blockchain/client/blockchain_client.py`**
   - Update contract addresses
   - Update ABI paths

2. **`voice/service/batch_creation.py`**
   - Enable blockchain anchoring
   - Call `anchorEvent()` after batch creation

3. **`dpp/dpp_builder.py`**
   - Include blockchain transaction hashes in DPPs

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
- **Purpose**: Mint tokenized coffee batches
- **Key Function**: `mintBatch(address recipient, uint256 quantity, string batchId, string metadata)`
- **Standard**: OpenZeppelin ERC-1155

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

**Last Updated**: December 18, 2025  
**Network**: Base Sepolia (Chain ID: 84532)  
**Deployer**: Voice Ledger Development Team
