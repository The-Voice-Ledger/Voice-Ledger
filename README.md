# Voice Ledger

**A Voice-first blockchain traceability System for coffee supply chains.** Farmers speak, the system records everything from harvest to export, anchored on-chain with IPFS storage. Built for smallholder farmers who shouldn't need a smartphone to prove their coffee's provenance.

**Current:** v2.2 (Production) — 37-tool AI agent, DeFi trade finance, LSP & customs integration  
**Status:** Deployed on Railway + Base Sepolia · 7 verified smart contracts · Telegram bot live

---

## What It Does

The Voice Ledger converts spoken supply chain events into verifiable blockchain records. Farmers send voice messages via Telegram in Amharic or English. An **AI agent powered by GPT-4o tool-calling** transcribes speech, reasons about intent, and autonomously selects from 37 tools across 10 domains — recording batches, managing marketplace offers, arranging DeFi financing, checking EUDR compliance, tracing provenance, and anchoring data on-chain. Full event data is stored on IPFS with cryptographic hashes anchored to Base Sepolia.

**The pitch:** A smallholder farmer in Yirgacheffe records "50 kilograms washed Arabica from Manufam farm" via voice. The AI agent selects the right tool, validates the data, creates a tokenized batch (ERC-1155) with blockchain-verified provenance, GPS coordinates proving deforestation-free origin, and a QR code that any buyer or customs broker can scan for full supply chain history — including EUDR Article 9 compliance data ready for EU import filing. All accessible through Telegram Mini Apps with voice-first interaction.

---

## Core Components

### Voice Interface
- **Telegram Bot** (@voice_ledger_bot): Primary interface for farmers
- **Telegram Mini Apps**: 5 voice-first web apps (Batch Browser, Marketplace, Trace, Profile, Admin)
  - SVG-based UI (no emoji dependencies)
  - Voice recording buttons on every screen
  - Shared voice.js library with context-aware processing
  - Haptic feedback and responsive design
- **Bilingual ASR**: Automatic English/Amharic routing
  - English: OpenAI Whisper API ($0.006/minute)
  - Amharic: Local fine-tuned model ($0, 9% WER)
- **Dual Delivery**: Every response sent as text + TTS voice note
- **Latency**: 5-15 seconds end-to-end (async Celery pipeline)
- **IVR Ready**: Twilio integration for feature phones (planned)

### Agentic AI (37 Tools, 10 Domains)
- **GPT-4o Tool-Calling Agent**: Replaces rigid NLU intent classification with autonomous reasoning
- **37 Tools across 10 Domains**:
  - **Supply Chain** (7): record commission/shipment/receipt/transformation, pack/unpack/split batches
  - **Marketplace** (5): create RFQ, browse RFQs, submit/accept/list offers
  - **Container** (2): browse containers, purchase container fractions
  - **Pool** (3): browse pools, commit to pool, list commitments
  - **DPP** (4): get batch/container DPP, trace lineage, validate passport
  - **Compliance** (2): EUDR deforestation check, mass balance validation
  - **Verification** (2): list pending verifications, verify batch
  - **Blockchain** (3): check anchor, get token info, verify hash
  - **Chainlink DON** (3): request/check DON attestation, get provenance metrics
  - **Payment** (4): confirm payment, check status, record payout, confirm receipt
  - **Query** (2): search batches, search knowledge base
- **Multi-Turn Conversations**: Redis-backed history (10-min TTL)
- **Safety Rails**: Write-tool confirmation, bounded turn limits (max 6), 4-min timeout
- **RAG Fallback**: ChromaDB Cloud + GPT-4 for documentation queries (3,539 docs indexed)
- **Bilingual**: English (GPT-4o) + Amharic (AddisAI) with automatic routing

### Identity & Credentials (SSI)
- **Decentralized Identifiers**: W3C DID (did:key method, Ed25519)
- **Verifiable Credentials**: Organic certifications, quality grades, farm registrations
- **QR Code Export**: Farmers get portable credentials (offline-verifiable)
- **Public Verification API**: `/voice/verify/{did}` - no auth required

### Supply Chain Events (EPCIS 2.0)
- **Event Types**: Commission, Receipt, Shipment, Transformation, Aggregation
- **GS1 Standards**: GTIN-13, GLN, SSCC identifiers
- **JSON-LD Canonicalization**: URDNA2015 for deterministic hashing
- **Multi-Language Support**: Amharic and English transcripts → standardized EPCIS

### Blockchain & Smart Contracts
- **7 Contracts on Base Sepolia** (all deployed & verified):
  - `EPCISEventAnchor.sol`: Hash anchoring with IPFS CID storage
  - `CoffeeBatchToken.sol`: ERC-1155 semi-fungible tokens for batches & containers
  - `SettlementContract.sol`: Multi-currency tracking (USD, ETH, BIRR, USDC)
  - `ProvenanceDataReceiver.sol`: Chainlink CRE data receiver
  - `FinancingPool.sol`: ERC-4626 vault — LPs deposit USDC, cooperatives draw advances
  - `TradeEscrow.sol`: Holds USDC per trade, disburses on delivery confirmation
  - `FeeDistributor.sol`: Fee splitting (treasury 70% / reserve 20% / LP bonus 10%)
- **Solidity 0.8.20** + OpenZeppelin 5.0, compiled with Foundry (`--via-ir`)
- **IPFS Storage**: Full event data on Pinata (40% gas savings vs on-chain)
- **Merkle Proofs**: Batch aggregation (75% gas reduction)

### DeFi Trade Finance
Receivables factoring for coffee cooperatives — they draw USDC advances against confirmed buyer orders instead of waiting 60–90 days for payment:

1. **FinancingPool** (ERC-4626): Liquidity providers deposit USDC, earn yield from trade fees
2. **TradeEscrow**: Holds buyer payment, disburses to cooperative on delivery confirmation
3. **FeeDistributor**: Splits the spread between treasury, reserve fund, and LP bonus
4. Atomic pull model — pool calls `safeTransferFrom(escrow)` for trustless principal return

### Chainlink CRE Integration
- **Chainlink Runtime Environment**: Decentralized oracle computation for supply chain verification
- **Off-Chain Verification Workflows**: EPCIS event hash validation, batch integrity checks, and compliance scoring executed on Chainlink's Decentralized Oracle Network (DON)
- **ProvenanceDataReceiver**: On-chain contract receives DON-attested verification results
- **Bridge Architecture**: AI agent tool results feed into CRE workflows for trustless verification
- **Status**: Workflow definitions + simulation complete; DON deployment pending CRE mainnet

### EU Deforestation Regulation (EUDR) Compliance
- **GPS Photo Verification**: Extract geolocation from farmer photo EXIF
- **Deforestation Detection**: Global Forest Watch API + satellite imagery analysis
- **Risk Assessment**: Gold/Silver/Bronze levels (<0.5ha, 0.5-2ha, >2ha forest loss)
- **Audit Trail**: 5-year blockchain record (Article 33 compliance)
- **Cost**: $0.065/farmer/month (prevents $160K customs rejections)

### Multi-Actor Marketplace (Phase 3)
- **User Roles**: Farmer, Cooperative, Exporter, Buyer (4 actors + 1 admin)
- **RFQ System**: Buyers create voice-based requests, cooperatives submit offers
- **Telegram Mini Apps**: Full voice-first marketplace UI
  - RFQ browsing with voice search
  - Offer submission via voice
  - Real-time updates
- **PIN Authentication**: 4-digit PIN for web UI access (bcrypt, 5-attempt lockout)
- **Redis Session Persistence**: Session survival across server reloads
- **Registration Flow**: Multi-language, role-specific, with photo upload

### LSP & Customs Clearance Integration
API surface for logistics service providers and EU customs brokers:

- **Digital Product Passport API** (`/api/dpp/*`): Full/summary/QR DPP per batch or container
- **EUDR Article 9 API** (`/api/eudr/*`): Flat compliance export for customs filing; container-level weakest-link rollup
- **Webhook System** (`/api/webhooks/*`): Register URLs, subscribe to events (`PREPARING_SHIPMENT`, `SHIPPED`, `DELIVERED`, etc.), HMAC-SHA256 signed payloads, 3x exponential retry
- **LSP Milestone Ingestion** (`/api/logistics/*`): Accept tracking milestones (PICKUP → PORT_ARRIVAL → CUSTOMS_CLEARED → DELIVERED), auto-generate EPCIS events
- **Delivery State Machine**: `PENDING` → `PREPARING_SHIPMENT` → `SHIPPED` → `DELIVERED` with webhook dispatch on each transition

### Telegram Mini Apps Suite (v2.0)
Five voice-first web applications accessible via Telegram:

1. **Index/Home** (`miniapps/index.html`)
   - Dashboard with 4 main app cards + admin portal
   - User profile display with stats
   - Voice navigation ("Go to batches", "Open marketplace")

2. **Batch Browser** (`miniapps/batch_browser.html`)
   - View all user's coffee batches
   - Batch details with metadata (variety, quantity, grade, status)
   - Voice batch recording via conversation flow
   - QR code generation for batch verification

3. **Marketplace** (`miniapps/marketplace.html`)
   - Browse RFQs (Request for Quotations)
   - Submit offers via voice or form
   - Filter by status, variety, origin
   - Voice search: "Show open RFQs for Arabica"

4. **Trace/Traceability** (`miniapps/trace.html`)
   - Full supply chain timeline visualization
   - EPCIS event timeline with icons
   - Blockchain verification display
   - Location trail (map visualization planned)
   - Voice trace lookup: "Trace batch ABC123"

5. **Profile** (`miniapps/profile.html`)
   - User identity (DID, credentials)
   - Account information
   - Verifiable credentials display
   - Voice profile updates: "Change language to Amharic"

**Admin Dashboard** (`miniapps/admin.html`)
- User registration approval/rejection
- System analytics (pending registrations, total users, RFQs, offers)
- Tabbed interface (Registrations, Users, RFQs, Offers)
- Voice admin commands

**Technical Features:**
- Shared voice.js library (882 lines, Priority 1-5 features)
- Context-aware voice processing (sends app state to backend)
- Action execution (navigate, filter, search, submit)
- Workflow support (multi-turn batch recording)
- TTS playback controls (pause, resume, replay)
- Error handling with exponential backoff retry
- Audio validation (silence detection, duration checks)

---

## Tech Stack

**Backend**
- Python 3.9 + FastAPI (async API framework)
- PostgreSQL (Neon serverless) - database branching, auto-scaling
- Redis - Celery task queue + session storage
- SQLAlchemy 2.0 ORM with async support
- Celery - async voice processing pipeline

**Voice Processing & AI**
- OpenAI Whisper API (English ASR)
- `b1n1yam/shook-medium-amharic-2k` (local Amharic ASR, HuggingFace)
- OpenAI GPT-4o (agentic AI with 37-tool function-calling)
- AddisAI API (Amharic conversational AI)
- ChromaDB Cloud (vector database, 3,539 docs)
  - OpenAI text-embedding-3-small (1536 dimensions)
  - Hybrid search (vector similarity + metadata filtering)
- Celery + Redis (async agent execution pipeline)

**Frontend (Telegram Mini Apps)**
- Vanilla JavaScript (no frameworks)
- Telegram Web App SDK (tg.MainButton, BackButton, HapticFeedback)
- Shared voice.js module (882 lines, context-aware recording)
- SVG icons (no emoji/image dependencies)
- Responsive CSS with glassmorphism effects

**Blockchain**
- Solidity 0.8.20 + OpenZeppelin 5.0
- Foundry (Forge, Anvil, Cast)
- Web3.py 6.11.3
- Base Sepolia testnet (low fees, fast finality)

**Storage & Crypto**
- IPFS (Pinata pinning service)
- PyNaCl (Ed25519 signatures)
- PyLD (JSON-LD canonicalization URDNA2015)

**Messaging & Communication**
- python-telegram-bot (Telegram webhook + Mini Apps)
- Celery + Redis (async task processing)
- WebSocket support (planned for realtime voice)

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/The-Voice-Ledger/Voice-Ledger.git
cd Voice-Ledger
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add: OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, DATABASE_URL, REDIS_URL

# 3. Download Amharic model (one-time, ~1.5GB)
python3 -c "
from transformers import AutoModelForSpeechSeq2Seq
model = AutoModelForSpeechSeq2Seq.from_pretrained('b1n1yam/shook-medium-amharic-2k')
print('✅ Model cached at ~/.cache/huggingface/')
"

# 4. Start services
./admin_scripts/START_SERVICES.sh
# Starts: Redis, PostgreSQL, Celery worker, FastAPI, ngrok tunnel

# 5. Test via Telegram
# Message @voice_ledger_bot:
#   English: "New batch of 50kg Yirgacheffe from Manufam farm"
#   Amharic: "አዲስ ባች 50 ኪሎ ይርጋቸፍ ከማኑፋም እርሻ"
```

---

## Usage Examples

### Voice Commands (Telegram)

```bash
# Register
/register  # Start registration flow (multi-step, role-based)

# Record new harvest (via conversational AI)
"New batch of 50 kilograms Sidama variety from Gedeo farm"
"አዲስ ባች 50 ኪሎ ሲዳማ ከገዴኦ እርሻ"

# Ask questions (RAG-enhanced responses)
"How does batch verification work?"
"What is the marketplace for?"
"የባች ማረጋገጫ እንዴት ነው የሚሰራው?" (Amharic)

# Navigate Mini Apps via voice
"Go to marketplace"
"Open my batches"
"Show trace for batch ABC123"

# Record receipt
"Received batch ABC123 from farmer Abebe"

# Record shipment
"Shipped batch ABC123 to Addis warehouse"

# Record processing
"Roasted batch ABC123, output 850 kilograms"

# Aggregate batches (pack into container)
"Pack batches BATCH-001, BATCH-002 into container C100"

# View identity
/myidentity  # Shows DID, credentials, credit score

# Export credentials
/export  # Generates QR code with W3C Verifiable Presentation
```

### Telegram Mini Apps (Voice-First UI)

```bash
# Access via Telegram bot
1. Open @voice_ledger_bot
2. Tap Menu → Select app (Batches, Marketplace, Trace, Profile)
3. Use voice button (top-right blue button) on any screen

# Voice interactions in Mini Apps:
- "Create new batch" (in Batch Browser)
- "Show open RFQs" (in Marketplace)
- "Trace batch ABC123" (in Trace)
- "Change language to Amharic" (in Profile)
- "Approve pending registrations" (in Admin)
```

### Direct API (Voice Processing)

```bash
# Start API server
uvicorn voice.service.api:app --port 8000

# Submit audio file for transcription + intent extraction
curl -X POST http://localhost:8000/asr-nlu \
  -H "X-API-Key: $VOICE_API_KEY" \
  -F "file=@audio.wav"

# Response:
{
  "transcript": "New batch of 50 kilograms Yirgacheffe",
  "language": "en",
  "intent": "record_commission",
  "entities": {
    "quantity": 50,
    "unit": "kilograms",
    "variety": "Yirgacheffe"
  }
}

# Voice upload endpoint (Mini Apps)
curl -X POST http://localhost:8000/api/voice/upload \
  -H "X-Telegram-User-Id: 123456" \
  -F "file=@voice.webm" \
  -F "language=en" \
  -F 'context={"app":"marketplace","view":"rfqs"}'

# Response with conversational AI + action:
{
  "transcript": "Show me open RFQs for Arabica",
  "message": "Here are the current open RFQs for Arabica coffee...",
  "audio_url": "https://api.voice-ledger.com/tts/abc123.mp3",
  "action": {
    "type": "filter_rfqs",
    "params": {"filter": "open", "variety": "Arabica"}
  }
}
```

### RAG-Enhanced Conversational AI

```bash
# Test ChromaDB integration
curl http://localhost:8000/api/test-chromadb

# Response:
{
  "status": "connected",
  "collection": "voice_ledger_docs_v2",
  "document_count": 3539,
  "embedding_dimension": 1536
}

# Query knowledge base
curl -X POST http://localhost:8000/api/voice/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How does batch verification work?"}'

# Response with RAG-enhanced answer:
{
  "query_type": "DOCUMENTATION",
  "answer": "The verification process works like this: When you create a batch, the system generates a QR code with a Telegram deep link. The cooperative manager scans it, which opens the Telegram bot and authenticates them. They physically inspect your coffee, confirm the quantity, and click verify. This creates a W3C Verifiable Credential signed by the cooperative that proves your batch is authentic.",
  "sources_count": 5,
  "retrieval_time_ms": 234
}
```

### Public Verification API (No Auth)

```bash
# Verify credentials by DID
curl http://localhost:8000/voice/verify/did:key:z6Mk...

# Get W3C Verifiable Presentation
curl http://localhost:8000/voice/verify/did:key:z6Mk.../presentation

# Human-readable HTML
open http://localhost:8000/voice/verify/did:key:z6Mk.../html
```

### Smart Contract Interaction

```python
from blockchain.blockchain_anchor import BlockchainAnchor

anchor = BlockchainAnchor(
    rpc_url="https://sepolia.base.org",
    contract_address="0x...",
    private_key=os.getenv("PRIVATE_KEY")
)

# Anchor event to blockchain with IPFS CID
tx_hash = anchor.anchor_event_with_ipfs(
    event_hash="0x123...",
    ipfs_cid="QmTFwE14...",
    batch_id="BATCH-2025-001"
)
```

---

## Architecture

```
Voice Input (Telegram/IVR/Mini Apps)
    ↓
Language Detection → [Amharic Model] or [Whisper API]
    ↓
Transcript → AI Agent (GPT-4o, 37 tools)
    ↓
┌─── Agent Reasoning Loop (max 6 turns) ───┐
│  Reason → Select Tool → Execute → Observe │
│  ├─→ Supply Chain tools (7)               │
│  ├─→ Marketplace tools (5)                │
│  ├─→ Container / Pool tools (5)           │
│  ├─→ DPP / Compliance tools (6)           │
│  ├─→ Verification tools (2)               │
│  ├─→ Blockchain / Chainlink tools (6)     │
│  ├─→ Payment tools (4)                    │
│  └─→ Query / RAG tools (2)                │
└──────────────────────────────────────────┘
    ↓
Tool Execution Results
    ├─→ EPCIS Event Builder → IPFS + Blockchain Anchor
    ├─→ Database Updates (PostgreSQL)
    ├─→ Smart Contracts (Base Sepolia, 7 contracts)
    └─→ Webhook dispatch (LSP / customs broker)
    ↓
┌─────────────┴──────────────┐
↓                            ↓
IPFS Storage            Blockchain Anchor
(Full Event)            (Hash + CID + Timestamp)
    ↓                            ↓
QR Code ← Digital Product Passport (DPP)
    ↓
Dual Response (Text + TTS Voice Note)
```

**Data Flow:**
1. Farmer speaks (Amharic/English) via Telegram or Mini App
2. ASR transcribes based on user language preference
3. AI agent receives transcript + conversation history (Redis-backed)
4. Agent reasons about intent and selects from 37 tools (GPT-4o function-calling)
5. Tool executes: create EPCIS event, query data, check compliance, etc.
6. Agent may chain multiple tool calls in one turn (multi-step reasoning)
7. EPCIS event → JSON-LD canonicalization → SHA-256 hash
8. Full event → IPFS (get CID)
9. Hash + CID → Blockchain (immutable anchor)
10. Token minted (ERC-1155) + QR code generated
11. User receives text + TTS voice note (dual delivery)

**Agent Architecture (v2.1):**
```
User Voice/Text
    ↓
ASR → Transcript
    ↓
Agent Executor (GPT-4o)
    ├─→ Tool Registry (37 tools, 10 domains)
    │     ├─→ Supply Chain handlers
    │     ├─→ Marketplace handlers
    │     ├─→ Container / Pool handlers
    │     ├─→ Compliance handlers
    │     ├─→ DPP / Traceability handlers
    │     ├─→ Verification handlers
    │     ├─→ Blockchain / Chainlink handlers
    │     └─→ Payment handlers
    ├─→ RAG Fallback (ChromaDB, 3,539 docs)
    └─→ Redis History (multi-turn context)
    ↓
Natural language response → TTS → Dual Delivery
```

---

## Testing

```bash
# Run all tests
pytest

# Targeted test runs
pytest tests/test_lsp_customs_integration.py   # LSP & customs
pytest tests/test_eudr_compliance.py            # EUDR compliance
pytest tests/test_voice_api.py                  # Voice processing
pytest tests/test_rag_integration.py            # RAG system
pytest tests/test_anchor_flow.py                # Blockchain anchoring

# Solidity tests
cd blockchain && forge test
```

---

## Database Setup

**Using Neon Serverless PostgreSQL** (serverless, auto-scaling, database branching):

```bash
# Install dependencies
pip install sqlalchemy asyncpg psycopg2-binary alembic

# Set connection string (get from Neon dashboard)
export DATABASE_URL="postgresql://username:password@host.neon.tech/dbname"

# Create tables
python database/models.py

# Run migrations
python -m scripts.migrate_to_neon

# Verify connection
python -c "
from database.connection import get_session
with get_session() as db:
    print('✅ Database connected')
"
```

**Schema (23 tables):**
- `user_identities`: DIDs, keys, language preferences, PINs
- `organizations`: Cooperatives, exporters, buyer companies
- `farmer_identities`: Farm details, GPS coordinates, photos
- `coffee_batches`: GTIN, token IDs, quantities, origins
- `epcis_events`: Event hashes, IPFS CIDs, blockchain TXs
- `verifiable_credentials`: Certifications, quality grades
- `pending_registrations`: Multi-step registration state
- `rfqs` / `rfq_offers` / `rfq_acceptances`: Marketplace lifecycle
- `container_offerings`: Fractional container sale listings
- `container_pools` / `buyer_commitments`: Shared buying pools
- `aggregation_relationships`: Parent-child SSCC/batch links
- `verification_photos`: EUDR GPS photo evidence
- `exporters` / `buyers`: Role-specific organization details

---

## Project Structure

```
Voice-Ledger/
├── voice/                    # Voice processing pipeline
│   ├── agent/                # AI agent (GPT-4o tool-calling, 37 tools)
│   │   ├── executor.py       # Agent loop with bounded turns
│   │   ├── registry.py       # Tool registry (10 domains)
│   │   └── schemas.py        # OpenAI function definitions
│   ├── asr/                  # Automatic speech recognition
│   ├── nlu/                  # Natural language understanding (legacy)
│   ├── integrations/         # Conversational AI (English + Amharic)
│   ├── rag/                  # RAG system (ChromaDB, hybrid search)
│   ├── telegram/             # Telegram bot + Mini Apps API
│   ├── marketplace/          # RFQ system (Phase 3)
│   ├── admin/                # Admin approval workflows
│   ├── verification/         # GPS + deforestation checking
│   └── service/              # FastAPI main service
│       ├── api.py            # Main app (19 routers)
│       ├── financing_api.py  # DeFi trade finance
│       ├── dpp_api.py        # DPP + EUDR compliance
│       ├── logistics_api.py  # LSP + webhook endpoints
│       └── webhook_dispatcher.py # Async webhook dispatch
├── miniapps/                 # Telegram Mini Apps (5 apps)
│   ├── index.html            # Main menu hub
│   ├── batch_browser.html    # Batch management
│   ├── marketplace.html      # RFQ marketplace
│   ├── trace.html            # Traceability viewer
│   ├── profile.html          # User profile
│   ├── admin.html            # Admin dashboard
│   └── shared/               # Shared JS + icons
│       ├── voice.js          # Voice recording library (882 lines)
│       └── icons.html        # SVG icon library
├── blockchain/               # Smart contracts (Solidity)
│   ├── src/                  # 7 contracts (ERC-1155, ERC-4626, escrow, etc.)
│   └── test/                 # Foundry tests
├── epcis/                    # EPCIS 2.0 event generation
├── ssi/                      # DIDs + Verifiable Credentials
├── database/                 # PostgreSQL models + migrations
├── ipfs/                     # IPFS storage (Pinata)
├── dpp/                      # Digital Product Passport
├── gs1/                      # GS1 identifier generation
└── tests/                    # Integration tests
```

---

## Configuration

Required environment variables:

```bash
# OpenAI (ASR + Conversational AI + Embeddings)
OPENAI_API_KEY=sk-...

# Database (Neon serverless PostgreSQL)
DATABASE_URL=postgresql://username:password@host.neon.tech/dbname

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_BOT_USERNAME=voice_ledger_bot

# Redis (Celery + sessions)
REDIS_URL=redis://localhost:6379/0

# ChromaDB Cloud (RAG vector database)
CHROMA_API_KEY=...
CHROMA_API_URL=https://api.trychroma.com
CHROMA_COLLECTION=voice_ledger_docs_v2

# Blockchain
BLOCKCHAIN_RPC_URL=https://sepolia.base.org
PRIVATE_KEY=0x...
EPCIS_EVENT_ANCHOR_ADDRESS=0xfda9...
COFFEE_BATCH_TOKEN_ADDRESS=0x2ff4...
SETTLEMENT_CONTRACT_ADDRESS=0x739b...
FINANCING_POOL_ADDRESS=0x1A2f...
TRADE_ESCROW_ADDRESS=0x32Af...
FEE_DISTRIBUTOR_ADDRESS=0xb763...
USDC_ADDRESS=0x036C...

# IPFS
PINATA_JWT=...

# AddisAI (Amharic conversational AI)
ADDIS_AI_API_KEY=...
ADDIS_AI_API_URL=https://addisai.net/api/v1

# AI Agent
AGENT_ENABLED=true           # Enable agentic tool-calling (false = legacy NLU)
AGENT_MODEL=gpt-4o           # OpenAI model for agent reasoning
AGENT_MAX_TURNS=6            # Max reasoning turns per request
AGENT_TEMPERATURE=0.2        # Low temperature for deterministic tool selection

# Optional: EUDR compliance
GFW_API_KEY=...  # Global Forest Watch API
```

---

## Standards Compliance

- **EPCIS 2.0** (ISO/IEC 19987:2024)
- **W3C DIDs** (did:key, Ed25519)
- **W3C Verifiable Credentials** (v1.1)
- **GS1 Identifiers** (GTIN-13, GLN, SSCC)
- **ERC-1155** (Multi Token Standard)
- **ERC-4626** (Tokenized Vault Standard)
- **EU Deforestation Regulation** (EUDR, Articles 9, 10, 33)

---

## Performance Metrics

**Voice Processing:**
- Latency: 5-15s (async pipeline)
- Cost: $0.008-0.010 per command
- ASR Accuracy: 95% (English), 88% (Amharic)

**AI Agent (v2.1):**
- Model: GPT-4o with function-calling
- Tools: 37 across 10 domains
- Max Turns: 6 (bounded reasoning loop)
- Timeout: 4 minutes (soft), 5 minutes (hard)
- Fallback: RAG pipeline for documentation queries
- History: Redis-backed, 10-minute TTL

**RAG System:**
- Knowledge Base: 3,539 documents (documentation + research)
- Embedding Model: OpenAI text-embedding-3-small (1536D)
- Vector Search: ChromaDB Cloud (no OOM, scalable)
- Retrieval Time: 200-500ms (hybrid search)

**Blockchain:**
- Gas cost: 75% reduction (Merkle proofs)
- Storage: 40% savings (IPFS vs on-chain)
- Network: Base Sepolia (low fees, fast finality)

**EUDR Compliance:**
- Processing: <5 seconds per farmer photo
- Cost: $0.065/farmer/month
- ROI: 2,500,000x (one customs rejection = $160K)

**Mini Apps:**
- Load Time: <2s (vanilla JS, no framework overhead)
- Voice Recording: WebM/Opus (efficient compression)
- TTS Playback: Pause/resume/replay controls
- Error Handling: Exponential backoff retry (3 attempts)

---

## Roadmap

**v2.0 (January 2026)** ✅
- ✅ Telegram Mini Apps (5 voice-first web apps)
- ✅ RAG-enhanced conversational AI (ChromaDB Cloud)
- ✅ Hybrid search (documentation + operational data)
- ✅ Bilingual support (English GPT-4 + Amharic AddisAI)
- ✅ Context-aware voice processing (882-line voice.js)
- ✅ Multi-actor marketplace with voice UI
- ✅ EUDR GPS + deforestation detection
- ✅ 90+ passing tests

**v2.1 (February 2026)** ✅
- ✅ Agentic AI: GPT-4o tool-calling agent (25 initial tools, 7 domains)
- ✅ Multi-turn conversation with Redis-backed history
- ✅ Safety rails: write-tool gating, bounded turns, timeout handling
- ✅ Dual delivery: text + TTS voice note on every response
- ✅ Production deployment on Railway (web + Celery worker + Redis)
- ✅ Chainlink CRE workflow simulation + ProvenanceDataReceiver contract

**v2.2 (Current — March 2026)** ✅
- ✅ DeFi trade finance: FinancingPool (ERC-4626), TradeEscrow, FeeDistributor
- ✅ LSP integration: webhook dispatch, milestone ingestion → EPCIS events
- ✅ Customs clearance: DPP API, EUDR Article 9 flat export, container-level compliance
- ✅ Agent expanded to 37 tools across 10 domains (Container, Pool, Chainlink DON, Payment)
- ✅ 7 verified smart contracts on Base Sepolia

**v3.0 (Planned — Q2/Q3 2026)**
- [ ] Chainlink CRE DON deployment (pending CRE mainnet)
- [ ] Payment integration (M-PESA, TeleBirr, Stripe)
- [ ] Base mainnet deployment
- [ ] Multi-origin expansion (Ethiopia → Colombia, Kenya, Vietnam)
- [ ] Realtime voice UI (<1s latency, WebSocket)
- [ ] 5 languages (add Afan Oromo, Tigrinya, Spanish)

---

## Documentation

Comprehensive guides in `/documentation`:
- **Labs** (31 educational tutorials)
  - Lab 28: Agentic AI — Tool-Calling Agent Architecture
  - Lab 29: Chainlink CRE — Agent-to-Oracle Bridge
  - Lab 30: CRE Demo — Hackathon Submission
  - Lab 31: UNICEF Pitch Video Runbook
- **Guides** (EUDR, ASR, marketplace, RAG, architecture)
- **Deployment** (Railway, Neon, Docker, production, ChromaDB Cloud)
- **Business** (pitch deck, grant proposals, partnership strategies)

**Key Resources:**
- `voice/agent/` - AI agent implementation (executor, registry, schemas)
- `documentation/business-docs/DEFI_TRADE_FINANCE.md` - Receivables factoring design
- `documentation/business-docs/LOGISTICS_SERVICE_PROVIDER_INTEGRATION.md` - LSP strategy
- `documentation/business-docs/EUROPEAN_CUSTOMS_CLEARANCE_PARTNER.md` - Customs broker integration
- `documentation/guides/CHROMADB_CLOUD_SETUP.md` - RAG vector database setup

---

## License

MIT

--- 

---

**Version:** 2.2 (Production)  
**Last Updated:** March 6, 2026  
**Major Features:** 37-tool AI agent, DeFi trade finance (ERC-4626), LSP & customs integration, 7 smart contracts on Base Sepolia
