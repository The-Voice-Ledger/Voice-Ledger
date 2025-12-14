# Voice Ledger - Lab 7: Voice Interface Integration

**Branch:** `feature/voice-interface`  
**Start Date:** December 14, 2025  
**Implementation Reference:** [VOICE_INTERFACE_IMPLEMENTATION_PLAN.md](documentation/VOICE_INTERFACE_IMPLEMENTATION_PLAN.md)

This lab document tracks every step to add voice input capability to Voice Ledger, transforming it from a backend-only system to a true voice-enabled traceability platform.

---

## 🎯 Lab Overview

**Goal:** Integrate voice input capability into Voice Ledger through 4 progressive phases:
- **Phase 1 (1-2 days):** Basic voice API with file upload
- **Phase 2 (2-3 days):** Production-ready async processing
- **Phase 3 (1 week):** IVR/phone system integration
- **Phase 4 (2-3 weeks):** Offline-first edge deployment

**The Problem We're Solving:**
Voice Ledger v1.0 has a complete backend (EPCIS, blockchain, IPFS, DPP, SSI) but **zero voice input capability**. The system is called "Voice Ledger" but farmers cannot actually use their voice to record events. This lab closes that gap.

**Why This Matters:**
- **Accessibility:** Many smallholder farmers have limited literacy but can speak
- **Speed:** Voice input is 3x faster than manual data entry
- **Accuracy:** Spoken information reduces transcription errors
- **Offline:** Voice can work in low-connectivity areas (Phase 4)
- **Scale:** Phone systems reach farmers without smartphones (Phase 3)

---

## 📋 Prerequisites - What We Have (v1.0)

**Completed from Previous Labs:**
- ✅ Lab 1: GS1 identifiers (GLN, GTIN, SSCC) and EPCIS 2.0 events
- ✅ Lab 2: Voice AI modules (ASR with Whisper, NLU with GPT-3.5) - **NOT INTEGRATED**
- ✅ Lab 3: Self-Sovereign Identity (DIDs, Verifiable Credentials)
- ✅ Lab 4: Blockchain anchoring (Foundry, ERC-1155 tokens, Polygon)
- ✅ Lab 4.5: Production database (Neon PostgreSQL, SQLAlchemy ORM)
- ✅ Lab 4.6: IPFS storage (Pinata integration)
- ✅ Lab 5: Digital Product Passports (DPP builder/resolver)
- ✅ Lab 6: Dashboard (Streamlit monitoring UI)

**Current System State:**
```bash
# Database: 21 farmers, 28 batches, 16 events
# Dashboard: Running at http://localhost:8501
# Blockchain: Anvil local node with deployed contracts
# IPFS: Pinata with working CIDs
# API: 5 REST endpoints (farmers, batches, events, credentials, DPPs)
```

**Existing Voice Components (Not Integrated):**
```
voice/
├── asr/
│   └── asr_infer.py          # OpenAI Whisper API (works standalone)
├── nlu/
│   └── nlu_infer.py          # GPT-3.5 intent extraction (works standalone)
└── service/
    └── api.py                # Empty FastAPI stub (not implemented)
```

**Already Installed:**
```
openai==1.12.0                # Whisper + GPT-3.5 API access
fastapi==0.104.1              # Web framework
uvicorn==0.24.0               # ASGI server
python-multipart==0.0.6       # File upload support
```

**The Gap - No Voice Integration:**
- ❌ No `/voice/transcribe` API endpoint
- ❌ No `/voice/process-command` API endpoint
- ❌ No audio file upload/validation
- ❌ No integration with existing ASR/NLU modules
- ❌ No audio format conversion (WAV/MP3/M4A)
- ❌ No async processing for long transcriptions
- ❌ No IVR/phone system
- ❌ No offline voice processing

**What We'll Install:**
```bash
# Phase 1 (Core):
pydub                         # Audio format conversion
soundfile                     # Audio I/O
aiofiles                      # Async file operations
ffmpeg (system)               # Audio processing backend

# Phase 2 (Production):
celery                        # Async task queue
redis                         # Message broker

# Phase 3 (IVR):
twilio                        # Phone system API

# Phase 4 (Offline):
openai-whisper                # Local Whisper models
torch                         # PyTorch runtime
torchaudio                    # Audio preprocessing
```

---

## Phase 1: Minimal Voice API (Days 1-2)

**Goal:** Add basic voice input via file upload - transform Voice Ledger from backend-only to voice-capable.

**Architecture:**
```
User → Upload Audio (WAV/MP3/M4A) 
  → API validates format
  → Convert to WAV 
  → OpenAI Whisper ASR 
  → Transcription → GPT-3.5 NLU 
  → Intent + Entities 
  → Execute Database Operation 
  → Return JSON Response
```

---

### Step 1: Branch Setup

**Command:**
```bash
cd /Users/manu/Voice-Ledger
git checkout -b feature/voice-interface
```

**Why:** Creating a feature branch isolates voice interface development from the stable v1.0 main branch. Allows experimentation without risk to production code.

**Expected Outcome:** New branch created, working tree clean from previous commits.

**Actual Result:**
```
Switched to a new branch 'feature/voice-interface'
```
✅ Branch created successfully

**Verification:**
```bash
git branch
# * feature/voice-interface
#   main

git status
# On branch feature/voice-interface
# nothing to commit, working tree clean
```

---

### Step 2: Install Core Audio Processing Packages

**Command:**
```bash
pip install pydub soundfile aiofiles
```

**Why Each Package:**
- **pydub** - High-level audio manipulation library. Converts between formats (MP3→WAV, M4A→WAV) and handles audio slicing, concatenation, effects. Requires ffmpeg backend.
- **soundfile** - Low-level audio I/O. Reads/writes WAV files with numpy arrays. Fast and memory-efficient for audio processing pipelines.
- **aiofiles** - Async file operations. Prevents blocking when reading large audio files (5-10 MB). Critical for production async API.

**Expected Outcome:**
```
Successfully installed:
- pydub-0.25.1
- soundfile-0.12.1
- aiofiles-23.2.1
```

**Actual Result:**
```
Successfully installed aiofiles-23.2.1 pydub-0.25.1 soundfile-0.12.1
```
✅ All Python audio packages installed successfully

---

### Step 3: Install FFmpeg (System Dependency)

**Command:**
```bash
brew install ffmpeg
```

**Why:** FFmpeg is the audio/video processing powerhouse that pydub uses as a backend. Handles codec conversion, resampling, bitrate adjustment. Without ffmpeg, pydub cannot convert MP3/M4A files.

**Background - What is FFmpeg:**
FFmpeg is an industry-standard multimedia framework used by:
- YouTube (video transcoding)
- Spotify (audio format conversion)
- Netflix (adaptive streaming)
- Discord (voice chat processing)

It supports 100+ codecs and can handle virtually any audio/video format.

**Expected Outcome:**
```
🍺  /opt/homebrew/Cellar/ffmpeg/8.0: 285 files, 55MB
```

**Actual Result:**
```
🍺  /opt/homebrew/Cellar/ffmpeg/8.0.1: 285 files, 55.4MB
```
✅ FFmpeg 8.0.1 installed with 90 dependencies (aom, x264, x265, libvpx, etc.)

**Verification:**
```bash
ffmpeg -version
# ffmpeg version 8.0.1 Copyright (c) 2000-2025 the FFmpeg developers
```
✅ FFmpeg operational

---

### Step 4: Update requirements.txt

**File Modified:** `requirements.txt`

**Why:** Document all installed packages for reproducibility. Other developers can run `pip install -r requirements.txt` to get exact same environment.

**Added Lines:**
```txt
# -----------------------------
# Lab 7: Voice Interface Integration (Audio Processing)
# -----------------------------
pydub==0.25.1       # Audio format conversion (MP3/M4A → WAV)
soundfile==0.12.1   # Audio I/O with numpy arrays
aiofiles==23.2.1    # Async file operations
```

**Verification:**
```bash
pip freeze | grep -E "(pydub|soundfile|aiofiles)"
```

**Expected Outcome:**
```
aiofiles==23.2.1
pydub==0.25.1
soundfile==0.12.1
```

✅ requirements.txt updated, packages documented

---

### Step 5: Examine Existing Voice Modules

**Command:**
```bash
# Check what's in the existing ASR module
cat voice/asr/asr_infer.py | head -50

# Check what's in the existing NLU module  
cat voice/nlu/nlu_infer.py | head -50

# Check current voice API stub
cat voice/service/api.py
```

**Why:** Before implementing new endpoints, we need to understand:
1. What functions already exist (ASR transcription, NLU extraction)
2. What parameters they expect
3. What data structures they return
4. If they need modification for integration

**Expected Findings:**
- `asr_infer.py` should have `transcribe_audio()` function using OpenAI Whisper
- `nlu_infer.py` should have `extract_intent_entities()` function using GPT-3.5
- `api.py` should be mostly empty or have basic FastAPI setup

**Actual Result - ASR Module (`voice/asr/asr_infer.py`):**
```python
def run_asr(audio_file_path: str) -> str:
    """Transcribe audio file to text using OpenAI Whisper API."""
    # Opens audio file, calls client.audio.transcriptions.create()
    # Returns: Plain text transcription
```
✅ **Status:** Complete and working standalone
- Uses OpenAI Whisper API (model: `whisper-1`)
- Accepts: WAV, MP3, M4A (any format OpenAI supports)
- Returns: Plain text string
- Error handling: FileNotFoundError, API exceptions

**Actual Result - NLU Module (`voice/nlu/nlu_infer.py`):**
```python
def infer_nlu_json(transcript: str) -> dict:
    """Extract intent and entities from transcript using GPT-3.5."""
    # Uses GPT-3.5-turbo with system prompt for supply chain commands
    # Returns: {"transcript": str, "intent": str, "entities": dict}
```
✅ **Status:** Complete and working standalone
- Uses GPT-3.5-turbo for intent/entity extraction
- System prompt: Extracts supply chain actions (record_shipment, record_commission, etc.)
- Returns: Structured JSON with intent + entities
- Intents: `record_shipment`, `record_commission`, `record_receipt`, `record_transformation`

**Actual Result - API Service (`voice/service/api.py`):**
```python
@app.post("/asr-nlu")
async def asr_nlu_endpoint(file: UploadFile, _: bool = Depends(verify_api_key)):
    """Accept audio file, run ASR + NLU, return structured JSON."""
    # 1. Saves uploaded file to temp directory
    # 2. Calls run_asr() to transcribe
    # 3. Calls infer_nlu_json() to extract intent/entities
    # 4. Cleans up temp file
    # 5. Returns result
```
✅ **Status:** Complete but basic implementation
- Endpoint: `POST /asr-nlu` (combines transcription + NLU)
- Authentication: Requires X-API-Key header via `verify_api_key` dependency
- Temp storage: Saves to `tests/samples/` directory
- Cleanup: Deletes temp file after processing
- Missing: No audio format conversion, no async processing, no validation

**Key Finding:**
The voice API is **80% complete** but not integrated with the rest of Voice Ledger:
- ✅ ASR works (Whisper API)
- ✅ NLU works (GPT-3.5 intent extraction)
- ✅ Combined endpoint exists (`/asr-nlu`)
- ❌ No audio format validation
- ❌ No connection to database (doesn't create batches/events)
- ❌ No `/voice/transcribe` endpoint (transcription only)
- ❌ No `/voice/process-command` endpoint (full workflow)
- ❌ Doesn't use pydub for format conversion
- ❌ No integration with existing CRUD operations

---

### Step 6: Design Voice API Architecture

**Decision:** Build on existing `/asr-nlu` endpoint vs. starting fresh

**Analysis:**
Current `/asr-nlu` endpoint is good but needs enhancements:
1. **Format conversion:** Add pydub to handle MP3/M4A → WAV
2. **Database integration:** Connect NLU output to CRUD operations
3. **Separate endpoints:** Create `/voice/transcribe` (ASR only) and `/voice/process-command` (full workflow)
4. **Validation:** Check audio format, duration, file size
5. **Better temp handling:** Use aiofiles for async file operations

**New Architecture:**
```
POST /voice/transcribe
├─ Upload audio file (any format)
├─ Convert to WAV if needed (pydub)
├─ Call OpenAI Whisper
└─ Return: {"transcript": "text"}

POST /voice/process-command
├─ Upload audio file
├─ Convert to WAV if needed
├─ Call ASR (transcription)
├─ Call NLU (intent + entities)
├─ Execute database operation based on intent:
│  ├─ record_shipment → create_epcis_event()
│  ├─ record_commission → create_batch()
│  ├─ record_receipt → create_epcis_event()
│  └─ record_transformation → create_epcis_event()
└─ Return: {"transcript": str, "intent": str, "entities": dict, "result": db_object}

GET /voice/health
└─ Check OpenAI API key, ffmpeg availability, database connection
```

**Implementation Plan:**
1. Keep existing `/asr-nlu` endpoint (for backward compatibility)
2. Add `/voice/transcribe` endpoint (transcription only, simpler use case)
3. Add `/voice/process-command` endpoint (full workflow with database)
4. Add audio validation utilities
5. Add audio format conversion with pydub
6. Integrate with existing database CRUD operations

---

### Step 7: Create Audio Utilities Module

**File Created:** `voice/audio_utils.py`

**Why:** Centralize audio processing logic for:
- Format validation (check if file is audio)
- Format conversion (MP3/M4A → WAV using pydub)
- Audio metadata extraction (duration, sample rate, channels)
- File size limits (prevent DoS attacks)
- Temp file management with async operations

**Background - Audio Format Considerations:**

**Why Convert to WAV?**
- WAV is uncompressed, lossless format
- OpenAI Whisper API accepts WAV natively
- Eliminates codec compatibility issues
- Consistent processing pipeline

**Format Support:**
- MP3: Most common, lossy compression (~10:1)
- M4A/AAC: Apple format, lossy compression (~12:1)
- WAV: Uncompressed, large files but no quality loss
- FLAC: Lossless compression (~2:1), supported by ffmpeg

**File Size Limits:**
- Max file size: 25 MB (OpenAI Whisper API limit)
- Max duration: 10 minutes (prevents abuse)
- Typical sizes: 1 min voice @ 128kbps MP3 ≈ 1 MB

**Implementation:**

```python
# voice/audio_utils.py - 312 lines

class AudioValidationError(Exception):
    """Raised when audio file validation fails."""
    pass

def validate_audio_file(file_path: str, max_size_mb: int = 25) -> None:
    """Validate file exists, has correct extension, size within limits."""
    # Checks: file exists, supported format, size <= max_size_mb
    
def get_audio_duration(file_path: str) -> float:
    """Get duration of audio file in seconds using pydub."""
    
def get_audio_metadata(file_path: str) -> dict:
    """Extract duration, sample_rate, channels, format, file_size_mb."""
    
def convert_to_wav(input_path: str, output_path: Optional[str] = None) -> str:
    """Convert any audio format to WAV using pydub + ffmpeg."""
    # If already WAV, returns original path
    # Otherwise creates temp WAV file
    
def validate_and_convert_audio(
    input_path: str,
    max_size_mb: int = 25,
    max_duration_seconds: int = 600
) -> Tuple[str, dict]:
    """Main function: validate + convert to WAV in one call."""
    # Returns: (wav_path, metadata)
    
def cleanup_temp_file(file_path: str) -> None:
    """Safely delete temporary file."""
```

**Key Design Decisions:**

1. **Constraint Constants:**
   - `MAX_FILE_SIZE_MB = 25` - OpenAI Whisper API limit
   - `MAX_DURATION_SECONDS = 600` - Prevents abuse (10 min max)
   - `SUPPORTED_FORMATS` - 7 common audio formats

2. **Why Separate Functions:**
   - `validate_audio_file()` - Quick check before expensive operations
   - `get_audio_metadata()` - Useful for logging/analytics
   - `convert_to_wav()` - Can be used standalone
   - `validate_and_convert_audio()` - Convenience wrapper for API

3. **Error Handling:**
   - Custom `AudioValidationError` for clear error messages
   - Specific errors: file not found, unsupported format, too large, too long
   - Silent cleanup (temp file deletion doesn't crash if it fails)

4. **Temp File Strategy:**
   - Uses `tempfile.mkstemp()` for secure temp file creation
   - Prefix: `voice_` for easy identification in /tmp
   - Auto-cleanup after processing

**Testing:**
```bash
# Generate 3-second test tone (440 Hz A note)
python3 -c "
from pydub.generators import Sine
tone = Sine(440).to_audio_segment(duration=3000)
tone.export('tests/samples/test_audio.wav', format='wav')
"

# Test audio utilities
python -m voice.audio_utils tests/samples/test_audio.wav
```

**Actual Result:**
```
Testing audio utilities with: tests/samples/test_audio.wav

1. Validating audio file...
   ✓ File is valid

2. Extracting metadata...
   Duration: 3.00s
   Sample rate: 44100 Hz
   Channels: 1
   Format: wav
   File size: 0.25 MB

3. Converting to WAV...
   ✓ Converted to: tests/samples/test_audio.wav
   ✓ Duration check: 3.00s

✅ All tests passed!
```

✅ Audio utilities module complete and tested

---

### Step 8: Implement Enhanced Voice API Endpoints

**File Modified:** `voice/service/api.py`

**Why:** Transform the basic ASR-NLU API into a comprehensive voice interface with:
1. **Separate concerns:** Transcription-only vs. full command processing
2. **Audio validation:** Use new audio_utils module for format conversion
3. **Database integration:** Connect NLU output to actual database operations
4. **Health monitoring:** Endpoint to check service dependencies
5. **Response models:** Pydantic models for type safety and API docs

**Architecture Changes:**

**Before (v1.0):**
```
POST /asr-nlu
  └─ Save file → ASR → NLU → Return JSON
  
GET /
  └─ Simple health check
```

**After (v2.0):**
```
GET /
  └─ Root with endpoint list

GET /voice/health
  └─ Check: OpenAI API, Database, FFmpeg

POST /voice/transcribe
  └─ Validate → Convert → ASR → Return transcript + metadata

POST /voice/process-command
  └─ Validate → Convert → ASR → NLU → Database Operation → Return full result

POST /asr-nlu (legacy)
  └─ Keep for backward compatibility
```

**New Response Models:**
```python
class TranscriptionResponse(BaseModel):
    transcript: str
    audio_metadata: dict

class NLUResponse(BaseModel):
    transcript: str
    intent: str
    entities: dict
    audio_metadata: Optional[dict] = None

class CommandResponse(BaseModel):
    transcript: str
    intent: str
    entities: dict
    result: Optional[dict] = None  # Database object created
    error: Optional[str] = None
    audio_metadata: dict

class HealthResponse(BaseModel):
    service: str
    status: str
    version: str
    openai_api_configured: bool
    database_available: bool
    ffmpeg_available: bool
```

**Key Implementation Details:**

1. **Audio Processing Pipeline:**
   ```python
   # Upload → Validate → Convert → Process → Cleanup
   
   temp_path = save_upload(file)
   wav_path, metadata = validate_and_convert_audio(temp_path)
   transcript = run_asr(wav_path)
   cleanup_temp_file(temp_path)
   cleanup_temp_file(wav_path)
   ```

2. **Error Handling:**
   - `AudioValidationError` → HTTP 400 (Bad Request)
   - `FileNotFoundError` → HTTP 404 (Not Found)
   - Generic exceptions → HTTP 500 (Internal Server Error)
   - Database unavailable → HTTP 503 (Service Unavailable)

3. **Database Integration (Placeholder):**
   ```python
   if DATABASE_AVAILABLE:
       if intent == "record_shipment":
           # TODO: create_epcis_event(entities)
       elif intent == "record_commission":
           # TODO: create_batch(entities)
   ```
   *Note: Full integration requires session management - deferred to testing phase*

4. **Temp File Management:**
   - Uploads: `tests/samples/temp/` directory
   - WAV conversions: System temp directory (auto-cleanup)
   - Cleanup in `finally` block ensures no file leaks

**Code Statistics:**
- Lines added: ~250
- New endpoints: 3 (health, transcribe, process-command)
- Response models: 4
- Error handling: 4 exception types
- Cleanup logic: Guaranteed via finally blocks

---

---

## Notes and Decisions

### Architecture Decisions
- **Audio Format Strategy:** Accept multiple formats (WAV, MP3, M4A), convert to WAV for processing
- **Transcription Service:** Start with OpenAI Whisper API (already integrated), add local models in Phase 4
- **NLU Approach:** Use existing GPT-3.5 integration, optimize prompts for voice commands
- **API Design:** RESTful with async/await pattern, job-based for long operations

### Cost Considerations
- **OpenAI Whisper API:** $0.006/minute (cheap for prototyping)
- **Twilio:** ~$1/month/number + $0.0085/minute (affordable for IVR)
- **Local Whisper:** One-time setup cost, zero ongoing cost per transcription

### Risk Mitigation
- Phase 1 provides immediate value without complex infrastructure
- Each phase is independently deployable
- OpenAI API fallback if local models underperform
- Offline queue prevents data loss in low connectivity

---

## Testing Checklist

### Phase 1 Testing
- [ ] Upload 5-second audio file (English)
- [ ] Upload 30-second audio file
- [ ] Test with different formats (WAV, MP3, M4A)
- [ ] Test with background noise
- [ ] Test with poor audio quality
- [ ] Verify intent extraction accuracy
- [ ] Verify entity extraction (farmer names, quantities, etc.)
- [ ] Test error handling (corrupt files, unsupported formats)

### Phase 2 Testing
- [ ] 100 concurrent uploads
- [ ] Job status tracking
- [ ] Webhook delivery
- [ ] Rate limiting triggers
- [ ] Authentication/authorization
- [ ] Error recovery and retries

### Phase 3 Testing
- [ ] Inbound call handling
- [ ] Real-time transcription latency
- [ ] Multi-turn conversations
- [ ] SMS fallback delivery
- [ ] Call quality in different regions

### Phase 4 Testing
- [ ] Offline operation (airplane mode)
- [ ] Sync after reconnection
- [ ] Conflict resolution
- [ ] Edge device performance
- [ ] Battery life impact
- [ ] Storage capacity limits

---

## Resources

### Documentation
- [Voice Interface Implementation Plan](documentation/VOICE_INTERFACE_IMPLEMENTATION_PLAN.md) - Complete 4-phase guide with code examples
- [V2 Aggregation Roadmap](documentation/V2_AGGREGATION_IMPLEMENTATION_ROADMAP.md) - Future aggregation support
- [LinkedIn Article](documentation/LINKEDIN_ARTICLE_VOICE_LEDGER.md) - System overview and traceability explanation

### API Endpoints (Current)
- `POST /farmers/` - Register farmer with DID
- `POST /batches/` - Create coffee batch with IPFS storage
- `POST /events/` - Record EPCIS event
- `GET /dpp/{batch_id}` - Retrieve Digital Product Passport
- `POST /credentials/issue` - Issue Verifiable Credential

### Voice Endpoints (To Be Implemented)
- `POST /voice/transcribe` - Transcribe audio to text
- `POST /voice/process-command` - Full voice command processing
- `GET /voice/job/{job_id}` - Check async job status
- `POST /voice/webhook` - Twilio IVR webhook (Phase 3)

---

## Progress Metrics

**Current Status:** Phase 1 - Setup  
**Time Invested:** 0 hours  
**Lines of Code Added:** 0  
**Tests Passing:** 0/8 (Phase 1)  
**API Endpoints Implemented:** 0/2  
**Packages Installed:** 0/4

**Target Completion:**
- Phase 1: December 16, 2025
- Phase 2: December 19, 2025
- Phase 3: December 26, 2025
- Phase 4: January 16, 2026

---

## Blockers and Issues

*No blockers yet*

---

## Questions and Clarifications

*To be added as questions arise*
