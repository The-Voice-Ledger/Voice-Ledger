#!/usr/bin/env python3
"""
Test script for AddisAI cloud STT integration

Tests:
1. AddisAI provider initialization
2. Transcription with cloud STT
3. Hybrid fallback behavior
4. TTS generation (bonus)

Usage:
    python test_addisai_stt.py
    
    # Test with specific audio file:
    python test_addisai_stt.py path/to/audio.wav
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from voice.providers.addis_ai import AddisAIProvider, AddisAIError


async def test_provider_initialization():
    """Test 1: Provider initialization"""
    logger.info("=" * 60)
    logger.info("TEST 1: AddisAI Provider Initialization")
    logger.info("=" * 60)
    
    try:
        provider = AddisAIProvider()
        
        if provider.api_key:
            logger.info("✅ Provider initialized successfully")
            logger.info(f"   Base URL: {provider.base_url}")
            logger.info(f"   Chat endpoint: {provider.chat_endpoint}")
            logger.info(f"   TTS endpoint: {provider.tts_endpoint}")
            return provider
        else:
            logger.error("❌ API key not configured")
            logger.error("   Set ADDIS_AI_API_KEY in .env")
            return None
            
    except Exception as e:
        logger.error(f"❌ Provider initialization failed: {e}")
        return None


async def run_cloud_transcription(provider: AddisAIProvider, audio_path: str):
    """Test 2: Cloud STT transcription"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Cloud STT Transcription")
    logger.info("=" * 60)
    
    if not Path(audio_path).exists():
        logger.error(f"❌ Audio file not found: {audio_path}")
        return False
    
    try:
        logger.info(f"Transcribing: {audio_path}")
        result = await provider.transcribe(
            audio_path=audio_path,
            language="am",
            return_ai_response=True
        )
        
        logger.info("✅ Transcription successful!")
        logger.info(f"   Text: {result['text'][:100]}...")
        logger.info(f"   Language: {result['language']}")
        logger.info(f"   Confidence: {result['confidence']:.2f}")
        logger.info(f"   Provider: {result['provider']}")
        
        if result.get('ai_response'):
            logger.info(f"   AI Response: {result['ai_response'][:100]}...")
        
        return True
        
    except AddisAIError as e:
        logger.error(f"❌ AddisAI transcription failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return False


async def test_hybrid_fallback():
    """Test 3: Hybrid fallback behavior"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Hybrid Fallback Behavior")
    logger.info("=" * 60)
    
    # Check environment configuration
    use_addis_stt = os.getenv("USE_ADDIS_STT", "true").lower() == "true"
    use_local_fallback = os.getenv("USE_LOCAL_AMHARIC_FALLBACK", "true").lower() == "true"
    
    logger.info(f"USE_ADDIS_STT: {use_addis_stt}")
    logger.info(f"USE_LOCAL_AMHARIC_FALLBACK: {use_local_fallback}")
    
    if use_addis_stt and use_local_fallback:
        logger.info("✅ Hybrid mode enabled (cloud with fallback)")
    elif use_addis_stt and not use_local_fallback:
        logger.info("✅ Cloud-only mode (production deployment)")
    elif not use_addis_stt and use_local_fallback:
        logger.info("✅ Local-only mode (offline/development)")
    else:
        logger.warning("⚠️  Both flags disabled - no STT available!")
    
    return True


async def run_tts_generation(provider: AddisAIProvider):
    """Test 4: TTS generation (bonus)"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: TTS Generation (Bonus)")
    logger.info("=" * 60)
    
    try:
        test_text = "ሰላም፣ እንዴት ነህ?"
        logger.info(f"Generating speech for: {test_text}")
        
        audio_bytes = await provider.text_to_speech(
            text=test_text,
            language="am"
        )
        
        logger.info(f"✅ TTS successful! Generated {len(audio_bytes)} bytes")
        
        # Save to file
        output_path = "test_tts_output.wav"
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        logger.info(f"   Saved to: {output_path}")
        
        return True
        
    except AddisAIError as e:
        logger.error(f"❌ TTS failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return False


async def run_asr_integration(audio_path: str):
    """Test 5: Full ASR integration"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Full ASR Integration")
    logger.info("=" * 60)
    
    if not Path(audio_path).exists():
        logger.warning(f"⚠️  Audio file not found: {audio_path}, skipping ASR test")
        return False
    
    try:
        from voice.asr.asr_infer import run_asr_with_user_preference
        
        logger.info(f"Testing ASR with hybrid routing: {audio_path}")
        result = run_asr_with_user_preference(
            audio_file_path=audio_path,
            user_language="am"
        )
        
        logger.info("✅ ASR integration successful!")
        logger.info(f"   Text: {result['text'][:100]}...")
        logger.info(f"   Language: {result['language']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ASR integration failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("AddisAI Cloud STT Integration Tests")
    logger.info("=" * 60)
    
    # Get test audio file from command line or use default
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        # Try to find a test audio file
        test_paths = [
            "admin_scripts/test_audio/amharic_sample.wav",
            "tests/audio/amharic_sample.wav",
            "test_audio.wav"
        ]
        audio_path = None
        for path in test_paths:
            if Path(path).exists():
                audio_path = path
                break
        
        if not audio_path:
            logger.warning("⚠️  No test audio file found. Some tests will be skipped.")
            logger.info("   Usage: python test_addisai_stt.py path/to/audio.wav")
            audio_path = "test_audio.wav"  # Use dummy path for initialization tests
    
    results = {}
    
    # Test 1: Provider initialization
    provider = await test_provider_initialization()
    results['initialization'] = provider is not None
    
    if not provider:
        logger.error("\n❌ Cannot proceed without valid provider. Check your ADDIS_AI_API_KEY.")
        return
    
    # Test 2: Cloud transcription
    if Path(audio_path).exists():
        results['transcription'] = await run_cloud_transcription(provider, audio_path)
    else:
        logger.warning(f"⚠️  Skipping transcription test (audio file not found)")
        results['transcription'] = None
    
    # Test 3: Hybrid fallback
    results['hybrid_config'] = await test_hybrid_fallback()
    
    # Test 4: TTS (optional)
    results['tts'] = await run_tts_generation(provider)
    
    # Test 5: ASR integration
    if Path(audio_path).exists():
        results['asr_integration'] = await run_asr_integration(audio_path)
    else:
        logger.warning(f"⚠️  Skipping ASR integration test (audio file not found)")
        results['asr_integration'] = None
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result is True else ("❌ FAIL" if result is False else "⚠️  SKIP")
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total - skipped} passed ({skipped} skipped, {failed} failed)")
    
    if failed == 0 and passed > 0:
        logger.info("\n🎉 All tests passed!")
        logger.info("\nNext steps:")
        logger.info("1. Test with real Amharic audio")
        logger.info("2. Monitor latency and accuracy")
        logger.info("3. Deploy to staging with USE_ADDIS_STT=true")
        logger.info("4. For production cloud-only: USE_LOCAL_AMHARIC_FALLBACK=false")
    elif failed > 0:
        logger.error("\n⚠️  Some tests failed. Check logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
