"""
Voice Ledger ASR-NLU API Service

This FastAPI service provides a secure endpoint for voice-to-structured-data conversion.
It accepts audio files, transcribes them, and extracts supply chain intents and entities.
"""

from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from voice.asr.asr_infer import run_asr
from voice.nlu.nlu_infer import infer_nlu_json
from voice.service.auth import verify_api_key

app = FastAPI(
    title="Voice Ledger ASR–NLU API",
    description="Convert voice commands to structured supply chain events",
    version="1.0.0"
)

# Allow local tools and UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Voice Ledger ASR-NLU API",
        "status": "operational",
        "version": "1.0.0"
    }


@app.post("/asr-nlu")
async def asr_nlu_endpoint(
    file: UploadFile = File(...),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Accept an audio file, run ASR + NLU, and return structured JSON.
    
    Args:
        file: Audio file (WAV, MP3, M4A, etc.)
        
    Returns:
        {
            "transcript": str,
            "intent": str,
            "entities": dict
        }
        
    Requires:
        X-API-Key header with valid API key
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Create temp directory for uploads
    temp_dir = Path("tests/samples")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        # Save incoming file
        with temp_path.open("wb") as f:
            content = await file.read()
            f.write(content)

        # Run ASR (audio → text)
        transcript = run_asr(str(temp_path))
        
        # Run NLU (text → intent + entities)
        result = infer_nlu_json(transcript)
        
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
