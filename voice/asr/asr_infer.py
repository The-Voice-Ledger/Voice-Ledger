"""
Automatic Speech Recognition (ASR) Module

This module handles audio-to-text transcription with automatic language detection.
It supports both English (OpenAI Whisper API) and Amharic (local fine-tuned model).
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import torchaudio

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client for English
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global model cache to avoid reloading
_amharic_model = None
_amharic_processor = None


def load_amharic_model():
    """
    Load the Amharic-optimized Whisper model (lazy loading).
    
    Returns:
        Tuple of (model, processor)
    """
    global _amharic_model, _amharic_processor
    
    if _amharic_model is None:
        logger.info("Loading Amharic Whisper model: b1n1yam/shook-medium-amharic-2k")
        model_name = "b1n1yam/shook-medium-amharic-2k"
        _amharic_processor = AutoProcessor.from_pretrained(model_name)
        _amharic_model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name)
        
        # Move to appropriate device
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _amharic_model = _amharic_model.to(device)
        logger.info(f"Amharic model loaded on device: {device}")
    
    return _amharic_model, _amharic_processor


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


def transcribe_with_amharic_model(audio_file_path: str) -> str:
    """
    Transcribe audio using local Amharic Whisper model.
    
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


def run_asr_with_user_preference(audio_file_path: str, user_language: str) -> Dict[str, str]:
    """
    Transcribe audio based on user's language preference (not detection).
    
    This function routes audio directly to the appropriate model based on
    the user's chosen language during registration, without relying on
    potentially unreliable language detection.
    
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
    
    try:
        logger.info(f"Transcribing with user preference: {user_language}")
        
        # Route based on user's language choice
        if user_language.lower() in ['am', 'amharic']:
            # Use local Amharic model
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
        
        return {
            'text': transcript,
            'language': language
        }
        
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
    
    try:
        # Detect language (unless forced)
        if force_language:
            language = force_language
            logger.info(f"Using forced language: {language}")
        else:
            language = detect_language(audio_file_path)
        
        # Ensure we have a valid language (fallback to english if detection failed)
        if not language:
            language = 'english'
            logger.warning("Language detection returned None, defaulting to English")
        
        # Route to appropriate model
        # OpenAI returns full language names like "amharic", "english"
        # but also accepts ISO codes like "am", "en"
        if language.lower() in ['am', 'amharic']:  # Amharic
            logger.info(f"Routing to Amharic Whisper model (detected: {language})")
            transcript = transcribe_with_amharic_model(audio_file_path)
            language = 'amharic'  # Normalize to full name
        else:  # English or other languages
            logger.info(f"Routing to OpenAI Whisper API (detected: {language})")
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcript = transcript.strip()
        
        return {
            'text': transcript,
            'language': language
        }
        
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
