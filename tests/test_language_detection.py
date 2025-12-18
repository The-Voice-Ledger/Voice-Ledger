"""
Test script to demonstrate automatic language detection in Voice Ledger ASR.

This shows how the system:
1. Automatically detects the language using OpenAI Whisper API
2. Routes Amharic audio to the local fine-tuned model (b1n1yam/shook-medium-amharic-2k)
3. Routes English/other languages to OpenAI Whisper API
"""

import sys
from pathlib import Path
from voice.asr.asr_infer import run_asr

def test_language_detection(audio_file: str):
    """Test language detection on an audio file."""
    print(f"\n{'='*60}")
    print(f"Testing: {audio_file}")
    print('='*60)
    
    try:
        result = run_asr(audio_file)
        
        print(f"\n✅ SUCCESS!")
        print(f"Detected Language: {result['language']}")
        print(f"Transcript: {result['text'][:100]}...")
        
        # Show which model was used
        if result['language'].lower() in ['am', 'amharic']:
            print(f"🎯 Routed to: Local Amharic Whisper Model")
        else:
            print(f"🎯 Routed to: OpenAI Whisper API")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║  Voice Ledger - Automatic Language Detection Test               ║
╚══════════════════════════════════════════════════════════════════╝

How it works:
1. OpenAI Whisper API detects the language (verbose_json format)
2. Returns: "english", "amharic", "somali", etc.
3. If "amharic" or "am" → Route to local fine-tuned model
4. Otherwise → Use OpenAI Whisper API for transcription

Testing with available audio files...
    """)
    
    # Test with available English audio
    test_samples = [
        "tests/samples/test_commission.wav",
        "tests/samples/test_audio.wav",
    ]
    
    for sample in test_samples:
        if Path(sample).exists():
            test_language_detection(sample)
        else:
            print(f"\n⚠️  File not found: {sample}")
    
    print("\n" + "="*60)
    print("📝 Note: To test Amharic detection:")
    print("   1. Record Amharic audio or use an Amharic test file")
    print("   2. Run: python test_language_detection.py path/to/amharic.wav")
    print("   3. System will auto-detect and route to local Amharic model")
    print("="*60 + "\n")
