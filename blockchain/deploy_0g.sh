#!/usr/bin/env bash
# Deploy Voice Ledger contracts to 0G Galileo Testnet
# Usage: cd blockchain && bash deploy_0g.sh
#
# Prerequisites:
#   - 0G testnet tokens in wallet (faucet: https://faucet.0g.ai/)
#   - OG_GALLILEO_TESTNET_RPC_URL set in ../.env
#   - PRIVATE_KEY_SEP set in ../.env (reused as deployer key)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load env
source ../.env 2>/dev/null || true

RPC_URL="${OG_GALLILEO_TESTNET_RPC_URL:-}"
PRIVATE_KEY="${ZG_PRIVATE_KEY:-${PRIVATE_KEY_SEP:-}}"
VERIFIER_URL="https://chainscan-galileo.0g.ai/open/api"
CHAINSCAN_API_KEY="${ZG_CHAINSCAN_API_KEY:-placeholder}"

if [ -z "$RPC_URL" ]; then
    echo -e "${RED}Error: OG_GALLILEO_TESTNET_RPC_URL not set${NC}"
    exit 1
fi
if [ -z "$PRIVATE_KEY" ]; then
    echo -e "${RED}Error: ZG_PRIVATE_KEY / PRIVATE_KEY_SEP not set${NC}"
    exit 1
fi

echo -e "${YELLOW}=== 0G Galileo Testnet Deployment ===${NC}"
echo -e "${YELLOW}RPC:${NC} $RPC_URL"
echo -e "${YELLOW}Chain ID:${NC} 16602"
echo -e "${YELLOW}Verification:${NC} $VERIFIER_URL"
echo ""

# Step 1: Deploy core contracts (EPCISEventAnchor, CoffeeBatchToken, Settlement, ProvenanceReceiver)
echo -e "${GREEN}[1/2] Deploying core contracts...${NC}"
forge script script/DeployVoiceLedger.s.sol:DeployVoiceLedger \
    --rpc-url "$RPC_URL" \
    --private-key "$PRIVATE_KEY" \
    --broadcast \
    --verify \
    --verifier-url "$VERIFIER_URL" \
    --etherscan-api-key "$CHAINSCAN_API_KEY" \
    --chain-id 16602 \
    --via-ir

echo ""

# Step 2: Deploy DeFi pool contracts (FinancingPool, FeeDistributor, TradeEscrow)
echo -e "${GREEN}[2/2] Deploying DeFi pool contracts...${NC}"
USDC_ADDRESS="${USDC_ADDRESS:-}" \
COFFEE_BATCH_TOKEN_ADDRESS="${ZG_COFFEE_BATCH_TOKEN_ADDRESS:-$COFFEE_BATCH_TOKEN_ADDRESS}" \
EPCIS_EVENT_ANCHOR_ADDRESS="${ZG_EPCIS_ANCHOR_ADDRESS:-$EPCIS_EVENT_ANCHOR_ADDRESS}" \
PROVENANCE_RECEIVER_ADDRESS="${ZG_PROVENANCE_RECEIVER_ADDRESS:-$PROVENANCE_RECEIVER_ADDRESS}" \
SETTLEMENT_CONTRACT_ADDRESS="${ZG_SETTLEMENT_CONTRACT_ADDRESS:-$SETTLEMENT_CONTRACT_ADDRESS}" \
TREASURY_ADDRESS="${TREASURY_ADDRESS:-}" \
RESERVE_FUND_ADDRESS="${RESERVE_FUND_ADDRESS:-}" \
forge script script/DeployDeFiPool.s.sol:DeployDeFiPool \
    --rpc-url "$RPC_URL" \
    --private-key "$PRIVATE_KEY" \
    --broadcast \
    --verify \
    --verifier-url "$VERIFIER_URL" \
    --etherscan-api-key "$CHAINSCAN_API_KEY" \
    --chain-id 16602 \
    --via-ir

echo ""
echo -e "${GREEN}=== Deployment + Verification Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Copy the deployed addresses from above into .env as ZG_* variables"
echo "  2. Set BLOCKCHAIN_NETWORK=0g in .env to switch the Python backend"
echo ""
echo -e "${YELLOW}Manual re-verification (if auto-verify failed):${NC}"
echo "  forge verify-contract <ADDRESS> src/EPCISEventAnchor.sol:EPCISEventAnchor \\"
echo "    --verifier-url $VERIFIER_URL --etherscan-api-key $CHAINSCAN_API_KEY --chain-id 16602 --via-ir"
