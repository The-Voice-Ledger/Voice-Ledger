#!/bin/bash
# Voice Ledger - Smart Contract Deployment Script
# Updated for Etherscan V2 API (December 2025)
# Network: Base Sepolia Testnet (Chain ID: 84532)

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Voice Ledger Contract Deployment${NC}"
echo -e "${GREEN}Etherscan V2 API (Unified Multi-chain)${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create a .env file with required variables"
    exit 1
fi

# Load environment variables
source ../.env

# Verify required variables
if [ -z "$BASE_SEPOLIA_RPC_URL" ]; then
    echo -e "${RED}❌ Error: BASE_SEPOLIA_RPC_URL not set${NC}"
    exit 1
fi

if [ -z "$PRIVATE_KEY_SEP" ]; then
    echo -e "${RED}❌ Error: PRIVATE_KEY_SEP not set${NC}"
    exit 1
fi

if [ -z "$ETHERSCAN_API_KEY" ]; then
    echo -e "${RED}❌ Error: ETHERSCAN_API_KEY (V2) not set${NC}"
    echo "Please obtain a V2 API key from https://etherscan.io/myapikey"
    exit 1
fi

echo -e "${YELLOW}Network:${NC} Base Sepolia (Chain ID: 84532)"
echo -e "${YELLOW}RPC URL:${NC} $BASE_SEPOLIA_RPC_URL"
echo -e "${YELLOW}Verification:${NC} Etherscan V2 API"
echo ""

# Confirm deployment
read -p "Deploy and verify contracts? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo -e "${GREEN}🚀 Deploying contracts...${NC}"
echo ""

# Deploy with Etherscan V2 API verification
# Key changes from V1:
# - verifier-url: https://api.etherscan.io/v2/api (unified endpoint)
# - Must include chainid=84532 for Base Sepolia
# - Single API key works across all chains
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
    --rpc-url $BASE_SEPOLIA_RPC_URL \
    --private-key $PRIVATE_KEY_SEP \
    --broadcast \
    --verify \
    --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --via-ir

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Copy the deployed contract addresses from above"
echo "2. Update .env file with the new addresses:"
echo "   - EPCIS_EVENT_ANCHOR_ADDRESS=0x..."
echo "   - COFFEE_BATCH_TOKEN_ADDRESS=0x..."
echo "   - SETTLEMENT_CONTRACT_ADDRESS=0x..."
echo ""
echo "3. Verify contracts on Base Sepolia Etherscan:"
echo "   https://sepolia.basescan.org/address/<CONTRACT_ADDRESS>"
echo ""
echo -e "${GREEN}🎉 Contracts deployed and verified with Etherscan V2 API!${NC}"
