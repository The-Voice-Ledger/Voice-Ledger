# The Voice Ledger

A voice-first blockchain traceability system for coffee supply chains that enables natural language event recording using standardized EPCIS 2.0 events, self-sovereign identity, and immutable blockchain anchoring.

**Current Status:** v1.5 (Bilingual Cloud) - Functional, English + Amharic, automatic language detection  
**In Development:** v2.0 (Offline-First) - 5 languages, offline-capable, 95%+ rural accessibility

## New Features (v1.5 - December 2025)

- **Bilingual Support**: Automatic English/Amharic language detection
- **50% Cost Savings**: Local Amharic model reduces transcription costs to $0
- **Telegram Bot**: @voice_ledger_bot for easy voice message submission
- **Async Processing**: Celery + Redis for non-blocking operations
- **Production Ready**: Database connection pooling, enhanced error handling
- **Comprehensive Docs**: 3000+ lines of documentation

## Overview

The Voice Ledger converts spoken supply chain events into verifiable, blockchain-anchored records. The system processes voice commands through automatic speech recognition and natural language understanding to generate standardized GS1 EPCIS 2.0 events, which are canonicalized, hashed, and anchored to blockchain with full event data stored on IPFS.

**v1.5 (Current Implementation):** Cloud-based system with **bilingual support (English + Amharic)**, automatic language detection, Telegram bot interface, and optimized costs (50% savings on Amharic transcriptions via local model).

**v2.0 (Planned):** Offline-first system with on-device AI models supporting 5 languages (Amharic, Afan Oromo, Tigrinya, Spanish, English) for 11M+ smallholder farmers.

## System Architecture (v1.5 - Current)

```
Voice Input (Telegram/IVR) → Language Detection (Whisper API)
                                       ↓
                              ┌────────┴────────┐
                              ↓                 ↓
                         Amharic?          English?
                              ↓                 ↓
                    Local Whisper Model   OpenAI Whisper API
                    (b1n1yam/shhook)      (whisper-1)
                    [On-device, $0]       [Cloud, $0.02]
                              ↓                 ↓
                              └────────┬────────┘
                                       ↓
                              NLU (GPT-3.5 API)
                              [Works both languages]
                                       ↓
                              EPCIS Event Builder
                                       ↓
                           Canonicalization (URDNA2015)
                                       ↓
                                 SHA-256 Hash
                                       ↓
                    ┌──────────────────┴──────────────────┐
                    ↓                                      ↓
              IPFS Storage                          Blockchain Anchor
           (Full Event Data)                   (Hash + CID + Timestamp)
```

## Implemented Components (v1.0)

### Core Modules (v1.0 - Production Ready)

**GS1 Identifier Generation** [COMPLETE]
- GTIN-13 generation with check digit validation
- GLN (Global Location Number) for farms and facilities
- SSCC (Serial Shipping Container Code) for shipments
- Compliance with GS1 standards

**EPCIS 2.0 Event Builder** [COMPLETE]
- ObjectEvent for harvest and observation
- TransformationEvent for processing stages
- AggregationEvent for shipment composition
- Full JSON-LD context with CBV business steps
- Instance/Lot Master Data (ILMD) support

**JSON-LD Canonicalization** [COMPLETE]
- URDNA2015 algorithm implementation using pyld
- Deterministic N-Quads output
- Semantic equivalence verification
- Ensures identical hashes regardless of key ordering

**Cryptographic Hashing** [COMPLETE]
- SHA-256 hashing of canonical events
- Event hash generation for blockchain anchoring
- Metadata tracking (algorithm, canonicalization method)

**W3C Decentralized Identifiers (DIDs)** [COMPLETE]
- did:key method implementation
- Ed25519 key pair generation using PyNaCl
- DID document resolution
- Multibase encoding (base58btc)

**Verifiable Credentials** [COMPLETE]
- W3C VC Data Model 1.1 implementation
- Ed25519Signature2020 proof type
- Organic certification credentials
- Quality grade credentials
- Credential verification with signature validation

**Smart Contracts** [COMPLETE]
- EPCISEventAnchor.sol: Event hash anchoring with IPFS CID storage
- CoffeeBatchToken.sol: ERC-1155 semi-fungible tokens for batch representation
- Event linking to token metadata
- Solidity 0.8.20 with OpenZeppelin libraries

**IPFS Integration** [COMPLETE]
- Full EPCIS event storage
- Content-addressed retrieval
- Pinata integration for persistent pinning
- Local IPFS node support

**Digital Twin Synchronization** [COMPLETE]
- Unified state management combining on-chain and off-chain data
- Neon PostgreSQL persistence layer
- Batch lifecycle tracking
- Event history aggregation
- Migration from JSON completed (9/9 batches)

**Voice Processing API** [COMPLETE - v1.5 Bilingual]
- FastAPI REST service for audio processing
- **Bilingual ASR**: Automatic language detection (English + Amharic)
- **Dual model routing**: OpenAI Whisper API (English) + Local Amharic model (b1n1yam/shhook-1.2k-sm)
- GPT-3.5 for natural language understanding (supports both languages)
- Entity extraction (quantity, variety, location, date, batch_id)
- Intent classification (commission, receipt, shipment, transformation)
- Celery + Redis for async processing
- API key authentication
- **Performance**: 2-4s (English), 3-6s (Amharic), 50% cost savings on Amharic

**Web Dashboard** [COMPLETE]
- Streamlit-based interface
- Batch tracking by GTIN or batch number
- Event timeline visualization
- Supply chain journey mapping
- Blockchain verification interface
**Digital Product Passport (DPP)** [COMPLETE]
- GS1 Digital Link URI generation
- QR code generation with embedded metadata
- Batch information aggregation
- Resolver service for DPP retrieval

### Standards Compliance

**GS1 Standards**
- EPCIS 2.0 (ISO/IEC 19987:2024)
- Core Business Vocabulary (CBV)
- EPC Tag Data Standard

**W3C Standards**
- DID Core Specification
- Verifiable Credentials Data Model
- JSON-LD 1.1

**Ethereum Standards**
- ERC-1155 Multi Token Standard
- EIP-712 for typed data signing
## Technology Stack (v1.0)

**Backend**
- Python 3.11
- FastAPI 0.104.1
- SQLAlchemy 2.0.23 (Neon PostgreSQL integration)
- PyNaCl 1.5.0 (Ed25519 cryptography)
- PyLD 2.0.3 (JSON-LD canonicalization)
- Web3.py 6.11.3 (blockchain interaction)
**Voice Processing (v1.5 - Bilingual Cloud)**
- OpenAI Whisper API (ASR) - English, cloud-based
- Amharic Whisper Model (b1n1yam/shhook-1.2k-sm) - Local inference, $0 cost
- Automatic language detection and intelligent routing
- OpenAI GPT-3.5 (NLU) - Bilingual entity extraction (English + Amharic)
- Celery workers with solo pool for async task processing
- Redis message broker
- Telegram Bot API integration

**Voice Processing (v2.0 - Planned Offline)**
- Whisper-Small quantized (244MB) - 5 languages, on-device
- Gemma 3B + LoRA (1.5GB) - Offline entity extraction
- ONNX Runtime for mobile inference

**Blockchain**
- Foundry (Forge, Anvil) - Local development and testing
- Solidity 0.8.20 - Smart contract development
- OpenZeppelin 5.0 - Contract libraries
- Web3.py 6.11.3 - Blockchain interaction
- Polygon/Ethereum - Target deployment networks

**Storage**
- IPFS (Pinata) - Decentralized event storage with pinning service
- Neon serverless PostgreSQL - Production database [COMPLETE]
- SQLite offline queue - Planned for v2.0 mobile app

**Frontend**
- Streamlit 1.28.2
- Plotly 5.18.0

## Project Structure

```
Voice-Ledger/
├── gs1/
│   └── identifiers.py          # GTIN, GLN, SSCC generation
├── epcis/
│   ├── epcis_builder.py        # EPCIS event construction
│   ├── canonicalise.py         # URDNA2015 canonicalization
│   └── hash_event.py           # SHA-256 hashing
├── ssi/
│   ├── did/
│   │   └── did_key.py          # DID generation and resolution
│   └── agent.py                # Verifiable Credential issuance
├── blockchain/
│   └── src/
│       ├── EPCISEventAnchor.sol
│       ├── CoffeeBatchToken.sol
│       └── SettlementContract.sol
├── voice/
│   ├── asr/
│   │   └── asr_infer.py        # Bilingual Whisper (EN + AM)
│   ├── nlu/
│   │   └── nlu_infer.py        # GPT-3.5 intent parsing
│   ├── telegram/
│   │   ├── telegram_api.py     # Telegram bot webhook
│   │   └── notifier.py         # Synchronous notifications
│   ├── channels/
│   │   ├── processor.py        # Multi-channel processor
│   │   ├── telegram_channel.py # Telegram integration
│   │   └── twilio_channel.py   # IVR integration (ready)
│   ├── tasks/
│   │   └── voice_tasks.py      # Celery async tasks
│   ├── service/
│   │   ├── api.py              # FastAPI REST service
│   │   └── auth.py             # API authentication
│   └── command_integration.py  # Voice → Database integration
├── database/
│   ├── models.py               # SQLAlchemy models (5 tables)
│   ├── connection.py           # Database session management
│   ├── crud.py                 # CRUD operations
│   └── test_db.py              # Database integration tests
├── scripts/
│   ├── migrate_to_neon.py      # JSON to Neon migration
│   └── clear_database.py       # Database maintenance
├── ipfs/
│   ├── ipfs_client.py          # IPFS integration (Pinata)
│   └── ipfs_upload.py          # Event upload to IPFS
├── twin/
│   └── twin_builder.py         # Digital twin management
├── dpp/
│   ├── schema.json             # DPP JSON Schema (EUDR)
│   ├── dpp_builder.py          # Digital Product Passport
│   ├── dpp_resolver.py         # DPP resolution service
│   └── qrcode_gen.py           # QR code generation
├── dashboard/
│   └── app.py                  # Streamlit dashboard
├── documentation/              # Comprehensive documentation
│   ├── VOICE_IVR_BUILD_LOG.md  # Complete implementation history
│   ├── BILINGUAL_ASR_GUIDE.md  # Bilingual system guide
│   ├── Technical_Guide.md      # Technical architecture
│   └── [30+ other docs]        # Setup, testing, operations
├── admin_scripts/              # Admin tools (git-ignored)
│   ├── START_SERVICES.sh       # Service startup
│   ├── STOP_SERVICES.sh        # Service shutdown
│   ├── CHECK_STATUS.sh         # Status monitoring
│   └── *.log                   # Service logs
└── tests/
    ├── test_dpp.py
    ├── test_ssi.py
    ├── test_anchor_flow.py
    └── test_voice_api.py
```

## Installation

```bash
# Clone repository
git clone https://github.com/voice-ledger/voice-ledger.git
cd Voice-Ledger

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with API keys and configuration
```

## Configuration

Environment variables required:

```bash
OPENAI_API_KEY=sk-...                    # OpenAI API key
TELEGRAM_BOT_TOKEN=...                   # Telegram bot token
VOICE_API_KEY=vl_...                     # API authentication key
BLOCKCHAIN_RPC_URL=https://...           # Ethereum RPC endpoint
DATABASE_URL=postgresql://...            # Neon database connection
REDIS_URL=redis://localhost:6379/0      # Redis for Celery
```

## Quick Start

```bash
# 1. Start all services
./admin_scripts/START_SERVICES.sh

# 2. Check status
./admin_scripts/CHECK_STATUS.sh

# 3. Send voice message to Telegram bot
# Message @voice_ledger_bot on Telegram with:
#   English: "New batch of 50kg Yirgacheffe from Manufam farm"
#   Amharic: "አዲስ ቢራ 50 ኪሎ ይርጋቸፍ ከማኑፋም እርሻ"

# 4. Monitor logs
tail -f admin_scripts/celery.log | grep "Detected language"
```

## Usage

**Telegram Bot (Recommended)**

```bash
# Start Telegram bot
python -m voice.telegram.telegram_api

# Send voice messages to @voice_ledger_bot
# System automatically detects English or Amharic
# Supports all 4 command types:
#   - New batch (commission)
#   - Received coffee (receipt)
#   - Sent coffee (shipment)
#   - Processed coffee (transformation)
```

**Voice Processing API (Direct)**

```bash
# Start API server
uvicorn voice.service.api:app --host 0.0.0.0 --port 8000

# Test bilingual ASR
python -m voice.asr.asr_infer audio.wav

# Process via API
curl -X POST http://localhost:8000/asr-nlu \
  -H "X-API-Key: vl_test_12345" \
  -F "file=@harvest_command.wav"
```

**Digital Product Passport Generation**

```python
from dpp.dpp_builder import build_dpp

dpp = build_dpp(
    batch_id="BATCH-2025-001",
    gtin="6001234567895",
    quantity_kg=500,
    origin="Yirgacheffe, Ethiopia",
    variety="Arabica Typica"
)
```

**Smart Contract Deployment**

```bash
# Deploy to local testnet
forge create --rpc-url http://localhost:8545 \
    --private-key 0x... \
    src/EPCISEventAnchor.sol:EPCISEventAnchor

# Deploy to Polygon Mumbai
forge create --rpc-url https://rpc-mumbai.maticvigil.com \
    --private-key $PRIVATE_KEY \
    --verify \
    src/EPCISEventAnchor.sol:EPCISEventAnchor
```

**Web Dashboard**

```bash
streamlit run dashboard/app.py
```

## Testing

```bash
# Run all tests
pytest

# Run specific test module
pytest tests/test_ssi.py

# Run with coverage
pytest --cov=. --cov-report=html

# Test smart contracts
cd blockchain
forge test
```

## Data Flow Example

```python
# 1. Generate identifiers
from gs1.identifiers import generate_gtin_13, generate_gln

gtin = generate_gtin_13("6001234", "56789")
gln = generate_gln("6001234", "00123")

# 2. Create EPCIS event
from epcis.epcis_builder import build_commissioning_event

event = build_commissioning_event(
    batch_id="BATCH-2025-001",
    gtin=gtin,
    quantity_kg=500,
    biz_location=gln,
    farmer_did="did:key:z6Mk..."
)

# 3. Canonicalize and hash
from epcis.canonicalise import canonicalise_event
from epcis.hash_event import hash_event

canonical = canonicalise_event(event)
event_hash = hash_event(canonical)

# 4. Anchor to blockchain
from blockchain import anchor_event

tx_hash = anchor_event(event_hash, "ObjectEvent", ipfs_cid)
```

## Performance Characteristics

**Voice Processing Latency**
- ASR (Whisper): 3-5 seconds
- NLU (GPT-3.5): 1-2 seconds
- Total pipeline: 8-15 seconds

**Cryptographic Operations**
- Ed25519 key generation: <1ms
- Ed25519 signing: <1ms
- SHA-256 hashing: <1ms (for typical EPCIS event)
- URDNA2015 canonicalization: 10-50ms

**Blockchain Operations**
- Event anchor gas cost: ~50,000 gas units
- ERC-1155 mint gas cost: ~80,000 gas units
- Transaction confirmation: 2-15 seconds (network dependent)

## Security Considerations

**Key Management**
- Ed25519 private keys encrypted with user password
- PBKDF2 key derivation (100,000 iterations)
- Keys never transmitted over network
- Secure enclave storage on mobile devices

**API Security**
- API key authentication on all endpoints
- Rate limiting to prevent abuse
## Recent Improvements (v1.5)

### Bilingual Support (December 2025)
- **Automatic language detection**: English and Amharic
- **Dual model architecture**: OpenAI API (English) + Local model (Amharic)
- **50% cost savings**: Amharic transcriptions run locally ($0 vs $0.02)
- **Zero configuration**: Farmers just speak, system auto-detects language
- **57M+ Amharic speakers**: Now accessible to Ethiopian farmers

### Production Enhancements
- **Telegram bot**: @voice_ledger_bot fully operational
- **Async processing**: Celery + Redis for non-blocking operations
- **Database connection pooling**: SSL handling with auto-reconnection
- **Enhanced NLU**: Comprehensive prompts with coffee domain examples
- **Improved batch IDs**: Timestamp-based to prevent collisions
- **Synchronous notifications**: Reliable Telegram message delivery

### Documentation & Organization
- **3000+ lines** of comprehensive documentation
- **Centralized docs**: All in `documentation/` folder
- **Admin scripts**: Service management tools in `admin_scripts/`
- **Complete build log**: Full implementation history tracked

## Current Limitations (v1.5)

- Voice processing requires internet connectivity (cloud APIs)
- Two languages currently supported (English + Amharic)
- Cloud API costs for English ($0.02/transaction)
- No mobile application implementation
- 2-6 second latency for voice processing
- ~30% of rural Ethiopian farmers have required connectivity

**These limitations are addressed in v2.0 roadmap below.**

## Documentation

Comprehensive documentation in `documentation/` folder:

**Core Documentation**
- `VOICE_IVR_BUILD_LOG.md`: Complete implementation history (1900+ lines)
- `BILINGUAL_ASR_GUIDE.md`: Bilingual system architecture and usage (400+ lines)
- `Technical_Guide.md`: Technical implementation details
- `INDEX.md`: Complete documentation index

**Setup & Operations**
- `QUICK_START.md`: Quick start guide for developers
- `SERVICE_COMMANDS.md`: Service management reference
- `BILINGUAL_QUICKSTART.md`: Testing bilingual features
- `../admin_scripts/README.md`: Admin tools documentation

**Implementation Summaries**
- `SESSION_FIXES_SUMMARY.md`: Production fixes (December 15, 2025)
- `BILINGUAL_IMPLEMENTATION_SUMMARY.md`: Bilingual implementation details

**Database & Integration**
- `NEON_DATABASE_SETUP.md`: Database setup and migration guide
- `NEON_INTEGRATION_COMPLETE.md`: Neon database integration status

**Business Documents**
- `PITCH_DECK.md`: Impact investor presentation
- `GRANT_PROPOSAL_TEMPLATE.md`: Grant application template

## Future Development Roadmap

### Version 2.0: Offline-First with Addis AI Integration

**Current State (v1.5 - Bilingual Cloud)**
- OpenAI Whisper ASR (cloud API, English, 2-4s latency)
- Local Amharic Whisper (b1n1yam/shhook-1.2k-sm, 3-6s latency)
- Automatic language detection and routing
- GPT-3.5 NLU (cloud API, works for both languages, 1-2s latency)
- English + Amharic supported
- Internet required
- $0.02 per English transaction, $0 per Amharic transaction
- ~30% rural accessibility (improved with Telegram bot)

**Planned State (v2.0 - Offline-First)**
- Whisper-Small quantized (244MB, on-device)
- Gemma 3B + LoRA (1.5GB, on-device)
- 5 languages (Amharic, Afan Oromo, Tigrinya, Spanish, English)
- No internet required (offline-first, sync when available)
- $0 marginal cost per transaction
- 95%+ rural accessibility

### Language Support

| Language | Region | Speakers | Coffee Farmers |
|----------|--------|----------|----------------|
| Amharic | Ethiopia | 32M | 2.5M |
| Afan Oromo | Ethiopia (Oromia) | 37M | 2.8M |
| Tigrinya | Ethiopia (Tigray) | 7M | 0.5M |
| Spanish | Latin America | 50M+ | 5M+ |
| English | International | 2M | 0.2M |

### Device Support Matrix

**Smartphone App (Android)**
- Whisper-Small ONNX (4-bit quantized): 244MB
- Gemma 3B ONNX (4-bit quantized): 1.5GB
- Offline SQLite queue for event storage
- Auto-sync when connectivity available
- Target: 30% of rural farmers

**IVR System (Feature Phones)**
- Toll-free number (e.g., 8000 1234)
- Edge GPU nodes (A100) in regional telecom centers
- Voice menu in 5 languages
- SMS receipt confirmation
- Target: 70% of rural farmers

### System Architecture Comparison

**v1.0 Architecture (Cloud-Dependent)**

```
┌─────────────────────────────────────┐
│   FARMER (Smartphone + Internet)   │
│   Records voice command             │
└──────────────┬──────────────────────┘
               │ Audio (WAV/MP3)
               ▼
┌─────────────────────────────────────┐
│   CLOUD PROCESSING (Required)       │
│  ┌──────────────┐  ┌──────────────┐│
│  │ OpenAI       │  │   GPT-3.5    ││
│  │ Whisper ASR  │→ │   NLU        ││
│  │ (3-5s)       │  │   (1-2s)     ││
│  └──────────────┘  └──────────────┘│
└──────────────┬──────────────────────┘
               │ Structured Data
               ▼
┌─────────────────────────────────────┐
│      BACKEND (FastAPI)              │
│  • Build EPCIS Event                │
│  • Canonicalize (URDNA2015)         │
│  • Hash (SHA-256)                   │
│  • Sign with DID                    │
└──────────────┬──────────────────────┘
               │
               ├─→ IPFS Storage
               ├─→ Blockchain Anchor
               └─→ JSON File Storage
```

**v2.0 Architecture (Offline-First)**

```
┌────────────────────────────────────────────────────────────┐
│              FARMER DEVICES (No Internet Required)         │
│                                                             │
│  ┌──────────────────────────┐  ┌───────────────────────┐  │
│  │ SMARTPHONE APP           │  │ FEATURE PHONE (IVR)   │  │
│  │ ┌──────────────────────┐ │  │ Call: 8000 1234       │  │
│  │ │ Whisper-Small (244MB)│ │  │ (Toll-free)           │  │
│  │ │ On-device ASR        │ │  │                       │  │
│  │ │ <1s latency          │ │  │ Edge GPU Node:        │  │
│  │ └──────────┬───────────┘ │  │ - Whisper ASR (0.8s)  │  │
│  │            ▼             │  │ - Gemma NLU (0.5s)    │  │
│  │ ┌──────────────────────┐ │  │ SMS confirmation      │  │
│  │ │ Gemma 3B + LoRA      │ │  └───────────┬───────────┘  │
│  │ │ On-device NLU        │ │              │              │
│  │ │ (1.5GB)              │ │              │              │
│  │ └──────────┬───────────┘ │              │              │
│  │            ▼             │              │              │
│  │ ┌──────────────────────┐ │              │              │
│  │ │ EPCIS Event Builder  │ │              │              │
│  │ │ SQLite Offline Queue │ │              │              │
│  │ └──────────┬───────────┘ │              │              │
│  └────────────┼──────────────┘              │              │
└───────────────┼─────────────────────────────┼──────────────┘
                │                             │
                │ (Sync when WiFi/3G available)
                ▼                             ▼
┌────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                       │
│  • Verify signature (DID)                                  │
│  • Canonicalize & Hash                                     │
│  • Deduplicate (check hash)                                │
│  • Store in Neon Database ──────┐                          │
└──────────────┬──────────────────┼──────────────────────────┘
               │                  │
               │                  ▼
               │         ┌─────────────────────────────┐
               │         │ NEON (Serverless Postgres)  │
               │         │ • EPCIS events              │
               │         │ • Farmer identities (DIDs)  │
               │         │ • Coffee batches            │
               │         │ • Verifiable credentials    │
               │         │ • Offline sync queue        │
               │         └─────────────────────────────┘
               │
               ├─────────→ IPFS Storage (full events)
               │
               └─────────→ Blockchain Anchor (hash + CID)
                          ┌──────────────────────────┐
                          │ Smart Contracts          │
                          │ • EPCISEventAnchor       │
                          │ • CoffeeBatchToken       │
                          │   (ERC-1155)             │
                          └──────────────────────────┘
```

### Key Improvements

**Accessibility**
- 6x increase in rural coverage (15% → 95%)
- Literacy-independent (voice-only interface)
- Works during network outages
- Supports feature phones via IVR

**Performance**
- 5x faster processing (<2s vs 8-15s)
- Zero latency dependency on cloud APIs
- On-device data privacy (voice never leaves device)

**Technical Architecture**
- Offline ASR: Whisper-Small with domain-specific fine-tuning (coffee terminology)
- Offline NLU: Gemma 3B with LoRA adapters for entity extraction
- Offline queue: SQLite database with conflict resolution
- Opportunistic sync: Automatic blockchain anchoring when connectivity restored

### Implementation Timeline

**Phase 1: Model Fine-Tuning (6 months)**
- Collect 100+ hours annotated audio per language
- Fine-tune Whisper-Small for coffee domain vocabulary
- Train Gemma 3B LoRA adapters for intent/entity extraction
- Target accuracy: 88-92% WER (Word Error Rate)

**Phase 2: Mobile App Development (6 months)**
- Native Android app with ONNX Runtime integration
- Offline queue with exponential backoff retry
- Secure DID key storage (encrypted with PIN)
- Background sync service

**Phase 3: IVR System Deployment (12 months)**
- Partner with Ethiopian Telecom for toll-free number
- Deploy edge GPU nodes (A100) in 10 regional centers
- Build multilingual IVR call flow
- SMS notification system

**Phase 4: Neon Database Migration** [COMPLETE]
- ✓ Replaced JSON file storage with Neon serverless PostgreSQL
- ✓ Unified database for dev/staging/production
- ✓ Database branching capability configured
- ✓ Migration script completed (9/9 batches migrated)
- ✓ Unique GTIN generation using gs1.identifiers module

### Database Migration: Neon Serverless Postgres [COMPLETE]

**Why Neon**
- Serverless auto-scaling (pay only for compute used)
- Database branching (like Git for databases)
- Same connection string for all environments
- Free tier: 10GB storage + 100 compute hours/month

**Implementation Completed**
```bash
# Dependencies installed ✓
pip install sqlalchemy asyncpg psycopg2-binary alembic

# Database connected ✓
export DATABASE_URL="postgresql://neondb_owner:***@ep-weathered-bread-agcdwm1n-pooler.c-2.eu-central-1.aws.neon.tech/neondb"

# Tables created ✓
python database/models.py

# Data migrated ✓ (9/9 batches)
python -m scripts.migrate_to_neon
```

**Database Schema (5 Tables)**
- `farmer_identities`: DID, encrypted keys, location, GLN
- `coffee_batches`: GTIN (unique), token ID, quantity, origin, variety
- `epcis_events`: Event hash, canonical form, IPFS CID, blockchain TX
- `verifiable_credentials`: Certifications, quality grades, VCs
- `offline_queue`: Pending events for sync

**Migration Results**
- ✓ All 9 batches migrated successfully
- ✓ Unique GTINs generated (0614141001000 - 0614141001008)
- ✓ CRUD operations tested and verified
- ✓ Connection verified (EU Central region)

### Target Impact

**Accessibility**
- 11M+ addressable smallholder farmers
- 95% rural coverage (vs 15% current)
- Support for 70% feature phone users

**Standards Compliance**
- EPCIS 2.0 (ISO/IEC 19987:2024)
- W3C DIDs and Verifiable Credentials
- EUDR automated compliance
- GS1 identifiers (GTIN, GLN, SSCC)

## License

MIT License

## Author

Emmanuel Acho, PhD

## Version

1.0.0 (Cloud Prototype) | 2.0.0 (Offline-First - In Development)
