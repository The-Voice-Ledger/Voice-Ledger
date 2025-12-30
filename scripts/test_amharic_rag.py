"""
Test Amharic RAG integration

Tests:
1. Translation (Amharic → English)
2. Query classification (skip RAG for operational commands)
3. RAG context enhancement for documentation queries
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from voice.integrations.amharic_conversation import (
    translate_amharic_to_english,
    enhance_with_rag_context,
    SYSTEM_PROMPT_AM
)

async def test_translation():
    """Test OpenAI translation of Amharic to English"""
    print("\n" + "="*60)
    print("Test 1: Translation (Amharic → English)")
    print("="*60)
    
    test_queries = [
        "የኢፒሲአይኤስ ክስተት ዓይነቶች ምንድናቸው?",
        "50 ኪሎግራም የሲዳማ ቡና አጨድኩ",
        "ባች ABC123ን ወደ አዲስ መጋዘን ላክ"
    ]
    
    for query in test_queries:
        print(f"\n📝 Amharic: {query}")
        translation = await translate_amharic_to_english(query)
        if translation:
            print(f"✅ English: {translation}")
        else:
            print(f"❌ Translation failed")

async def test_query_classification():
    """Test that operational commands skip RAG"""
    print("\n" + "="*60)
    print("Test 2: Query Classification (Operational vs Documentation)")
    print("="*60)
    
    test_cases = [
        ("50 ኪሎግራም የሲዳማ ቡና አጨድኩ", "TRANSACTIONAL - should skip RAG"),
        ("የኢፒሲአይኤስ ክስተት ዓይነቶች ምንድናቸው?", "DOCUMENTATION - should use RAG"),
        ("ባች ABC123ን ወደ አዲስ መጋዘን ላክ", "TRANSACTIONAL - should skip RAG")
    ]
    
    for query, expected in test_cases:
        print(f"\n📝 Query: {query}")
        print(f"🎯 Expected: {expected}")
        
        # Check if RAG context is added
        enhanced = await enhance_with_rag_context(query, SYSTEM_PROMPT_AM)
        
        if "Additional Context" in enhanced or "የተጨማሪ አውድ" in enhanced:
            print(f"✅ RAG context added (Documentation query)")
        else:
            print(f"⏭️  No RAG context (Transactional/Operational query)")

async def test_rag_enhancement():
    """Test RAG context enhancement for documentation queries"""
    print("\n" + "="*60)
    print("Test 3: RAG Context Enhancement")
    print("="*60)
    
    doc_query = "የኢፒሲአይኤስ ክስተት ዓይነቶች ምንድናቸው?"
    print(f"\n📝 Documentation Query: {doc_query}")
    
    enhanced = await enhance_with_rag_context(doc_query, SYSTEM_PROMPT_AM)
    
    if enhanced != SYSTEM_PROMPT_AM:
        print(f"✅ System prompt enhanced with RAG context")
        context_added = len(enhanced) - len(SYSTEM_PROMPT_AM)
        print(f"📊 Context added: {context_added} characters")
    else:
        print(f"❌ No RAG context added (might be transactional or RAG failed)")

async def main():
    print("="*60)
    print("Amharic RAG Integration Tests")
    print("="*60)
    print("\nThis tests:")
    print("1. OpenAI translation (Amharic → English)")
    print("2. Query classification (operational vs documentation)")
    print("3. RAG enhancement (only for documentation queries)")
    print("4. Safety: Operational commands bypass RAG")
    
    await test_translation()
    await test_query_classification()
    await test_rag_enhancement()
    
    print("\n" + "="*60)
    print("Tests Complete")
    print("="*60)
    print("\n💡 To disable RAG for Amharic:")
    print("   Edit: voice/integrations/amharic_conversation.py")
    print("   Uncomment line: # use_rag = False")

if __name__ == "__main__":
    asyncio.run(main())
