# Chainlink CRE Integration — Voice Ledger Oracle

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.9+ | Provenance API |
| Bun | latest | CRE TypeScript workflow |
| Chainlink CRE CLI | latest | Workflow simulation & deployment |
| Foundry | latest | Smart contract compilation & deployment |

### 1. Start the Provenance API

```bash
# From project root
cd /path/to/Voice-Ledger

# Install API dependencies (if not already installed)
pip install fastapi uvicorn

# Start the API server
uvicorn chainlink.api.provenance_api:app --host 0.0.0.0 --port 8100
```

Verify:
```bash
curl http://localhost:8100/health
curl http://localhost:8100/api/provenance
```

### 2. Install CRE Workflow Dependencies

```bash
cd chainlink/workflow
bun install
```

### 3. Simulate Each Trigger

```bash
# Trigger 1 — Proof of Provenance (Cron)
cre workflow simulate \
  --workflow-file main.ts \
  --config-file config.json \
  --trigger-index 0

# Trigger 2 — Event Watcher (LogTrigger)
cre workflow simulate \
  --workflow-file main.ts \
  --config-file config.json \
  --trigger-index 1

# Trigger 3 — Deforestation Oracle (HTTP)
cre workflow simulate \
  --workflow-file main.ts \
  --config-file config.json \
  --trigger-index 2 \
  --http-payload @../test/deforestation_request.json
```

### 4. Compile & Deploy the Receiver Contract

The `ProvenanceDataReceiver.sol` contract lives in the main Foundry suite at `blockchain/src/` alongside all other Voice Ledger contracts.

```bash
# From project root — build all contracts with Foundry
cd blockchain && forge build

# Deploy to Base Sepolia
forge create src/ProvenanceDataReceiver.sol:ProvenanceDataReceiver \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --private-key $PRIVATE_KEY_SEP \
  --constructor-args $DEPLOYER_ADDRESS

# Or deploy all contracts at once via the deploy script
forge script script/DeployVoiceLedger.s.sol --rpc-url $BASE_SEPOLIA_RPC_URL --broadcast
```

After deployment, update `chainlink/workflow/config.json` with the deployed addresses:
- `provenanceReceiverAddress` → the new contract address
- `dataFeedsCacheAddress` → same address (or a separate DataFeedsCache if deployed)

### 5. Run API Tests

```bash
# Python tests
python -m pytest chainlink/test/test_provenance_api.py -v

# Shell smoke tests (requires API running on :8100)
bash chainlink/test/test_api.sh
```

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Provenance API │◄─────│  Chainlink DON   │─────►│  Base Sepolia    │
│  (Python/ASGI)  │      │  (CRE Workflow)  │      │  (Contracts)     │
│                 │      │                  │      │                  │
│  /api/provenance│      │  T1: Cron        │      │  DataFeedsCache  │
│  /api/batch/:id │      │  T2: LogTrigger  │      │  ProvenanceRecvr │
│  /api/deforest  │      │  T3: HTTP        │      │  EPCISAnchor ◄───│
└─────────────────┘      └──────────────────┘      └──────────────────┘
```

## File Structure

```
chainlink/
├── api/
│   ├── provenance_api.py     ← FastAPI (3 endpoints)
│   └── requirements.txt
├── workflow/
│   ├── main.ts               ← CRE workflow (3 triggers)
│   ├── config.json            ← Addresses, schedule, API URL
│   ├── package.json
│   └── tsconfig.json
├── test/
│   ├── test_provenance_api.py      ← pytest suite
│   ├── test_api.sh                 ← curl smoke tests
│   └── deforestation_request.json  ← HTTP trigger test fixture
└── README.md                       ← this file

blockchain/src/
└── ProvenanceDataReceiver.sol      ← DON report receiver (in Foundry suite)
```

## Configuration

Edit `chainlink/workflow/config.json`:

| Key | Description |
|-----|-------------|
| `schedule` | Cron expression for Trigger 1 (default: every 5 min) |
| `apiBaseUrl` | Where the Provenance API is running |
| `provenanceDataIdHex` | Hex ID for the provenance data feed |
| `evms[0].epcisEventAnchorAddress` | Existing EPCISEventAnchor contract |
| `evms[0].provenanceReceiverAddress` | Deployed ProvenanceDataReceiver |
| `evms[0].dataFeedsCacheAddress` | DataFeedsCache for provenance feed |
| `evms[0].gasLimit` | Gas limit for on-chain writes |

## Contract Addresses (Base Sepolia)

| Contract | Address |
|----------|---------|
| EPCISEventAnchor | `0xfda9e00d22eb166796449e919295e9755fd9a699` |
| CoffeeBatchToken | `0x2ff41d578a945036743d83972d4ab85f155a96fe` |
| SettlementContract | `0x739b34396259120177fba257019a005c3794b3da` |
| ProvenanceDataReceiver | _deploy and update config.json_ |
