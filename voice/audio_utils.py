"""
Audio Processing Utilities

This module provides utilities for audio file validation, format conversion,
and metadata extraction for the Voice Ledger API.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import tempfile
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import soundfile as sf
import json


# Audio constraints
MAX_FILE_SIZE_MB = 25  # OpenAI Whisper API limit
MAX_DURATION_SECONDS = 600  # 10 minutes max
SUPPORTED_FORMATS = ['.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma']


class AudioValidationError(Exception):
    """Raised when audio file validation fails."""
    pass


def validate_audio_file(file_path: str, max_size_mb: int = MAX_FILE_SIZE_MB) -> None:
    """
    Validate audio file exists, has correct extension, and size is within limits.
    
    Args:
        file_path: Path to audio file
        max_size_mb: Maximum file size in megabytes
        
    Raises:
        AudioValidationError: If validation fails
        
    Example:
        >>> validate_audio_file("audio.mp3")
        # No error means validation passed
        
        >>> validate_audio_file("huge_file.mp3", max_size_mb=5)
        # Raises AudioValidationError if file > 5 MB
    """
    path = Path(file_path)
    
    # Check file exists
    if not path.exists():
        raise AudioValidationError(f"Audio file not found: {file_path}")
    
    # Check file extension
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise AudioValidationError(
            f"Unsupported audio format: {path.suffix}. "
            f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    # Check file size
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        raise AudioValidationError(
            f"Audio file too large: {file_size_mb:.2f} MB. "
            f"Maximum allowed: {max_size_mb} MB"
        )


def get_audio_duration(file_path: str, timeout: int = 10) -> float:
    """
    Get duration of audio file in seconds using ffprobe.
    
    Args:
        file_path: Path to audio file
        timeout: Maximum seconds to wait (default: 10)
        
    Returns:
        Duration in seconds
        
    Raises:
        AudioValidationError: If audio file cannot be read
        
    Example:
        >>> duration = get_audio_duration("voice_command.mp3")
        >>> print(f"Duration: {duration:.2f} seconds")
        Duration: 15.43 seconds
    """
    try:
        # Use ffprobe to get duration without loading entire file
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=True
        )
        
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
        
    except subprocess.TimeoutExpired:
        raise AudioValidationError(f"Reading audio duration timed out after {timeout} seconds")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise AudioValidationError(f"Failed to parse audio duration: {str(e)}")
    except subprocess.CalledProcessError as e:
        raise AudioValidationError(f"Failed to read audio file: {e.stderr.decode('utf-8', errors='ignore')}")
    except Exception as e:
        raise AudioValidationError(f"Error getting audio duration: {str(e)}")


def get_audio_metadata(file_path: str, timeout: int = 10) -> dict:
    """
    Extract metadata from audio file using ffprobe.
    
    Args:
        file_path: Path to audio file
        timeout: Maximum seconds to wait (default: 10)
        
    Returns:
        Dictionary with metadata:
        {
            "duration_seconds": float,
            "sample_rate": int,
            "channels": int,
            "format": str,
            "file_size_mb": float
        }
        
    Example:
        >>> metadata = get_audio_metadata("recording.wav")
        >>> print(metadata)
        {
            "duration_seconds": 32.5,
            "sample_rate": 44100,
            "channels": 2,
            "format": "wav",
            "file_size_mb": 2.8
        }
    """
    path = Path(file_path)
    
    try:
        # Use ffprobe to get audio metadata
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration:stream=sample_rate,channels',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=True
        )
        
        data = json.loads(result.stdout)
        
        # Extract values (first audio stream)
        stream = data['streams'][0] if data.get('streams') else {}
        duration = float(data['format'].get('duration', 0))
        sample_rate = int(stream.get('sample_rate', 16000))
        channels = int(stream.get('channels', 1))
        
        return {
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "format": path.suffix.lstrip('.').lower(),
            "file_size_mb": path.stat().st_size / (1024 * 1024)
        }
        
    except subprocess.TimeoutExpired:
        raise AudioValidationError(f"Reading audio metadata timed out after {timeout} seconds")
    except (KeyError, ValueError, json.JSONDecodeError, IndexError) as e:
        raise AudioValidationError(f"Failed to parse audio metadata: {str(e)}")
    except subprocess.CalledProcessError as e:
        raise AudioValidationError(f"Failed to read audio file: {e.stderr.decode('utf-8', errors='ignore')}")
    except Exception as e:
        raise AudioValidationError(f"Failed to extract metadata: {str(e)}")


def convert_to_wav(input_path: str, output_path: Optional[str] = None, timeout: int = 30) -> str:
    """
    Convert audio file to WAV format using ffmpeg directly with timeout protection.
    
    Args:
        input_path: Path to input audio file (any format)
        output_path: Path for output WAV file (optional, creates temp file if None)
        timeout: Maximum seconds to wait for conversion (default: 30)
        
    Returns:
        Path to converted WAV file
        
    Raises:
        AudioValidationError: If conversion fails or times out
        
    Example:
        >>> wav_path = convert_to_wav("voice.mp3")
        >>> print(wav_path)
        /tmp/tmpXYZ123.wav
        
        >>> wav_path = convert_to_wav("voice.m4a", "output.wav")
        >>> print(wav_path)
        output.wav
    """
    input_path_obj = Path(input_path)
    
    # If already WAV, return original path
    if input_path_obj.suffix.lower() == '.wav':
        return input_path
    
    try:
        # Create output path if not provided
        if output_path is None:
            # Create temp file with .wav extension
            fd, output_path = tempfile.mkstemp(suffix='.wav', prefix='voice_')
            os.close(fd)  # Close file descriptor
        
        # Use ffmpeg directly with explicit pipes to avoid stdin/stdout blocking
        # -y: overwrite output file without asking
        # -i: input file
        # -acodec pcm_s16le: standard WAV codec
        # -ar 16000: 16kHz sample rate (good for speech)
        # -ac 1: mono audio
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite without asking
            '-i', input_path,  # Input file
            '-acodec', 'pcm_s16le',  # WAV codec
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',  # Mono
            output_path
        ]
        
        # Run with timeout and explicit pipe configuration
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,  # Don't wait for stdin
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            raise AudioValidationError(f"ffmpeg conversion failed: {error_msg}")
        
        # Verify output file was created
        if not Path(output_path).exists():
            raise AudioValidationError("Conversion completed but output file not found")
        
        return output_path
        
    except subprocess.TimeoutExpired:
        raise AudioValidationError(f"Audio conversion timed out after {timeout} seconds")
    except AudioValidationError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        raise AudioValidationError(f"Audio conversion failed: {str(e)}")


def validate_and_convert_audio(
    input_path: str,
    max_size_mb: int = MAX_FILE_SIZE_MB,
    max_duration_seconds: int = MAX_DURATION_SECONDS
) -> Tuple[str, dict]:
    """
    Validate audio file and convert to WAV if needed.
    
    This is the main function to use before sending audio to ASR.
    It performs all validation checks and ensures output is in WAV format.
    
    Args:
        input_path: Path to input audio file
        max_size_mb: Maximum file size in MB
        max_duration_seconds: Maximum duration in seconds
        
    Returns:
        Tuple of (wav_path, metadata):
        - wav_path: Path to WAV file (converted or original)
        - metadata: Audio metadata dict
        
    Raises:
        AudioValidationError: If validation fails
        
    Example:
        >>> wav_path, metadata = validate_and_convert_audio("voice.mp3")
        >>> print(f"Ready for ASR: {wav_path}")
        >>> print(f"Duration: {metadata['duration_seconds']:.2f}s")
        Ready for ASR: /tmp/voice_abc123.wav
        Duration: 15.43s
    """
    # Step 1: Validate file
    validate_audio_file(input_path, max_size_mb)
    
    # Step 2: Get metadata
    metadata = get_audio_metadata(input_path)
    
    # Step 3: Check duration
    if metadata['duration_seconds'] > max_duration_seconds:
        raise AudioValidationError(
            f"Audio duration too long: {metadata['duration_seconds']:.2f}s. "
            f"Maximum allowed: {max_duration_seconds}s"
        )
    
    # Step 4: Convert to WAV if needed
    wav_path = convert_to_wav(input_path)
    
    return wav_path, metadata


def cleanup_temp_file(file_path: str) -> None:
    """
    Safely delete temporary file.
    
    Args:
        file_path: Path to file to delete
        
    Example:
        >>> wav_path = convert_to_wav("audio.mp3")
        >>> # ... use wav_path for processing ...
        >>> cleanup_temp_file(wav_path)
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        # Silently ignore cleanup errors
        pass


if __name__ == "__main__":
    """Test audio utilities with sample file."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m voice.audio_utils <audio-file>")
        print("\nTests audio validation and conversion utilities.")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    try:
        print(f"Testing audio utilities with: {audio_file}\n")
        
        # Test validation
        print("1. Validating audio file...")
        validate_audio_file(audio_file)
        print("   ✓ File is valid\n")
        
        # Test metadata extraction
        print("2. Extracting metadata...")
        metadata = get_audio_metadata(audio_file)
        print(f"   Duration: {metadata['duration_seconds']:.2f}s")
        print(f"   Sample rate: {metadata['sample_rate']} Hz")
        print(f"   Channels: {metadata['channels']}")
        print(f"   Format: {metadata['format']}")
        print(f"   File size: {metadata['file_size_mb']:.2f} MB\n")
        
        # Test conversion
        print("3. Converting to WAV...")
        wav_path, meta = validate_and_convert_audio(audio_file)
        print(f"   ✓ Converted to: {wav_path}")
        print(f"   ✓ Duration check: {meta['duration_seconds']:.2f}s\n")
        
        # Cleanup
        if wav_path != audio_file:
            print("4. Cleaning up temp file...")
            cleanup_temp_file(wav_path)
            print("   ✓ Cleanup complete\n")
        
        print("✅ All tests passed!")
        
    except AudioValidationError as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
