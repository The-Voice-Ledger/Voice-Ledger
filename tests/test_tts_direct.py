#!/usr/bin/env python3
"""
Test TTS functionality directly.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

async def test_tts():
    """Test TTS generation and text processing."""
    
    print("=" * 60)
    print("Testing Voice TTS System")
    print("=" * 60)
    print()
    
    # Test 1: Text cleaning and formatting
    print("Test 1: Text Cleaning & Formatting")
    print("-" * 40)
    from voice.telegram.voice_responses import clean_text_for_tts, format_for_voice
    
    test_text = '📦 *Batch Created*: 50kg for $450\n\nGTIN: `00614141618286`'
    clean = clean_text_for_tts(test_text)
    formatted = format_for_voice(clean)
    
    print(f'Original:  {test_text!r}')
    print(f'Clean:     {clean!r}')
    print(f'Formatted: {formatted!r}')
    print()
    
    # Test 2: OpenAI TTS generation
    print("Test 2: OpenAI TTS Generation")
    print("-" * 40)
    from openai import AsyncOpenAI
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set in environment")
        return False
    
    client = AsyncOpenAI(api_key=api_key)
    
    try:
        test_input = "This is a test of the text to speech system."
        print(f'Generating TTS for: "{test_input}"')
        
        response = await client.audio.speech.create(
            model='tts-1',
            voice='nova',
            input=test_input
        )
        audio_bytes = response.content
        print(f'✅ OpenAI TTS successful: {len(audio_bytes):,} bytes generated')
        
        # Save to file
        output_path = '/tmp/test_tts.mp3'
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        print(f'✅ Audio saved to {output_path}')
        print()
        
    except Exception as e:
        print(f'❌ OpenAI TTS failed: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Full voice_responses flow (without sending to Telegram)
    print("Test 3: Voice Response Processing")
    print("-" * 40)
    
    try:
        batch_message = (
            "📦 Batch Created - Awaiting Verification\n\n"
            "Batch ID: TEST_BATCH_001\n"
            "GTIN: 00614141618286\n"
            "Variety: Arabica Coffee\n"
            "Quantity: 50 kg\n"
            "Origin: Siddhama"
        )
        
        clean_batch = clean_text_for_tts(batch_message)
        formatted_batch = format_for_voice(clean_batch)
        
        print(f'Processing batch message...')
        print(f'Input length: {len(batch_message)} chars')
        print(f'Clean length: {len(clean_batch)} chars')
        print(f'Formatted: {formatted_batch[:100]}...')
        
        response = await client.audio.speech.create(
            model='tts-1',
            voice='nova',
            input=formatted_batch
        )
        audio_bytes = response.content
        print(f'✅ Batch TTS successful: {len(audio_bytes):,} bytes')
        
        output_path = '/tmp/test_batch_tts.mp3'
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        print(f'✅ Batch audio saved to {output_path}')
        print()
        
    except Exception as e:
        print(f'❌ Batch TTS failed: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 60)
    print("✅ All TTS tests passed!")
    print("=" * 60)
    print()
    print("You can play the test audio files:")
    print("  afplay /tmp/test_tts.mp3")
    print("  afplay /tmp/test_batch_tts.mp3")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tts())
    sys.exit(0 if success else 1)
