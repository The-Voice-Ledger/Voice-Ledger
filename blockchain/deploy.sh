#!/bin/bash

# Voice Ledger Smart Contract Deployment Script
# Network: Base Sepolia Testnet
# Date: December 18, 2025

set -e  # Exit on any error

echo "=========================================="
echo "Voice Ledger Contract Deployment"
echo "=========================================="
echo ""

# Source environment variables
if [ -f ../.env ]; then
    source ../.env
    echo "✓ Environment variables loaded"
else
    echo "✗ Error: .env file not found"
    exit 1
fi

# Verify required environment variables
if [ -z "$BASE_SEPOLIA_RPC_URL" ]; then
    echo "✗ Error: BASE_SEPOLIA_RPC_URL not set"
    exit 1
fi

if [ -z "$PRIVATE_KEY_SEP" ]; then
    echo "✗ Error: PRIVATE_KEY_SEP not set"
    exit 1
fi

if [ -z "$BASESCAN_API_KEY" ]; then
    echo "✗ Error: BASESCAN_API_KEY not set"
    exit 1
fi

echo "✓ All required environment variables present"
echo ""

# Build contracts first
echo "Building contracts..."
forge build

if [ $? -ne 0 ]; then
    echo "✗ Build failed"
    exit 1
fi

echo "✓ Build successful"
echo ""

# Deploy and verify
echo "Deploying to Base Sepolia..."
echo "This will:"
echo "  1. Deploy EPCISEventAnchor"
echo "  2. Deploy CoffeeBatchToken"
echo "  3. Deploy SettlementContract"
echo "  4. Verify all contracts on BaseScan"
echo ""

forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --broadcast \
  --verify \
  --verifier etherscan \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY \
  -vvvv

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Deployment Successful!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Copy the contract addresses from the output above"
    echo "2. Add them to your .env file:"
    echo "   EPCIS_EVENT_ANCHOR_ADDRESS=0x..."
    echo "   COFFEE_BATCH_TOKEN_ADDRESS=0x..."
    echo "   SETTLEMENT_CONTRACT_ADDRESS=0x..."
    echo "3. Verify contracts on BaseScan:"
    echo "   https://sepolia.basescan.org/"
    echo ""
else
    echo ""
    echo "✗ Deployment failed"
    exit 1
fi
