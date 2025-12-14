# Voice Ledger

A voice-first blockchain traceability system for coffee supply chains that enables natural language event recording using standardized EPCIS 2.0 events, self-sovereign identity, and immutable blockchain anchoring.

## Overview

Voice Ledger converts spoken supply chain events into verifiable, blockchain-anchored records. The system processes voice commands through automatic speech recognition and natural language understanding to generate standardized GS1 EPCIS 2.0 events, which are canonicalized, hashed, and anchored to blockchain with full event data stored on IPFS.

## System Architecture

```
Voice Input → ASR (Whisper) → NLU (GPT-3.5) → EPCIS Event Builder
                                                      ↓
                                              Canonicalization (URDNA2015)
                                                      ↓
                                                SHA-256 Hash
                                                      ↓
                                    ┌─────────────────┴──────────────────┐
                                    ↓                                    ↓
                              IPFS Storage                      Blockchain Anchor
                           (Full Event Data)                  (Hash + CID + Timestamp)
```

## Implemented Components

### Core Modules

**GS1 Identifier Generation**
- GTIN-13 generation with check digit validation
- GLN (Global Location Number) for farms and facilities
- SSCC (Serial Shipping Container Code) for shipments
- Compliance with GS1 standards

**EPCIS 2.0 Event Builder**
- ObjectEvent for harvest and observation
- TransformationEvent for processing stages
- AggregationEvent for shipment composition
- Full JSON-LD context with CBV business steps
- Instance/Lot Master Data (ILMD) support

**JSON-LD Canonicalization**
- URDNA2015 algorithm implementation using pyld
- Deterministic N-Quads output
- Semantic equivalence verification
- Ensures identical hashes regardless of key ordering

**Cryptographic Hashing**
- SHA-256 hashing of canonical events
- Event hash generation for blockchain anchoring
- Metadata tracking (algorithm, canonicalization method)

**W3C Decentralized Identifiers (DIDs)**
- did:key method implementation
- Ed25519 key pair generation using PyNaCl
- DID document resolution
- Multibase encoding (base58btc)

**Verifiable Credentials**
- W3C VC Data Model 1.1 implementation
- Ed25519Signature2020 proof type
- Organic certification credentials
- Quality grade credentials
- Credential verification with signature validation

**Smart Contracts**
- EPCISEventAnchor.sol: Event hash anchoring with IPFS CID storage
- CoffeeBatchToken.sol: ERC-1155 semi-fungible tokens for batch representation
- Event linking to token metadata
- Solidity 0.8.20 with OpenZeppelin libraries

**IPFS Integration**
- Full EPCIS event storage
- Content-addressed retrieval
- Pinata integration for persistent pinning
- Local IPFS node support

**Digital Twin Synchronization**
- Unified state management combining on-chain and off-chain data
- JSON-based persistence layer
- Batch lifecycle tracking
- Event history aggregation

**Voice Processing API**
- FastAPI REST service for audio processing
- OpenAI Whisper integration for speech recognition
- GPT-3.5 for natural language understanding
- Entity extraction (quantity, variety, location, date)
- Intent classification (harvest, processing, shipment)
- API key authentication

**Web Dashboard**
- Streamlit-based interface
- Batch tracking by GTIN or batch number
- Event timeline visualization
- Supply chain journey mapping
- Blockchain verification interface

**Digital Product Passport (DPP)**
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

## Technology Stack

**Backend**
- Python 3.11
- FastAPI 0.104.1
- SQLAlchemy 2.0.23 (prepared for Neon database migration)
- PyNaCl 1.5.0 (Ed25519 cryptography)
- PyLD 2.0.3 (JSON-LD canonicalization)
- Web3.py 6.11.3 (blockchain interaction)

**Voice Processing**
- OpenAI Whisper (ASR)
- OpenAI GPT-3.5 (NLU)

**Blockchain**
- Foundry (Solidity development framework)
- Solidity 0.8.20
- OpenZeppelin Contracts 5.0.0
- Ethereum-compatible networks (Polygon, Ethereum)

**Storage**
- IPFS (go-ipfs)
- JSON file system (current)
- Neon serverless PostgreSQL (in progress)

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
│   └── contracts/
│       ├── EPCISEventAnchor.sol
│       └── CoffeeBatchToken.sol
├── voice/
│   ├── asr/
│   │   └── asr_infer.py        # Whisper integration
│   ├── nlu/
│   │   └── nlu_infer.py        # GPT-3.5 intent parsing
│   └── service/
│       ├── api.py              # FastAPI REST service
│       └── auth.py             # API authentication
├── twin/
│   └── twin_builder.py         # Digital twin management
├── dpp/
│   ├── dpp_builder.py          # Digital Product Passport
│   ├── dpp_resolver.py         # DPP resolution service
│   └── qrcode_gen.py           # QR code generation
├── dashboard/
│   └── app.py                  # Streamlit dashboard
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
VOICE_API_KEY=vl_...                     # API authentication key
BLOCKCHAIN_RPC_URL=https://...           # Ethereum RPC endpoint
DATABASE_URL=postgresql://...            # Neon database connection
```

## Usage

**Voice Processing API**

```bash
# Start API server
uvicorn voice.service.api:app --host 0.0.0.0 --port 8000

# Process voice command
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
- CORS configuration for production
- HTTPS required in production

**Smart Contract Security**
- OpenZeppelin audited libraries
- Access control with Ownable pattern
- Event emission for all state changes
- Reentrancy guards where applicable

## Current Limitations

- Voice processing requires internet connectivity (OpenAI API)
- English language only in current implementation
- JSON file-based storage (PostgreSQL migration in progress)
- Cloud API costs limit scalability
- No mobile application implementation

## Documentation

- `END_TO_END_WORKFLOW.md`: Comprehensive technical workflow documentation
- `VOICE_LEDGER_OVERVIEW.md`: System overview and future roadmap
- `NEON_DATABASE_SETUP.md`: Database migration guide
- `Technical_Guide.md`: Implementation details

## License

MIT License

## Author

Emmanuel Acho, PhD

## Version

1.0.0 (Cloud Prototype)
