"""
Voice API Integration Tests

Tests the complete voice-to-structured-data pipeline.
"""

import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Import the FastAPI app
from voice.service.api import app
from voice.service.auth import get_expected_api_key


# Create test client
client = TestClient(app)

# Set test API key
os.environ["VOICE_LEDGER_API_KEY"] = "test-api-key-12345"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ["healthy", "operational"]
    assert "voice" in data["service"].lower()


def test_missing_api_key():
    """Test that requests without API key are rejected"""
    response = client.post("/asr-nlu")
    assert response.status_code in [401, 403]


def test_invalid_api_key():
    """Test that requests with invalid API key are rejected"""
    headers = {"X-API-Key": "wrong-key"}
    response = client.post("/asr-nlu", headers=headers)
    assert response.status_code in [401, 403]


def test_missing_file():
    """Test that requests without audio file are rejected"""
    headers = {"X-API-Key": "test-api-key-12345"}
    response = client.post("/asr-nlu", headers=headers)
    assert response.status_code == 422  # FastAPI validation error


@pytest.mark.skip(reason="Requires OpenAI API key and audio file")
def test_asr_nlu_pipeline():
    """
    Test complete ASR + NLU pipeline.
    
    Skipped by default because it requires:
    - Valid OpenAI API key
    - Audio file for upload
    """
    headers = {"X-API-Key": "test-api-key-12345"}
    
    # This would need a real audio file
    audio_file_path = Path(__file__).parent / "fixtures" / "test_audio.wav"
    
    if not audio_file_path.exists():
        pytest.skip("Test audio file not found")
    
    with open(audio_file_path, "rb") as f:
        files = {"file": ("test_audio.wav", f, "audio/wav")}
        response = client.post("/asr-nlu", headers=headers, files=files)
    
    assert response.status_code == 200
    
    data = response.json()
    assert "transcript" in data
    assert "intent" in data
    assert "entities" in data


def test_nlu_extract_entities():
    """Test NLU entity extraction logic (unit test)"""
    from voice.nlu.nlu_infer import infer_nlu_json
    
    # Test commissioning intent
    transcript = "Commission 50 bags of washed coffee from cooperative Guzo"
    result = infer_nlu_json(transcript)
    
    assert result["transcript"] == transcript
    assert "commission" in result.get("intent", "").lower()
    assert "entities" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
