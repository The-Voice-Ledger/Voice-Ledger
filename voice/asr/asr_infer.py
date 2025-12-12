"""
Automatic Speech Recognition (ASR) Module

This module handles audio-to-text transcription using OpenAI's Whisper API.
It processes audio files and returns transcribed text.
"""

import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_asr(audio_file_path: str) -> str:
    """
    Transcribe audio file to text using OpenAI Whisper API.
    
    Args:
        audio_file_path: Path to the audio file (supports WAV, MP3, M4A, etc.)
        
    Returns:
        Transcribed text from the audio
        
    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: If API call fails
        
    Example:
        >>> transcript = run_asr("tests/samples/coffee_delivery.wav")
        >>> print(transcript)
        "Deliver 50 bags of washed coffee from station Abebe to Addis"
    """
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        return transcript.strip()
    except Exception as e:
        raise Exception(f"ASR failed: {str(e)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m voice.asr.asr_infer <audio-file-path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    try:
        result = run_asr(audio_path)
        print(f"Transcript: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
