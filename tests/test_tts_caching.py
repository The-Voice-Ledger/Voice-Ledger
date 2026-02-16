#!/usr/bin/env python3
"""
Test TTS functionality with Caching.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from voice.tts.tts_provider import TTSProvider

async def test_tts_caching():
    """Test TTS generation and caching."""
    
    print("=" * 60)
    print("Testing Voice TTS System with Caching")
    print("=" * 60)
    print()
    
    text = "This is a test of the cached text to speech system."
    language = "en"
    
    # Run 1: Should be slow (API call)
    print("Run 1: Generating audio (expecting API call)...")
    start_time = time.time()
    try:
        audio_1 = await TTSProvider.text_to_speech(text, language)
        duration_1 = time.time() - start_time
        print(f"  [OK] Run 1 complete: {len(audio_1)} bytes in {duration_1:.2f} seconds")
    except Exception as e:
        print(f"  [FAIL] Run 1 failed: {e}")
        return False

    # Run 2: Should be fast (Cache hit)
    print("\nRun 2: Requesting same audio (expecting Cache HIT)...")
    start_time = time.time()
    try:
        audio_2 = await TTSProvider.text_to_speech(text, language)
        duration_2 = time.time() - start_time
        print(f"  [OK] Run 2 complete: {len(audio_2)} bytes in {duration_2:.2f} seconds")
        
        if duration_2 < 0.1:
            print("  [SPEED] Speedup confirmed: Result returned instantly!")
        else:
            print("  [WARN] Warning: Result took longer than expected for a cache hit.")
            
    except Exception as e:
        print(f"  [FAIL] Run 2 failed: {e}")
        return False
        
    # Verify content matches
    if audio_1 == audio_2:
        print("  [OK] validated: Audio content is identical.")
    else:
        print("  [FAIL] validation failed: Audio content differs!")
        return False
        
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tts_caching())
    sys.exit(0 if success else 1)
