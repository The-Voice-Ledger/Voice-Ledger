"""
Automatic Speech Recognition (ASR) Module

This module handles audio-to-text transcription with automatic language detection.
It supports:
- English: OpenAI Whisper API
- Amharic: Addis AI STT API (preferred) or local fine-tuned Whisper model (fallback)
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import torchaudio
import httpx

# Add parent directory to path for logging config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging
from voice.logging_config import get_logger
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Import cache after logging setup
from voice.cache.transcription_cache import (
    compute_audio_hash,
    get_cached_transcription,
    set_cached_transcription,
)

# Configure HuggingFace cache path (Railway compatible with local fallback)
HF_HOME = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
os.environ["HF_HOME"] = HF_HOME
os.environ["TRANSFORMERS_CACHE"] = HF_HOME
logger.info(f"HuggingFace cache directory: {HF_HOME}")

# Initialize OpenAI client for English
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Addis AI configuration for Amharic STT
ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
ADDIS_AI_STT_URL = "https://api.addisassistant.com/api/v1/audio/transcribe"

# Global model cache to avoid reloading (fallback only)
_amharic_model = None
_amharic_processor = None


def load_amharic_model():
    """
    Load the Amharic-optimized Whisper model (lazy loading).
    Model cache location configured via HF_HOME environment variable.
    
    Returns:
        Tuple of (model, processor)
    """
    global _amharic_model, _amharic_processor
    
    if _amharic_model is None:
        logger.info("Loading Amharic Whisper model: b1n1yam/shook-medium-amharic-2k")
        logger.info(f"Cache location: {HF_HOME}")
        model_name = "b1n1yam/shook-medium-amharic-2k"
        _amharic_processor = AutoProcessor.from_pretrained(model_name)
        _amharic_model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name)
        
        # Move to appropriate device
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _amharic_model = _amharic_model.to(device)
        logger.info(f"Amharic model loaded on device: {device}")
    
    return _amharic_model, _amharic_processor


def check_amharic_model() -> bool:
    """
    Check if Amharic model is cached (for Railway startup checks).
    
    Returns:
        True if model is cached, False otherwise
    """
    try:
        from transformers import AutoModel
        model_name = "b1n1yam/shook-medium-amharic-2k"
        cache_path = Path(HF_HOME) / "hub" / f"models--{model_name.replace('/', '--')}"
        return cache_path.exists()
    except:
        return False


def detect_language(audio_file_path: str) -> str:
    """
    Detect language of audio using OpenAI Whisper API.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        Language code ('en' for English, 'am' for Amharic, etc.)
    """
    try:
        with open(audio_file_path, "rb") as audio_file:
            # Use OpenAI API for language detection (returns JSON with language)
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
            detected_lang = result.language if hasattr(result, 'language') else 'en'
            logger.info(f"Detected language: {detected_lang}")
            return detected_lang
    except Exception as e:
        logger.warning(f"Language detection failed: {e}, defaulting to English")
        return 'en'


async def transcribe_with_addis_ai(audio_file_path: str) -> str:
    """
    Transcribe audio using Addis AI STT API (Amharic).
    
    This is the preferred method for Amharic transcription as it uses
    Addis AI's native Amharic speech recognition model.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        Transcribed text in Amharic
        
    Raises:
        Exception: If API call fails
    """
    if not ADDIS_AI_API_KEY:
        raise ValueError("ADDIS_AI_API_KEY not set in environment")
    
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    try:
        logger.info("Transcribing Amharic audio with Addis AI STT")
        
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            with open(audio_path, 'rb') as audio_file:
                files = {'audio': (audio_path.name, audio_file, 'audio/wav')}
                data = {'language': 'am'}
                
                response = await http_client.post(
                    ADDIS_AI_STT_URL,
                    headers={"X-API-Key": ADDIS_AI_API_KEY},
                    files=files,
                    data=data
                )
                response.raise_for_status()
                
                result = response.json()
                transcript = result.get('text', '')
                
                if not transcript:
                    raise ValueError("Empty transcript from Addis AI")
                
                logger.info(f"Addis AI transcription: {transcript[:50]}...")
                return transcript.strip()
                
    except httpx.HTTPStatusError as e:
        logger.error(f"Addis AI STT HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Addis AI STT failed: {e.response.text}")
    except Exception as e:
        logger.error(f"Addis AI STT failed: {e}")
        raise Exception(f"Addis AI STT failed: {str(e)}")


def transcribe_with_amharic_model(audio_file_path: str) -> str:
    """
    Transcribe audio using local Amharic Whisper model (FALLBACK).
    
    This is kept as a fallback if Addis AI STT fails.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        Transcribed text in Amharic
    """
    model, processor = load_amharic_model()
    
    # Load audio file at 16kHz (Whisper standard)
    waveform, sample_rate = torchaudio.load(audio_file_path)
    if sample_rate != 16000:
        resampler = torchaudio.transforms.Resample(sample_rate, 16000)
        waveform = resampler(waveform)
    
    # Convert to mono if stereo
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
    
    # Process audio
    audio_array = waveform.squeeze().numpy()
    input_features = processor(
        audio_array, 
        sampling_rate=16000, 
        return_tensors="pt"
    ).input_features
    
    # Move to same device as model
    device = next(model.parameters()).device
    input_features = input_features.to(device)
    
    # Generate transcription
    with torch.no_grad():
        predicted_ids = model.generate(input_features)
    
    # Decode transcription
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    
    return transcription.strip()


async def run_asr_with_user_preference_async(audio_file_path: str, user_language: str) -> Dict[str, str]:
    """
    Transcribe audio based on user's language preference (ASYNC version with Addis AI).
    
    This function routes audio directly to the appropriate model based on
    the user's chosen language during registration.
    
    Amharic: Uses Addis AI STT API (preferred), falls back to local model
    English: Uses OpenAI Whisper API
    
    Args:
        audio_file_path: Path to the audio file (supports WAV, MP3, M4A, etc.)
        user_language: User's preferred language ('en' or 'am')
        
    Returns:
        Dictionary with 'text' and 'language' keys
        
    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: If transcription fails
        
    Example:
        >>> result = await run_asr_with_user_preference_async("voice.wav", "am")
        >>> print(f"Language: {result['language']}, Text: {result['text']}")
        Language: am, Text: አዲስ ቢራ 50 ኪሎ ከገዴኦ እርሻ
    """
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Hash-based cache: same audio + language => skip API call
    audio_hash = compute_audio_hash(str(audio_path))
    cached = get_cached_transcription(audio_hash, user_language)
    if cached and cached.get("text") is not None:
        logger.info("ASR cache HIT (async) user_language=%s", user_language)
        return {"text": cached["text"], "language": cached.get("language", user_language)}
    
    try:
        logger.info(f"Transcribing with user preference: {user_language}")
        
        # Route based on user's language choice
        if user_language.lower() in ['am', 'amharic']:
            # Try Addis AI first, fallback to local model
            try:
                logger.info("Routing to Addis AI STT (Amharic)")
                transcript = await transcribe_with_addis_ai(audio_file_path)
                language = 'am'
            except Exception as addis_error:
                logger.warning(f"Addis AI failed, falling back to local model: {addis_error}")
                transcript = transcribe_with_amharic_model(audio_file_path)
                language = 'am'
        else:
            # Use OpenAI Whisper API for English
            logger.info("Routing to OpenAI Whisper API (English)")
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcript = transcript.strip()
            language = 'en'
        
        result = {"text": transcript, "language": language}
        set_cached_transcription(audio_hash, language, result)
        return result
        
    except Exception as e:
        logger.error(f"ASR failed: {str(e)}")
        raise Exception(f"ASR failed: {str(e)}")


def run_asr_with_user_preference(audio_file_path: str, user_language: str) -> Dict[str, str]:
    """
    Transcribe audio based on user's language preference (SYNC version - for backward compatibility).
    
    This is the synchronous version for existing Celery tasks.
    For new web voice API, use run_asr_with_user_preference_async().
    
    Args:
        audio_file_path: Path to the audio file (supports WAV, MP3, M4A, etc.)
        user_language: User's preferred language ('en' or 'am')
        
    Returns:
        Dictionary with 'text' and 'language' keys
        
    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: If transcription fails
        
    Example:
        >>> result = run_asr_with_user_preference("voice.wav", "am")
        >>> print(f"Language: {result['language']}, Text: {result['text']}")
        Language: am, Text: አዲስ ቢራ 50 ኪሎ ከገዴኦ እርሻ
    """
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Hash-based cache (sync path, used by Celery)
    audio_hash = compute_audio_hash(str(audio_path))
    cached = get_cached_transcription(audio_hash, user_language)
    if cached and cached.get("text") is not None:
        logger.info("ASR cache HIT (sync) user_language=%s", user_language)
        return {"text": cached["text"], "language": cached.get("language", user_language)}
    
    try:
        logger.info(f"Transcribing with user preference: {user_language}")
        
        # Route based on user's language choice
        if user_language.lower() in ['am', 'amharic']:
            # Use local Amharic model (sync only for Celery)
            logger.info("Routing to local Amharic Whisper model")
            transcript = transcribe_with_amharic_model(audio_file_path)
            language = 'am'
        else:
            # Use OpenAI Whisper API for English
            logger.info("Routing to OpenAI Whisper API (English)")
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcript = transcript.strip()
            language = 'en'
        
        result = {"text": transcript, "language": language}
        set_cached_transcription(audio_hash, language, result)
        return result
        
    except Exception as e:
        logger.error(f"ASR failed: {str(e)}")
        raise Exception(f"ASR failed: {str(e)}")


def run_asr(audio_file_path: str, force_language: Optional[str] = None) -> Dict[str, str]:
    """
    Transcribe audio file with automatic language detection and routing.
    
    DEPRECATED: Use run_asr_with_user_preference() instead for conversational AI.
    This function is kept for backward compatibility and fallback scenarios.
    
    This function intelligently routes audio to the appropriate model:
    - Amharic audio → Local fine-tuned Whisper model (b1n1yam/shook-medium-amharic-2k)
    - English audio → OpenAI Whisper API (whisper-1)
    
    Args:
        audio_file_path: Path to the audio file (supports WAV, MP3, M4A, etc.)
        force_language: Optional language code to skip detection ('en' or 'am')
        
    Returns:
        Dictionary with 'text' and 'language' keys
        
    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: If transcription fails
        
    Example:
        >>> result = run_asr("tests/samples/amharic_coffee.wav")
        >>> print(f"Language: {result['language']}, Text: {result['text']}")
        Language: am, Text: አዲስ ቢራ 50 ኪሎ ከገዴኦ እርሻ
    """
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Hash-based cache: try multiple language keys before transcribing
    audio_hash = compute_audio_hash(str(audio_path))
    
    # Try cache with force_language if provided
    if force_language:
        cached = get_cached_transcription(audio_hash, force_language)
        if cached and cached.get("text") is not None:
            logger.info("ASR cache HIT (run_asr) force_language=%s", force_language)
            return {"text": cached["text"], "language": cached.get("language", force_language)}
    
    # Try common language keys before expensive detection
    for lang_key in ["auto", "en", "english", "am", "amharic"]:
        cached = get_cached_transcription(audio_hash, lang_key)
        if cached and cached.get("text") is not None:
            logger.info("ASR cache HIT (run_asr) lang_key=%s", lang_key)
            return {"text": cached["text"], "language": cached.get("language", "en")}
    
    try:
        # Detect language (unless forced) - expensive, so only do if cache miss
        if force_language:
            language = force_language
            logger.info(f"Using forced language: {language}")
        else:
            language = detect_language(audio_file_path)
        
        # Ensure we have a valid language (fallback to english if detection failed)
        if not language:
            language = 'english'
            logger.warning("Language detection returned None, defaulting to English")
        
        # Normalize language name for consistent caching
        if language.lower() in ['am', 'amharic']:
            language = 'amharic'
        else:
            language = 'english'  # Normalize to full name
        
        # Route to appropriate model
        if language == 'amharic':
            logger.info(f"Routing to Amharic Whisper model (detected: {language})")
            transcript = transcribe_with_amharic_model(audio_file_path)
        else:  # English or other languages
            logger.info(f"Routing to OpenAI Whisper API (detected: {language})")
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcript = transcript.strip()
        
        result = {"text": transcript, "language": language}
        set_cached_transcription(audio_hash, language, result)
        return result
        
    except Exception as e:
        logger.error(f"ASR failed: {str(e)}")
        raise Exception(f"ASR failed: {str(e)}")


if __name__ == "__main__":
    import sys
    
    # Setup logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python -m voice.asr.asr_infer <audio-file-path> [--lang en|am]")
        print("\nExamples:")
        print("  python -m voice.asr.asr_infer audio.wav")
        print("  python -m voice.asr.asr_infer audio.wav --lang am")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    force_lang = None
    
    # Check for language flag
    if len(sys.argv) > 2 and sys.argv[2] == '--lang':
        if len(sys.argv) > 3:
            force_lang = sys.argv[3]
    
    try:
        result = run_asr(audio_path, force_language=force_lang)
        print(f"\nLanguage: {result['language']}")
        print(f"Transcript: {result['text']}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
