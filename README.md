# Voice Ledger

**Voice-first blockchain traceability for coffee supply chains.** Farmers speak, the system records everything from harvest to export, anchored on-chain with IPFS storage. Built for smallholder farmers who shouldn't need a smartphone to prove their coffee's provenance.

**Current:** v2.0 (Production) - Telegram Mini Apps, RAG-enhanced AI, conversational UI  
**Status:** Deployed, tested, ready for scale

---

## What It Does

Voice Ledger converts spoken supply chain events into verifiable blockchain records. Farmers send voice messages via Telegram in Amharic or English. The system transcribes, understands intent using RAG-enhanced conversational AI, generates standardized EPCIS 2.0 events, stores full data on IPFS, and anchors cryptographic hashes on-chain.

**The pitch:** A smallholder farmer in Yirgacheffe records "50 kilograms washed Arabica from Manufam farm" via voice. Minutes later, that batch has a tokenized identity (ERC-1155), blockchain-verified provenance, GPS coordinates proving deforestation-free origin, and a QR code that buyers can scan for full supply chain history. All accessible through Telegram Mini Apps with voice-first interaction.

---

## Core Components

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
- **RAG-Enhanced Conversational AI**: ChromaDB Cloud + GPT-4
  - 3,539 documents indexed (system documentation + research papers)
  - Hybrid search (documentation + operational data)
  - Query classification (TRANSACTIONAL, DOCUMENTATION, OPERATIONAL, HYBRID)
  - Context-aware responses using specific technical details
  - Bilingual support (English & Amharic with AddisAI)
- **Latency**: 5-15 seconds end-to-end (async pipeline)
- **IVR Ready**: Twilio integration for feature phones (planned)

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

### Blockchain & Storage
- **Smart Contracts** (Base Sepolia):
  - `EPCISEventAnchor.sol`: Hash anchoring with IPFS CID storage
  - `CoffeeBatchToken.sol`: ERC-1155 semi-fungible tokens (50/50 tests passing)
  - `SettlementContract.sol`: Multi-currency tracking (USD, ETH, BIRR, USDC)
- **IPFS Storage**: Full event data on Pinata (40% gas savings vs on-chain)
- **Merkle Proofs**: Batch aggregation (75% gas reduction)

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
- OpenAI GPT-4 (conversational AI with RAG)
- AddisAI API (Amharic conversational AI)
- ChromaDB Cloud (vector database, 3,539 docs)
  - OpenAI text-embedding-3-small (1536 dimensions)
  - Hybrid search (vector similarity + metadata filtering)

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
Transcript → RAG-Enhanced Conversational AI
    ├─→ ChromaDB Vector Search (documentation)
    ├─→ PostgreSQL Query (operational data)
    └─→ GPT-4 / AddisAI (response generation)
    ↓
Intent + Entities + Action
    ↓
Command Execution (async Celery)
    ├─→ EPCIS Event Builder
    ├─→ Database Updates
    └─→ Blockchain Anchor
    ↓
┌─────────────┴──────────────┐
↓                            ↓
IPFS Storage            Blockchain Anchor
(Full Event)            (Hash + CID + Timestamp)
    ↓                            ↓
QR Code ← Digital Product Passport (DPP)
```

**Data Flow:**
1. Farmer speaks (Amharic/English) via Telegram or Mini App
2. ASR transcribes based on user language preference
3. RAG system enhances query with relevant documentation/data context
4. Conversational AI (GPT-4/AddisAI) generates response + optional action
5. If action present: System executes (create EPCIS event, update DB, etc.)
6. EPCIS event → JSON-LD canonicalization → SHA-256 hash
7. Full event → IPFS (get CID)
8. Hash + CID → Blockchain (immutable anchor)
9. Token minted (ERC-1155) + QR code generated
10. User receives confirmation + TTS audio response

**RAG Architecture (Lab 18):**
```
User Query
    ↓
Query Classifier → [TRANSACTIONAL | DOCUMENTATION | OPERATIONAL | HYBRID]
    ↓
Hybrid Router
    ├─→ ChromaDB (vector search: 3,539 docs)
    ├─→ PostgreSQL (structured data: batches, users, RFQs)
    └─→ Combine contexts
    ↓
Enhanced Prompt (with specific technical details)
    ↓
GPT-4 / AddisAI (knowledge-grounded response)
```

---

## Testing

```bash
# Run all tests (90+ tests)
pytest

# Voice processing
pytest tests/test_voice_api.py

# RAG system (Lab 18)
pytest tests/test_rag_integration.py

# Conversational AI
pytest tests/test_english_conversation.py
pytest tests/test_amharic_conversation.py

# Blockchain integration
pytest tests/test_anchor_flow.py
pytest tests/test_ipfs_blockchain_integration.py

# EUDR compliance
pytest tests/test_eudr_compliance.py  # 42/42 passing

# Smart contracts
cd blockchain && forge test  # 50/50 passing

# PIN setup (Phase 3)
pytest tests/test_pin_setup.py  # 6/6 passing

# Mini Apps (integration testing via Telegram)
# 1. Open @voice_ledger_bot
# 2. Navigate to each Mini App
# 3. Test voice recording on each screen
# 4. Verify context-aware responses
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

**Schema (7 core tables):**
- `user_identities`: DIDs, keys, language preferences, PINs
- `coffee_batches`: GTIN, token IDs, quantities, origins
- `epcis_events`: Event hashes, IPFS CIDs, blockchain TXs
- `verifiable_credentials`: Certifications, quality grades
- `pending_registrations`: Multi-step registration state
- `rfqs`: Request for Quotations (marketplace)
- `offers`: Offers on RFQs (marketplace)

---

## Project Structure

```
Voice-Ledger/
├── voice/                    # Voice processing pipeline
│   ├── asr/                  # Automatic speech recognition
│   ├── nlu/                  # Natural language understanding
│   ├── integrations/         # Conversational AI (English + Amharic)
│   ├── rag/                  # RAG system (ChromaDB, hybrid search)
│   ├── telegram/             # Telegram bot + Mini Apps API
│   ├── marketplace/          # RFQ system (Phase 3)
│   ├── admin/                # Admin approval workflows
│   ├── verification/         # GPS + deforestation checking
│   └── service/              # FastAPI main service
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
│   ├── src/                  # EPCISEventAnchor, CoffeeBatchToken, Settlement
│   └── test/                 # Foundry tests (50/50 passing)
├── epcis/                    # EPCIS 2.0 event generation
├── ssi/                      # DIDs + Verifiable Credentials
├── database/                 # PostgreSQL models + migrations
├── ipfs/                     # IPFS storage (Pinata)
├── dpp/                      # Digital Product Passport
├── gs1/                      # GS1 identifier generation
└── tests/                    # 90+ integration tests
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

# IPFS
PINATA_JWT=...

# AddisAI (Amharic conversational AI)
ADDIS_AI_API_KEY=...
ADDIS_AI_API_URL=https://addisai.net/api/v1

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
- **EU Deforestation Regulation** (EUDR, Articles 9, 10, 33)

---

## Performance Metrics

**Voice Processing:**
- Latency: 5-15s (async pipeline)
- Cost: $0.008-0.010 per command
- ASR Accuracy: 95% (English), 88% (Amharic)
- Conversational AI: GPT-4 (English), AddisAI (Amharic)

**RAG System (Lab 18):**
- Knowledge Base: 3,539 documents (documentation + research)
- Embedding Model: OpenAI text-embedding-3-small (1536D)
- Vector Search: ChromaDB Cloud (no OOM, scalable)
- Retrieval Time: 200-500ms (hybrid search)
- Query Classification: TRANSACTIONAL, DOCUMENTATION, OPERATIONAL, HYBRID

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

**v2.0 (Current - January 2026)** ✅
- ✅ Telegram Mini Apps (5 voice-first web apps)
- ✅ RAG-enhanced conversational AI (ChromaDB Cloud)
- ✅ Hybrid search (documentation + operational data)
- ✅ Bilingual support (English GPT-4 + Amharic AddisAI)
- ✅ Context-aware voice processing (882-line voice.js)
- ✅ Multi-actor marketplace with voice UI
- ✅ EUDR GPS + deforestation detection
- ✅ 90+ passing tests

**v2.1 (Planned - Q2 2026)**
- [ ] Realtime voice UI (<1s latency, WebSocket)
- [ ] Payment integration (Stripe, M-PESA, TeleBirr)
- [ ] Mobile app (offline-capable, React Native)
- [ ] Advanced analytics dashboard
- [ ] Batch recommendations (ML-based)

**v2.2 (Planned - Q3 2026)**
- [ ] 5 languages (add Afan Oromo, Tigrinya, Spanish)
- [ ] Edge inference (quantized models, on-device ASR)
- [ ] Mainnet deployment (Base L2)
- [ ] Integration with external coffee platforms (ICO, ECX)
- [ ] Advanced traceability maps (GPS visualization)

---

## Documentation

Comprehensive guides in `/documentation`:
- **Labs** (18 educational tutorials, gitignored)
  - Lab 18: RAG-Enhanced Conversational AI (latest)
- **Guides** (EUDR, ASR, marketplace, RAG, architecture)
- **Deployment** (Neon setup, Docker, production, ChromaDB Cloud)
- **Business** (pitch deck, grant proposals)
- **Mini Apps** (COMPLETION_SUMMARY.md, IMPLEMENTATION_PLAN.md)

**Key Resources:**
- `miniapps/COMPLETION_SUMMARY.md` - Complete Mini Apps implementation guide
- `documentation/guides/CHROMADB_CLOUD_SETUP.md` - RAG vector database setup
- `documentation/guides/CONVERSATIONAL_AI.md` - Conversational AI architecture
- `voice/rag/README.md` - RAG system documentation

---

## License

MIT

--- 

---

**Version:** 2.0 (Production)  
**Last Updated:** January 20, 2026  
**Major Features:** Telegram Mini Apps, RAG-Enhanced AI, ChromaDB Cloud Integration
