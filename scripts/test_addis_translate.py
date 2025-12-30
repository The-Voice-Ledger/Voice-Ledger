"""
Test script for AddisAI translate endpoint
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from voice.providers.addis_ai import translate_sync
import json

def test_amharic_to_english():
    """Test translating from Amharic to English"""
    print("\n=== Testing Amharic → English ===")
    amharic_text = "ሰላም። የኔ ስም አብደላ ነው።"
    
    try:
        result = translate_sync(
            text=amharic_text,
            source_lang="am",
            target_lang="en"
        )
        print(f"✅ Original: {result['original_text']}")
        print(f"✅ Translation: {result['translation']}")
        print(f"✅ Source: {result['source_lang']} → Target: {result['target_lang']}")
        print(f"✅ Provider: {result['provider']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_english_to_amharic():
    """Test translating from English to Amharic"""
    print("\n=== Testing English → Amharic ===")
    english_text = "Hello. My name is Abdela."
    
    try:
        result = translate_sync(
            text=english_text,
            source_lang="en",
            target_lang="am"
        )
        print(f"✅ Original: {result['original_text']}")
        print(f"✅ Translation: {result['translation']}")
        print(f"✅ Source: {result['source_lang']} → Target: {result['target_lang']}")
        print(f"✅ Provider: {result['provider']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_query_translation():
    """Test translating typical RAG query from Amharic to English"""
    print("\n=== Testing RAG Query Translation ===")
    amharic_query = "የኢፒሲአይኤስ ክስተት ዓይነቶች ምንድናቸው?"
    
    try:
        result = translate_sync(
            text=amharic_query,
            source_lang="am",
            target_lang="en"
        )
        print(f"✅ Original query: {result['original_text']}")
        print(f"✅ Translated query: {result['translation']}")
        print(f"✅ This can now be used to search English documentation")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("AddisAI Translation API Test")
    print("=" * 60)
    
    # Check environment variable
    api_key = os.getenv("ADDIS_AI_API_KEY")
    if not api_key:
        print("❌ ADDIS_AI_API_KEY not set in environment")
        sys.exit(1)
    
    print(f"✅ API Key found: {api_key[:10]}...")
    
    results = []
    
    # Run all tests
    results.append(("Amharic → English", test_amharic_to_english()))
    results.append(("English → Amharic", test_english_to_amharic()))
    results.append(("RAG Query Translation", test_rag_query_translation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Translation is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check error messages above.")
        sys.exit(1)
