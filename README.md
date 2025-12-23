# Voice Ledger

**Voice-first blockchain traceability for coffee supply chains.** Farmers speak, the system records—everything from harvest to export, anchored on-chain with IPFS storage. Built for 11M+ smallholder farmers who shouldn't need a smartphone to prove their coffee's provenance.

**Current:** v1.8 (Production) - Telegram bot, bilingual ASR, marketplace, EUDR compliance  
**Status:** Deployed, tested, ready for scale

---

## What It Does

Voice Ledger converts spoken supply chain events into verifiable blockchain records. Farmers send voice messages via Telegram in Amharic or English. The system transcribes, understands intent, generates standardized EPCIS 2.0 events, stores full data on IPFS, and anchors cryptographic hashes on-chain.

**The pitch:** A smallholder farmer in Yirgacheffe records "50 kilograms washed Arabica from Manufam farm" via voice. Minutes later, that batch has a tokenized identity (ERC-1155), blockchain-verified provenance, GPS coordinates proving deforestation-free origin, and a QR code that buyers can scan for full supply chain history.

---

## Core Components

### Voice Interface
- **Telegram Bot** (@voice_ledger_bot): Primary interface for farmers
- **Bilingual ASR**: Automatic English/Amharic routing
  - English: OpenAI Whisper API ($0.006/minute)
  - Amharic: Local fine-tuned model ($0, 9% WER)
- **NLU**: GPT-4o-mini extracts intents and entities from natural speech
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
- **PIN Authentication**: 4-digit PIN for web UI access (bcrypt, 5-attempt lockout)
- **Redis Session Persistence**: Session survival across server reloads
- **Registration Flow**: Multi-language, role-specific, with photo upload

---

## Tech Stack

**Backend**
- Python 3.9 + FastAPI
- PostgreSQL (Neon serverless) - database branching, auto-scaling
- Redis - Celery task queue + session storage
- SQLAlchemy 2.0 ORM

**Voice Processing**
- OpenAI Whisper API (English)
- `b1n1yam/shook-medium-amharic-2k` (local Amharic model, HuggingFace)
- OpenAI GPT-4o-mini (intent extraction)
- OpenAI GPT-4 (conversational AI, optional)

**Blockchain**
- Solidity 0.8.20 + OpenZeppelin 5.0
- Foundry (Forge, Anvil)
- Web3.py 6.11.3
- Base Sepolia testnet

**Storage & Crypto**
- IPFS (Pinata pinning service)
- PyNaCl (Ed25519 signatures)
- PyLD (JSON-LD canonicalization)

**Messaging**
- python-telegram-bot (Telegram webhook)
- Celery + Redis (async processing)

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

# Record new harvest
"New batch of 50 kilograms Sidama variety from Gedeo farm"
"አዲስ ባች 50 ኪሎ ሲዳማ ከገዴኦ እርሻ"

# Record receipt
"Received batch ABC123 from farmer Abebe"

# Record shipment
"Shipped batch ABC123 to Addis warehouse"

# Record processing
"Roasted batch ABC123, output 850 kilograms"

# View identity
/myidentity  # Shows DID, credentials, credit score

# Export credentials
/export  # Generates QR code with W3C Verifiable Presentation
```

### Direct API (Voice Processing)

```bash
# Start API server
uvicorn voice.service.api:app --port 8000

# Submit audio file
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
Voice Input (Telegram/IVR)
    ↓
Language Detection → [Amharic Model] or [Whisper API]
    ↓
Transcript → GPT-4o-mini (Intent + Entities)
    ↓
EPCIS Event Builder → JSON-LD Canonicalization
    ↓
SHA-256 Hash
    ↓
┌─────────────┴──────────────┐
↓                            ↓
IPFS Storage            Blockchain Anchor
(Full Event)            (Hash + CID + Timestamp)
    ↓                            ↓
QR Code ← Digital Product Passport (DPP)
```

**Data Flow:**
1. Farmer speaks (Amharic/English)
2. ASR transcribes based on user language preference
3. NLU extracts intent and entities
4. System creates EPCIS event, canonicalizes, hashes
5. Full event → IPFS (get CID)
6. Hash + CID → Blockchain (immutable anchor)
7. Token minted (ERC-1155) + QR code generated
8. Farmer receives confirmation + batch ID

---

## Testing

```bash
# Run all tests (90+ tests)
pytest

# Voice processing
pytest tests/test_voice_api.py

# Blockchain integration
pytest tests/test_anchor_flow.py
pytest tests/test_ipfs_blockchain_integration.py

# EUDR compliance
pytest tests/test_eudr_compliance.py  # 42/42 passing

# Smart contracts
cd blockchain && forge test  # 50/50 passing

# PIN setup (Phase 3)
pytest tests/test_pin_setup.py  # 6/6 passing
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

**Schema (5 core tables):**
- `user_identities`: DIDs, keys, language preferences, PINs
- `coffee_batches`: GTIN, token IDs, quantities, origins
- `epcis_events`: Event hashes, IPFS CIDs, blockchain TXs
- `verifiable_credentials`: Certifications, quality grades
- `pending_registrations`: Multi-step registration state

---

## Project Structure

```
Voice-Ledger/
├── voice/                    # Voice processing pipeline
│   ├── asr/                  # Automatic speech recognition
│   ├── nlu/                  # Natural language understanding
│   ├── telegram/             # Telegram bot + registration
│   ├── marketplace/          # RFQ system (Phase 3)
│   ├── admin/                # Admin approval workflows
│   └── verification/         # GPS + deforestation checking
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
# OpenAI (ASR + NLU)
OPENAI_API_KEY=sk-...

# Database (Neon serverless PostgreSQL)
DATABASE_URL=postgresql://username:password@host.neon.tech/dbname

# Telegram
TELEGRAM_BOT_TOKEN=...

# Redis (Celery + sessions)
REDIS_URL=redis://localhost:6379/0

# Blockchain
BLOCKCHAIN_RPC_URL=https://sepolia.base.org
PRIVATE_KEY=0x...

# IPFS
PINATA_JWT=...

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
- NLU Accuracy: 92% (intent), 87% (entities)

**Blockchain:**
- Gas cost: 75% reduction (Merkle proofs)
- Storage: 40% savings (IPFS vs on-chain)
- Network: Base Sepolia (low fees, fast finality)

**EUDR Compliance:**
- Processing: <5 seconds per farmer photo
- Cost: $0.065/farmer/month
- ROI: 2,500,000x (one customs rejection = $160K)

---

## Roadmap

**v1.8 (Current - December 2025)**
- ✅ Telegram bot with bilingual ASR
- ✅ Multi-actor marketplace (4 roles)
- ✅ PIN authentication + Redis sessions
- ✅ EUDR GPS + deforestation detection
- ✅ IPFS + blockchain integration
- ✅ 90+ passing tests

**v2.0 (Planned - Q2 2026)**
- [ ] Realtime voice UI (<1s latency, WebSocket)
- [ ] Payment integration (Stripe, M-PESA, TeleBirr)
- [ ] Mobile app (offline-capable)
- [ ] 5 languages (add Afan Oromo, Tigrinya, Spanish)
- [ ] Edge inference (quantized models)

---

## Documentation

Comprehensive guides in `/documentation`:
- **Labs** (17 educational tutorials, gitignored)
- **Guides** (EUDR, ASR, marketplace, architecture)
- **Deployment** (Neon setup, Docker, production)
- **Business** (pitch deck, grant proposals)

---

## License

MIT

---

## Author

Emmanuel Acho, PhD  
Building voice-first identity and traceability systems for the Global South.

---

**Version:** 1.8 (Production)  
**Last Updated:** December 23, 2025
