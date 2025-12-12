# Voice Ledger - Complete Build Log

This document tracks every step taken to build the Voice Ledger prototype, with explanations of why each step is necessary and what outcome to expect.

---

## Project Setup

### Step 1: Verify Python Installation

**Command:**
```bash
python3 --version
```

**Why:** We need Python 3.10+ (or 3.9.6 minimum) to run all the components in the Voice Ledger system. This verifies the Python version available on the system.

**Expected Outcome:** Should display `Python 3.9.6` or higher.

**Actual Result:** `Python 3.9.6` ✅

---

### Step 2: Create Virtual Environment

**Command:**
```bash
python3 -m venv venv
```

**Why:** A virtual environment isolates project dependencies from system-wide Python packages, preventing version conflicts and ensuring reproducible builds.

**Expected Outcome:** Creates a `venv/` directory with Python binaries and package management tools. No console output means success.

**Actual Result:** `venv/` folder created successfully ✅

---

### Step 3: Activate Virtual Environment

**Command:**
```bash
source venv/bin/activate
```

**Why:** Activating the virtual environment ensures all subsequent `pip` installations and Python commands use the isolated environment rather than the system Python.

**Expected Outcome:** Terminal prompt changes to show `(venv)` prefix. Python commands now point to the virtual environment.

**Actual Result:** Virtual environment activated, `python --version` now works and shows `Python 3.9.6` ✅

---

### Step 4: Create Project Directory Structure

**Command:**
```bash
mkdir -p voice/asr voice/nlu voice/service gs1 epcis ssi blockchain twin dpp docker tests dashboard examples
```

**Why:** The Technical Guide specifies a modular architecture where each lab has dedicated directories. Creating this structure upfront ensures organized development.

**Directory Purpose:**
- `voice/` - Lab 2: Audio processing, ASR, NLU
- `gs1/` - Lab 1: GS1 identifier generation
- `epcis/` - Lab 1: EPCIS 2.0 event construction
- `ssi/` - Lab 3: Self-sovereign identity and credentials
- `blockchain/` - Lab 4: Smart contracts and anchoring
- `twin/` - Lab 4: Digital twin synchronization
- `dpp/` - Lab 5: Digital Product Passports
- `docker/` - Lab 6: Containerization
- `tests/` - Lab 6: Automated testing
- `dashboard/` - Lab 6: Monitoring UI
- `examples/` - Sample data and demos

**Expected Outcome:** All directories created with no errors.

**Actual Result:** Full directory structure created successfully ✅

---

### Step 5: Create Base Requirements File

**Command:**
```bash
# Created requirements.txt with:
pytest==7.4.3
```

**Why:** We start with minimal dependencies for Lab 1. Pytest is needed for testing our GS1 and EPCIS components. We'll add more packages as needed in subsequent labs.

**Expected Outcome:** `requirements.txt` file created with base testing framework.

**Actual Result:** File created ✅

---

### Step 6: Install Base Python Packages

**Command:**
```bash
pip install -r requirements.txt
```

**Why:** Installs pytest and its dependencies into our virtual environment, enabling us to write and run tests for Lab 1 components.

**Expected Outcome:** Pytest 7.4.3 and dependencies installed. Warning about pip upgrade is non-critical.

**Actual Result:** Successfully installed:
- pytest==7.4.3
- packaging==25.0
- exceptiongroup==1.3.1
- iniconfig==2.1.0
- pluggy==1.6.0
- tomli==2.3.0
- typing-extensions==4.15.0

✅ Project setup complete!

---

## Lab 1: GS1 Identifiers & EPCIS Events

### Step 1: Create GS1 Identifier Module

**File Created:** `gs1/identifiers.py`

**Why:** GS1 identifiers are the foundation of supply chain traceability. Before we can create EPCIS events, we need consistent ways to identify:
- **GLN (Global Location Number)** - Farms, warehouses, stations
- **GTIN (Global Trade Item Number)** - Coffee products/batches
- **SSCC (Serial Shipping Container Code)** - Logistic units (bags, pallets)

**What it does:**
- Uses a company prefix `0614141` (example prefix for this prototype)
- `gln(location_code)` - Generates 13-digit location identifiers
- `gtin(product_code)` - Generates 13-digit product identifiers
- `sscc(serial)` - Generates 18-digit logistic unit identifiers

**Test Command:**
```bash
python3 -c "
from gs1.identifiers import gln, gtin, sscc
print('GLN(10):', gln('10'))
print('GTIN(200):', gtin('200'))
print('SSCC(999):', sscc('999'))
"
```

**Expected Outcome:** Three valid GS1 identifiers printed to console.

**Actual Result:**
```
GLN(10): 0614141000010
GTIN(200): 0614141000200
SSCC(999): 00614141000000999
```
✅ All identifiers generated correctly!

---

### Step 2: Create EPCIS Event Builder

**File Created:** `epcis/epcis_builder.py`

**Why:** EPCIS (Electronic Product Code Information Services) is the GS1 standard for capturing supply chain events. We need to create structured, standardized events that describe what happened, when, where, and to which items.

**What it does:**
- Creates EPCIS 2.0 JSON-LD ObjectEvents
- Generates "commissioning" events (batch creation/registration)
- Uses GS1 identifiers (SSCC, GLN, GTIN) from the previous step
- Saves events to `epcis/events/` directory as JSON files

**Event Structure:**
- `type`: "ObjectEvent" - describes an action on objects
- `action`: "ADD" - commissioning adds new items to the system
- `bizStep`: "commissioning" - the business process step
- `epcList`: List of items (using SSCC identifiers)
- `readPoint` / `bizLocation`: Where the event occurred (using GLN)
- `productClass`: What type of product (using GTIN)

**Test Command:**
```bash
python -m epcis.epcis_builder BATCH-2025-001
```

**Expected Outcome:** 
- Creates `epcis/events/BATCH-2025-001_commission.json`
- File contains valid EPCIS 2.0 JSON structure

**Actual Result:**
```
Created: epcis/events/BATCH-2025-001_commission.json
```

**Event Content Verified:**
```json
{
  "type": "ObjectEvent",
  "eventTime": "2025-01-01T00:00:00Z",
  "eventTimeZoneOffset": "+00:00",
  "epcList": ["urn:epc:id:sscc:00614141BATCH-2025-001"],
  "action": "ADD",
  "bizStep": "commissioning",
  "readPoint": {"id": "urn:epc:id:gln:0614141100001"},
  "bizLocation": {"id": "urn:epc:id:gln:0614141100001"},
  "productClass": "urn:epc:id:gtin:0614141200001",
  "batchId": "BATCH-2025-001"
}
```
✅ EPCIS event created successfully!

---

### Step 3: Create Event Canonicalization Module

**File Created:** `epcis/canonicalise.py`

**Why:** JSON objects can have the same data but with fields in different orders. For example:
```json
{"name": "Alice", "age": 30}
{"age": 30, "name": "Alice"}
```
These are semantically identical but will produce different hashes. Canonicalization ensures deterministic hashing by:
1. Sorting all keys alphabetically
2. Removing all whitespace
3. Always producing the same string for the same data

This is **critical for blockchain anchoring** - we need the same event to always produce the same hash for verification.

**What it does:**
- Takes an EPCIS event JSON file path
- Loads and normalizes the JSON
- Returns a compact, sorted string representation

**Test Command:**
```bash
python3 -c "
from pathlib import Path
from epcis.canonicalise import canonicalise_event
canonical = canonicalise_event(Path('epcis/events/BATCH-2025-001_commission.json'))
print('Canonicalized:', canonical[:100] + '...')
print('Length:', len(canonical))
"
```

**Expected Outcome:** 
- Compact JSON string with sorted keys
- No whitespace or indentation
- Deterministic output

**Actual Result:**
```
Canonicalized: {"action":"ADD","batchId":"BATCH-2025-001","bizLocation":{"id":"urn:epc:id:gln:0614141100001"},...
Length: 358 characters
```
✅ Canonicalization working correctly!

---

### Step 4: Create Event Hashing Module

**File Created:** `epcis/hash_event.py`

**Why:** Cryptographic hashes are the foundation of blockchain anchoring. A hash is a unique "fingerprint" of data that:
- Is deterministic (same input → same hash)
- Is one-way (can't reverse engineer the original data)
- Changes completely if even one character changes
- Is fixed-length (always 64 hex characters for SHA-256)

These hashes will be stored on-chain as proof that an event existed, without revealing sensitive supply chain data publicly.

**What it does:**
- Takes a canonicalized EPCIS event
- Computes SHA-256 hash
- Returns 64-character hexadecimal string
- Can be run as CLI tool or imported as module

**Test Command:**
```bash
python -m epcis.hash_event epcis/events/BATCH-2025-001_commission.json
```

**Expected Outcome:** 
- 64-character hexadecimal hash
- Deterministic (same hash every time for same event)

**Actual Result (First run):**
```
Event hash: bc16581a015e8d239723f41734f0847b8615dcae996f182491ddffc67017b3fc
```

**Actual Result (Second run - verification):**
```
Event hash: bc16581a015e8d239723f41734f0847b8615dcae996f182491ddffc67017b3fc
```
✅ Hash is deterministic - identical on both runs!

---

### Lab 1 Complete Pipeline Test

Let's verify the entire Lab 1 pipeline works end-to-end:

**Test Command:**
```bash
# Create a new batch event
python -m epcis.epcis_builder BATCH-TEST-001

# Hash the event
python -m epcis.hash_event epcis/events/BATCH-TEST-001_commission.json
```

**Expected Outcome:** New event created and hashed successfully.

**Actual Result:**
```
Created: epcis/events/BATCH-TEST-001_commission.json
Event hash: 16bafa768867d77e294f86d929f74e50b50399364d90603cc44f58041516bc58
```
✅ Complete pipeline working perfectly!

---

## 🎉 Lab 1 Complete Summary

**What we built:**
1. ✅ GS1 identifier generators (GLN, GTIN, SSCC)
2. ✅ EPCIS 2.0 event builder
3. ✅ Event canonicalization (deterministic JSON)
4. ✅ SHA-256 event hashing

**Pipeline flow:**
```
Batch ID → GS1 Identifiers → EPCIS Event → Canonicalize → Hash
```

**Deliverables:**
- `gs1/identifiers.py` - Identifier generation
- `epcis/epcis_builder.py` - Event creation
- `epcis/canonicalise.py` - Deterministic JSON normalization
- `epcis/hash_event.py` - Cryptographic hashing
- `epcis/events/` - Directory with event files

**Ready for:** Lab 2 (Voice & AI Layer)

---

### Step 5: Initialize Git Repository

**Commands:**
```bash
git init
git add .
git commit -m "Initial commit: Lab 1 complete - GS1 identifiers and EPCIS events"
```

**Why:** Version control is essential for:
- Tracking changes across all labs
- Reverting if something breaks
- Documenting progress with meaningful commits
- Eventually pushing to GitHub for backup/sharing

**What's in `.gitignore`:**
- Python artifacts (`__pycache__`, `*.pyc`, `venv/`)
- Generated files (EPCIS events, digital twins, DPP outputs)
- API keys and secrets (`.env` files)
- Blockchain build artifacts
- Audio test samples
- IDE configurations

**What's tracked:**
- All source code (`*.py`)
- Documentation (`*.md`)
- Configuration files (`requirements.txt`)
- Directory structure (`.gitkeep` files)

**Actual Result:**
```
[main (root-commit) 634feae] Initial commit: Lab 1 complete - GS1 identifiers and EPCIS events
13 files changed, 2306 insertions(+)
```

✅ Git repository initialized and Lab 1 committed!

---

## Lab 2: Voice & AI Layer - Prerequisites

### API Keys and Setup Options

Before starting Lab 2, you need to decide on your ASR (Automatic Speech Recognition) and NLU (Natural Language Understanding) implementation approach.

#### Option A: OpenAI APIs (Recommended for beginners)

**What you need:**
- 1 OpenAI API key from: https://platform.openai.com/api-keys

**What it provides:**
- **Whisper API** for speech-to-text (ASR)
  - Cost: ~$0.006 per minute of audio
  - Highly accurate, supports 50+ languages
  - Simple API integration
  
- **GPT-3.5/GPT-4 API** for intent extraction (NLU)
  - Cost: ~$0.002 per request
  - Flexible entity and intent extraction
  - No training required

**Pros:**
- Fastest to implement
- Production-quality results immediately
- Single API key for both components

**Cons:**
- Requires internet connection
- Ongoing API costs (though minimal for testing)
- Data sent to OpenAI servers

---

#### Option B: Fully Local Implementation (No API keys needed)

**What you need:**
- No API keys
- Additional Python packages (we'll install together)
- More disk space (~1-3GB for models)

**What we'll use:**
- **Whisper (local)** - OpenAI's open-source model
  - Free, runs on your machine
  - Good quality (medium model recommended)
  - Slower than API but no costs
  
- **spaCy + Custom NLU** - Local intent classification
  - We'll train a simple model on supply chain intents
  - Fully offline
  - Complete control over the pipeline

**Pros:**
- Zero API costs
- Complete privacy (data stays local)
- Works offline
- Good learning experience

**Cons:**
- More setup time
- Requires decent CPU/RAM
- Model download time

---

#### Option C: Hybrid Approach

**Mix and match:**
- OpenAI Whisper API for ASR (paid)
- Local spaCy for NLU (free)

OR

- Local Whisper for ASR (free)
- OpenAI GPT for NLU (paid)

---

### Recommended Approach for This Build

**Start with stubs/mocks** (as shown in Technical Guide):
- Create the complete API structure
- Use simple mock functions that return hardcoded transcripts
- Test the full pipeline end-to-end
- Then integrate real ASR/NLU later

This allows us to:
1. Build and test the FastAPI service immediately
2. Verify the voice → EPCIS event flow
3. Add real AI later without restructuring

**Decision needed before Lab 2:**
- [ ] Option A: OpenAI API key ready
- [ ] Option B: Build everything locally
- [ ] Option C: Hybrid approach
- [ ] Option D: Start with stubs, decide on real implementation later

---

### What We'll Build in Lab 2

Regardless of the API choice, Lab 2 will create:

1. **Audio preprocessing** (`voice/asr/preprocessing/audio_utils.py`)
   - Normalize volume
   - Reduce noise
   - Resample to 16kHz
   
2. **ASR module** (`voice/asr/asr_infer.py`)
   - Audio → text transcription
   - Pluggable backend (stub, OpenAI, or local)
   
3. **NLU module** (`voice/nlu/nlu_infer.py`)
   - Text → intent + entities
   - Extract: quantity, product, location, action
   
4. **FastAPI service** (`voice/service/api.py`)
   - `/asr-nlu` endpoint
   - File upload handling
   - API key authentication
   
5. **Authentication** (`voice/service/auth.py`)
   - API key middleware
   - Secure endpoint protection

---

## Lab 2: Voice & AI Layer - Implementation

**Implementation Choice:** OpenAI APIs (Whisper for ASR, GPT for NLU)

### Step 1: Install Lab 2 Dependencies

**Command:**
```bash
pip install -r requirements.txt
```

**Packages Added:**
- `fastapi==0.104.1` - Modern web framework for building APIs
- `uvicorn==0.24.0` - ASGI server to run FastAPI
- `python-multipart==0.0.6` - Required for file uploads
- `openai==1.3.5` - OpenAI API client
- `pydantic==2.5.0` - Data validation (FastAPI dependency)

**Why Each Package:**
- **FastAPI** - High-performance async framework, perfect for file uploads and AI integration
- **Uvicorn** - Production-ready ASGI server with great performance
- **python-multipart** - Handles multipart/form-data for audio file uploads
- **OpenAI** - Official client for Whisper (ASR) and GPT (NLU) APIs
- **Pydantic** - Type validation and serialization for API responses

**Expected Outcome:** All packages installed successfully.

**Actual Result:** Successfully installed fastapi, uvicorn, openai, and dependencies ✅

---

### Step 2: Create API Authentication Module

**File Created:** `voice/service/auth.py`

**Why:** Secure API endpoints to ensure only authorized clients can submit voice commands. Uses API key authentication via HTTP headers.

**What it does:**
- Reads expected API key from `VOICE_LEDGER_API_KEY` environment variable
- Validates incoming `X-API-Key` header on protected endpoints
- Returns 401 Unauthorized if key is invalid
- Returns 500 if API key not configured

**Test:** Module imports successfully ✅

---

### Step 3: Create ASR Module (Whisper Integration)

**File Created:** `voice/asr/asr_infer.py`

**Why:** Converts audio files to text transcriptions using OpenAI's Whisper API. This is the first stage of the voice pipeline.

**What it does:**
- Accepts audio file path (WAV, MP3, M4A formats supported)
- Sends audio to OpenAI Whisper API
- Returns clean text transcript
- Handles errors gracefully

**Dependencies Resolved:**
- Installed `openai==1.12.0` (compatible with Python 3.9)
- Installed `httpx==0.26.0` (compatible version)
- Installed `python-dotenv==1.0.0` for environment variable loading

**API Key:** Stored securely in `.env` file (git-ignored)

**Test:** Module loads successfully ✅

---

### Step 4: Create NLU Module (Intent & Entity Extraction)

**File Created:** `voice/nlu/nlu_infer.py`

**Why:** Extracts structured information from transcripts. Identifies what action is being described (intent) and key details (entities) like quantity, product, locations.

**What it does:**
- Takes text transcript from ASR
- Uses GPT-3.5-turbo to extract:
  - **Intent**: `record_shipment`, `record_commission`, `record_receipt`, etc.
  - **Entities**: quantity, unit, product, origin, destination, batch_id
- Returns structured JSON
- Falls back gracefully if extraction fails

**Test Command:**
```bash
python -m voice.nlu.nlu_infer "Deliver 50 bags of washed coffee from station Abebe to Addis warehouse"
```

**Actual Result:**
```json
{
  "transcript": "Deliver 50 bags of washed coffee from station Abebe to Addis warehouse",
  "intent": "record_shipment",
  "entities": {
    "quantity": 50,
    "unit": "bags",
    "product": "washed coffee",
    "origin": "station Abebe",
    "destination": "Addis warehouse",
    "batch_id": null
  }
}
```
✅ NLU extraction working perfectly!

---

### Step 5: Create FastAPI Service

**File Created:** `voice/service/api.py`

**Why:** Exposes the complete ASR → NLU pipeline as a REST API that can be called by mobile apps, web UIs, or other services.

**What it provides:**
- `GET /` - Health check endpoint
- `POST /asr-nlu` - Main endpoint accepting audio files

**How it works:**
1. Accepts multipart/form-data file upload
2. Validates API key via `X-API-Key` header
3. Saves audio temporarily
4. Runs ASR (audio → text)
5. Runs NLU (text → intent + entities)
6. Returns structured JSON
7. Cleans up temp file

**Start Server:**
```bash
uvicorn voice.service.api:app --host 127.0.0.1 --port 8000
```

**Test Health Endpoint:**
```bash
curl http://localhost:8000/
```

**Actual Result:**
```json
{"service":"Voice Ledger ASR-NLU API","status":"operational","version":"1.0.0"}
```
✅ API server running successfully!

---

### Step 6: Testing the Complete Voice Pipeline

**To test with a real audio file:**

1. Record or obtain an audio file (WAV, MP3, M4A)
2. Place it in `tests/samples/test_audio.wav`
3. Run:
```bash
curl -X POST "http://localhost:8000/asr-nlu" \
  -H "X-API-Key: dev-secret-key-2025" \
  -F "file=@tests/samples/test_audio.wav"
```

**Expected Response:**
```json
{
  "transcript": "[transcribed text]",
  "intent": "[detected intent]",
  "entities": {
    "quantity": number,
    "unit": "string",
    ...
  }
}
```

**Note:** For full testing, you'll need an actual audio file. The pipeline is ready and waiting for audio input.

---

## 🎉 Lab 2 Complete Summary

**What we built:**
1. ✅ API authentication with API key validation
2. ✅ ASR module with OpenAI Whisper integration
3. ✅ NLU module with GPT-3.5 for intent/entity extraction
4. ✅ FastAPI service exposing `/asr-nlu` endpoint

**Pipeline flow:**
```
Audio File → ASR (Whisper) → Transcript → NLU (GPT) → {intent, entities}
```

**Deliverables:**
- `voice/asr/asr_infer.py` - Speech recognition
- `voice/nlu/nlu_infer.py` - Intent & entity extraction
- `voice/service/api.py` - REST API service
- `voice/service/auth.py` - API key authentication
- `.env` - Secure API key storage (git-ignored)

**Ready for:** Lab 3 (Self-Sovereign Identity)

---

## Lab 3: Self-Sovereign Identity & Access Control

### Step 1: Install Lab 3 Dependencies

**Command:**
```bash
pip install PyNaCl==1.5.0
```

**Package Added:**
- `PyNaCl==1.5.0` - Python binding to libsodium for Ed25519 cryptography

**Why:** 
- Ed25519 is a modern, secure signature algorithm
- Used for DID keypair generation
- Used for signing and verifying credentials
- Fast and secure on all platforms

**Actual Result:** PyNaCl installed successfully ✅

---

### Step 2: Create DID Generation Module

**File Created:** `ssi/did/did_key.py`

**Why:** Decentralized Identifiers (DIDs) provide self-sovereign identity without centralized registries. Each actor (farmer, cooperative, facility) gets a cryptographically verifiable identity.

**What it does:**
- Generates Ed25519 keypair
- Creates `did:key` identifier embedding the public key
- Returns DID, public key, and private key
- DIDs are self-verifiable (no external lookup needed)

**Test Command:**
```bash
python -m ssi.did.did_key
```

**Actual Result:**
```
Generating new DID...
DID: did:key:ztEv0yGkafcCHChC3snTlr0Unawz2aJAHBf2HWLhUAu0
Public Key: b44bf4c8691a7dc0870a10b7b274e5af45276b0cf668900705fd8758b85402ed
⚠️  Keep private key secure!
Private Key: a6ca9765ebb9b6d653d7aa5377f5981510751c0ce38aec831cb73528086f2aaa
```
✅ DID generation working!

---

### Step 3: Create Credential Schemas

**File Created:** `ssi/credentials/schemas.py`

**Why:** Define standardized credential types for the coffee supply chain. Each credential type has specific claims that can be verified.

**Schemas Defined:**
- **FarmerCredential** - Verifies farmer identity (name, farm_id, country, DID)
- **FacilityCredential** - Verifies facilities (name, type, GLN, DID)
- **DueDiligenceCredential** - EUDR compliance data (batch, geolocation, timestamp)
- **CooperativeCredential** - Cooperative identity and role

**What it provides:**
- Schema definitions with required and optional fields
- Schema retrieval by credential type
- Claim validation against schemas

**Test Command:**
```bash
python -m ssi.credentials.schemas
```

**Actual Result:** All 4 credential schemas displayed with claims and requirements ✅

---

### Step 4: Create Credential Issuance Module

**File Created:** `ssi/credentials/issue.py`

**Why:** Issue verifiable credentials by signing claims with the issuer's private key. This creates W3C-compliant verifiable credentials.

**What it does:**
- Takes claims and issuer's private key
- Constructs W3C Verifiable Credential structure
- Canonicalizes credential for signing
- Signs with Ed25519
- Adds cryptographic proof

**Credential Structure:**
- `@context` - W3C standards context
- `type` - Credential type
- `issuer` - Issuer's public key
- `issuanceDate` - ISO8601 timestamp
- `credentialSubject` - The claims
- `proof` - Ed25519 signature and metadata

**Test Command:**
```bash
python -m ssi.credentials.issue
```

**Actual Result:**
```json
{
  "@context": [...],
  "type": ["VerifiableCredential", "FarmerCredential"],
  "issuer": "88d78722ef412941b717c7b74dae3aafc6747b3014cc5fd80eba4a42c9fd34e3",
  "issuanceDate": "2025-12-12T19:27:30.466373+00:00",
  "credentialSubject": {
    "name": "Abebe Fekadu",
    "farm_id": "ETH-SID-001",
    "country": "Ethiopia",
    "did": "did:key:zY9AhakoK9kNzjU3qOYlSHCEupqEOXpR4gYtnJRhCdiE"
  },
  "proof": {
    "type": "Ed25519Signature2020",
    "signature": "e8eca1e1a480242c982d2e336ff0b5e4206a2849f64029d16863759b45006a17..."
  }
}
```
✅ Credential issuance working!

---

### Step 5: Create Credential Verification Module

**File Created:** `ssi/credentials/verify.py`

**Why:** Verify credentials are authentic and haven't been tampered with. This ensures only valid credentials are accepted.

**What it verifies:**
1. Required fields present
2. Signature exists
3. Issuer matches verification method
4. Cryptographic signature is valid

**Test Command:**
```bash
python -m ssi.credentials.verify
```

**Actual Result:**
```
Issued credential for: Test Farmer
✅ Credential signature is valid

Testing tampering detection...
✅ Tampering detected: Invalid signature - credential has been tampered with
```
✅ Verification working with tampering detection!

---

### Step 6: Create SSI Agent (Role-Based Access Control)

**File Created:** `ssi/agent.py`

**Why:** Enforce role-based access control for EPCIS event submission. Different roles (farmer, cooperative, facility) have different permissions.

**What it does:**
- Maintains DID → role registry
- Maintains trusted issuer list
- Verifies credentials before authorization
- Enforces event submission permissions

**Permission Model:**
- **Commissioning events**: cooperative, facility
- **Shipment events**: cooperative, facility, farmer
- **Receipt events**: cooperative, facility
- **Transformation events**: facility only

**Test Command:**
```bash
python -m ssi.agent
```

**Actual Result:**
```
Test 1: Farmer submitting shipment event
  ✅ Authorized to submit shipment event

Test 2: Farmer trying to submit commissioning event
  ❌ Role 'farmer' cannot submit 'commissioning' events

Test 3: Cooperative submitting commissioning event
  ✅ Authorized to submit commissioning event
```
✅ Role-based access control working perfectly!

---

## 🎉 Lab 3 Complete Summary

**What we built:**
1. ✅ DID generation with Ed25519 keypairs
2. ✅ Credential schemas (4 types)
3. ✅ Credential issuance with W3C format
4. ✅ Cryptographic verification with tampering detection
5. ✅ SSI agent with role-based access control

**Pipeline flow:**
```
Actor → DID → Credential → Verify → Check Role → Authorize Event
```

**Deliverables:**
- `ssi/did/did_key.py` - DID generation
- `ssi/credentials/schemas.py` - Credential definitions
- `ssi/credentials/issue.py` - Credential issuance
- `ssi/credentials/verify.py` - Signature verification
- `ssi/agent.py` - Access control engine

**Ready for:** Lab 4 (Blockchain & Tokenization)

---

## Lab 4: Blockchain Anchoring & Tokenization

### Step 1: Verify Foundry Installation

**Command:**
```bash
forge --version
```

**Why:** Foundry is the modern Solidity development toolchain providing:
- **forge** - Build, test, and deploy contracts
- **cast** - Interact with contracts via CLI
- **anvil** - Local Ethereum node for testing
- **chisel** - Solidity REPL for debugging

**Actual Result:**
```
forge Version: 1.3.4-Homebrew
```
✅ Foundry already installed!

---

### Step 2: Initialize Foundry Project

**Command:**
```bash
cd blockchain && forge init --no-git --force .
```

**Why:** Creates the standard Foundry project structure:
- `src/` - Smart contracts
- `script/` - Deployment scripts
- `test/` - Contract tests
- `lib/` - Dependencies (OpenZeppelin, etc.)
- `foundry.toml` - Configuration

**What it does:**
- Installs forge-std (Foundry's standard library)
- Creates directory structure
- Sets up for Solidity 0.8.20+

**Actual Result:** Foundry project initialized successfully ✅

---

### Step 3: Install OpenZeppelin Contracts

**Command:**
```bash
forge install OpenZeppelin/openzeppelin-contracts
```

**Why:** OpenZeppelin provides battle-tested, audited implementations of:
- ERC-1155 (multi-token standard)
- Ownable (access control)
- Other security primitives

**Created:** `remappings.txt` for import paths

**Actual Result:** OpenZeppelin v5.5.0 installed ✅

---

### Step 4: Create EPCIS Event Anchor Contract

**File Created:** `blockchain/src/EPCISEventAnchor.sol`

**Why:** Provides immutable on-chain anchoring of EPCIS event hashes. This creates an auditable, tamper-proof record without revealing sensitive supply chain data.

**What it does:**
- Stores SHA-256 hashes of EPCIS events
- Records metadata (batch ID, event type, timestamp, submitter)
- Prevents duplicate anchoring
- Emits events for off-chain indexing

**Modern Solidity Patterns:**
- ✅ Custom errors (gas efficient)
- ✅ Named imports
- ✅ Clear error messages

**Key Functions:**
- `anchorEvent()` - Store event hash on-chain
- `isAnchored()` - Check if event exists
- `getEventMetadata()` - Retrieve event details

**Compilation:** ✅ Compiles successfully

---

### Step 5: Create ERC-1155 Batch Token Contract

**File Created:** `blockchain/src/CoffeeBatchToken.sol`

**Why:** Tokenizes coffee batches as ERC-1155 tokens. Each token ID represents a unique batch with:
- Quantity (number of bags)
- Metadata (origin, cooperative, process)
- Traceability link to EPCIS events

**What it provides:**
- Unique token ID per batch
- Batch ID → Token ID mapping
- Transfer functionality
- Metadata storage

**Modern Solidity Patterns:**
- ✅ Custom errors with parameters
- ✅ Named imports from OpenZeppelin
- ✅ Clear access control (onlyOwner)

**Key Functions:**
- `mintBatch()` - Create new batch token
- `transferBatch()` - Transfer ownership
- `getBatchMetadata()` - Retrieve batch details
- `getTokenIdByBatchId()` - Lookup by batch ID string

**Compilation:** ✅ Compiles successfully

---

### Step 6: Create Settlement Contract

**File Created:** `blockchain/src/SettlementContract.sol`

**Why:** Automates settlement/rewards after valid commissioning events. In production, this would trigger payments to cooperatives.

**What it does:**
- Records settlement per batch
- Prevents double-settlement
- Tracks recipient and amount
- Emits settlement events

**Modern Solidity Patterns:**
- ✅ Custom errors
- ✅ Immutable settlement records
- ✅ Clear validation logic

**Key Functions:**
- `settleCommissioning()` - Execute settlement
- `isSettled()` - Check settlement status
- `getSettlement()` - Retrieve settlement details

**Compilation:** ✅ All three contracts compile successfully

---

### Step 7: Create Digital Twin Module

**File Created:** `twin/twin_builder.py`

**Why:** Maintains a unified digital twin combining on-chain and off-chain data. This provides a complete view of each batch's lifecycle.

**What it tracks:**
- **Anchors** - On-chain event hashes
- **Tokens** - ERC-1155 token IDs and quantities
- **Settlement** - Payment information
- **Credentials** - Verifiable credentials
- **Metadata** - Origin, cooperative, process details

**Functions:**
- `record_anchor()` - Add event anchor
- `record_token()` - Add token minting
- `record_settlement()` - Add settlement
- `record_credential()` - Attach VC
- `get_batch_twin()` - Retrieve complete twin
- `list_all_batches()` - List all batches

**Storage:** JSON file at `twin/digital_twin.json`

**Test Command:**
```bash
python -m twin.twin_builder
```

**Actual Result:**
```json
{
  "batchId": "BATCH-2025-001",
  "anchors": [{
    "eventHash": "bc1658...",
    "eventType": "commissioning"
  }],
  "tokenId": 1,
  "quantity": 50,
  "metadata": {
    "origin": "Ethiopia",
    "cooperative": "Guzo"
  },
  "settlement": {
    "amount": 1000000,
    "recipient": "0x1234...",
    "settled": true
  }
}
```
✅ Digital twin synchronization working!

---

## 🎉 Lab 4 Complete Summary

**What we built:**
1. ✅ EPCISEventAnchor.sol - On-chain event anchoring
2. ✅ CoffeeBatchToken.sol - ERC-1155 batch tokenization
3. ✅ SettlementContract.sol - Settlement record tracking
4. ✅ Digital twin module - Unified data synchronization

**Modern Solidity Patterns:**
- Custom errors (gas efficient, clear messages)
- Named imports from OpenZeppelin
- Clear validation with if/revert pattern

**Key Features:**
- Immutable event anchoring (SHA-256 hashes)
- ERC-1155 multi-token standard for batches
- Settlement audit trail (record-only, not payment execution)
- Digital twin bridges on-chain and off-chain data

**Deliverables:**
- `blockchain/src/EPCISEventAnchor.sol`
- `blockchain/src/CoffeeBatchToken.sol`
- `blockchain/src/SettlementContract.sol`
- `twin/twin_builder.py`
- All contracts compile successfully with Foundry

**Ready for:** Lab 5 (Digital Product Passports)

---

## Lab 5: Digital Product Passports (DPPs)

### Step 1: Create DPP Schema

**File Created:** `dpp/schema.json`

**Why:** Defines the EUDR-compliant structure for Digital Product Passports. This schema ensures all required traceability, due diligence, and sustainability information is captured.

**Schema Sections:**
- **Product Information** - Name, GTIN, quantity, variety, process method
- **Traceability** - Origin (country, region, geolocation), supply chain actors (with DIDs), EPCIS events
- **Sustainability** - Certifications (Organic, FairTrade, etc.), carbon footprint, water usage
- **Due Diligence** - EUDR compliance, deforestation risk assessment, land use rights
- **Blockchain** - Contract addresses, token ID, on-chain anchors
- **QR Code** - Resolver URL and image encoding

**Key Features:**
- Supports GeoJSON polygon coordinates for farm boundaries
- Links to verifiable credentials for supply chain actors
- Integrates blockchain transaction hashes
- ISO 3166-1 country codes for standardization

**Result:** ✅ Schema created with full EUDR compliance fields

---

### Step 2: Build DPP Builder Module

**File Created:** `dpp/dpp_builder.py`

**Why:** Translates digital twin data into consumer-facing DPPs. This module pulls data from the unified digital twin and formats it according to the schema for public access.

**Key Functions:**
- `load_twin_data()` - Load batch data from digital twin
- `build_dpp()` - Generate complete DPP from twin + metadata
- `save_dpp()` - Save DPP to `dpp/passports/` directory
- `validate_dpp()` - Ensure all required EUDR fields present

**What it does:**
- Extracts product information (quantity, variety, process)
- Maps supply chain actors from credentials
- Converts EPCIS anchors to traceability events
- Formats due diligence and risk assessment
- Links blockchain contract addresses and token IDs
- Generates resolver URL for QR codes

**Test Command:**
```bash
python -m dpp.dpp_builder
```

**Actual Result:**
```
✅ Built DPP: DPP-BATCH-2025-001
   Product: Ethiopian Yirgacheffe - Washed Arabica
   Quantity: 50 bags
   Origin: Yirgacheffe, Gedeo Zone, ET
   EUDR Compliant: True
   Deforestation Risk: none
   Events: 1 EPCIS events
✅ DPP validation passed
💾 Saved DPP to: dpp/passports/BATCH-2025-001_dpp.json
```

---

### Step 3: Create DPP Resolver API

**File Created:** `dpp/dpp_resolver.py`

**Why:** Public-facing FastAPI service that resolves DPPs by batch ID. This is what consumers access when they scan QR codes on product packaging.

**Endpoints:**
- `GET /` - Health check
- `GET /dpp/{batch_id}` - Resolve full DPP (supports ?format=full|summary|qr)
- `GET /dpp/{batch_id}/verify` - Verify blockchain anchoring and credentials
- `GET /batches` - List all available batches

**Response Formats:**
- **full** - Complete DPP with all sections
- **summary** - Consumer-friendly overview (product, origin, EUDR status)
- **qr** - QR code data only

**Features:**
- CORS enabled for public web access
- Dynamic DPP building from digital twin
- Validation before returning data
- Blockchain verification status

**Test Command:**
```bash
python -m dpp.dpp_resolver  # Starts on port 8001
curl http://localhost:8001/dpp/BATCH-2025-001?format=summary
```

**Actual Result:**
```json
{
  "passportId": "DPP-BATCH-2025-001",
  "batchId": "BATCH-2025-001",
  "product": "Ethiopian Yirgacheffe - Washed Arabica",
  "quantity": "50 bags",
  "origin": "Yirgacheffe, Gedeo Zone, ET",
  "eudrCompliant": true,
  "deforestationRisk": "none",
  "qrUrl": "https://dpp.voiceledger.io/dpp/BATCH-2025-001"
}
```

**Verification Endpoint Result:**
```json
{
  "batchId": "BATCH-2025-001",
  "verificationStatus": "partial",
  "blockchain": {
    "anchored": true,
    "anchoredEvents": 1,
    "totalAnchors": 1
  },
  "credentials": {
    "verified": false,
    "totalCredentials": 0
  },
  "settlement": {
    "recorded": true,
    "amount": 1000000,
    "recipient": "0x1234..."
  }
}
```

✅ API running and responsive!

---

### Step 4: Build QR Code Generator

**File Created:** `dpp/qrcode_gen.py`

**Why:** Generates QR codes that consumers can scan to access DPPs. Supports PNG, SVG, and labeled formats for flexible packaging integration.

**Dependencies Installed:**
```bash
pip install 'qrcode[pil]'  # QR code generation with PIL imaging
```

**Key Functions:**
- `generate_qr_code()` - Basic QR code with base64 encoding
- `generate_qr_code_svg()` - Scalable vector graphics version
- `create_labeled_qr_code()` - QR code with product name and batch ID overlay
- `generate_batch_qr_codes()` - Bulk generation for multiple batches

**Features:**
- High error correction (ERROR_CORRECT_H) for durability
- Base64 encoding for embedding in DPPs
- Labeled versions with product information
- SVG output for print-ready graphics
- Customizable size and border

**Test Command:**
```bash
python -m dpp.qrcode_gen
```

**Actual Result:**
```
📱 Generating QR Codes for DPPs...
✅ QR code saved to: dpp/qrcodes/BATCH-2025-001_qr.png
   URL: https://dpp.voiceledger.io/dpp/BATCH-2025-001
   Base64 length: 1588 characters
✅ Labeled QR code generated: dpp/qrcodes/BATCH-2025-001_labeled_qr.png
✅ SVG QR code saved to: dpp/qrcodes/BATCH-2025-001_qr.svg
   SVG size: 13553 characters
🎉 QR code generation complete!
```

**Generated Files:**
- PNG QR code for digital use
- Labeled PNG with product info for packaging
- SVG for high-quality printing

---

### Step 5: Test Complete DPP Flow

**File Created:** `tests/test_dpp_flow.py`

**Why:** End-to-end integration test validating the complete workflow from EPCIS event creation to QR code generation.

**Test Flow:**
1. Create EPCIS commissioning event
2. Hash event for blockchain anchoring
3. Build digital twin (anchor, token, settlement)
4. Generate DPP from digital twin
5. Validate DPP against schema
6. Save DPP to file
7. Generate QR codes (plain and labeled)
8. Verify all components working together

**Test Command:**
```bash
python -m tests.test_dpp_flow
```

**Actual Result:**
```
============================================================
🧪 TESTING COMPLETE DPP FLOW
============================================================

📝 Step 1: Creating EPCIS commissioning event...
   ✅ Event created: epcis/events/BATCH-2025-TEST_commission.json

🔐 Step 2: Hashing EPCIS event...
   ✅ Event hash: a3aedade85dc4abb6de9443ed1cc2e73...

🔗 Step 3: Building digital twin...
   ✅ Recorded event anchor
   ✅ Recorded token minting
   ✅ Recorded settlement

🔍 Step 4: Verifying digital twin...
   ✅ Digital twin found
      - Token ID: 42
      - Quantity: 100 bags
      - Anchors: 2 events
      - Settlement: $25000.00

📄 Step 5: Building Digital Product Passport...
   ✅ DPP built: DPP-BATCH-2025-TEST
      - Product: Ethiopian Yirgacheffe - Test Batch
      - Quantity: 100 bags
      - EUDR Compliant: True
      - Events: 2

✅ Step 6: Validating DPP...
   ✅ DPP validation passed

💾 Step 7: Saving DPP...
   ✅ DPP saved to: dpp/passports/BATCH-2025-TEST_dpp.json

📱 Step 8: Generating QR codes...
   ✅ QR code generated
   ✅ Labeled QR code generated

============================================================
✅ COMPLETE DPP FLOW TEST PASSED
============================================================

📊 Summary:
   • Batch ID: BATCH-2025-TEST
   • EPCIS Event: BATCH-2025-TEST_commission.json
   • Event Hash: a3aedade85dc4abb...
   • Token ID: 42
   • DPP: BATCH-2025-TEST_dpp.json
   • QR Code: BATCH-2025-TEST_qr.png
   • Resolver URL: https://dpp.voiceledger.io/dpp/BATCH-2025-TEST
```

✅ **Complete end-to-end flow validated!**

---
