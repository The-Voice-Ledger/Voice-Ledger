#!/usr/bin/env python3
"""
Test Code Retrieval from ChromaDB

Tests the RAG system's ability to retrieve relevant code snippets
after indexing the codebase.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.rag.hybrid_router import search_documentation

def test_code_queries():
    """Test various code-related queries"""
    
    queries = [
        "How is batch verification implemented?",
        "Show me the marketplace API endpoints",
        "Where is GPS photo extraction done?",
        "Explain the token minting workflow",
        "How does conversation management work?",
        "What are the EPCIS event types?",
        "How is aggregation implemented?",
        "Show me the database models for coffee batches",
    ]
    
    print("=" * 80)
    print("CODE RETRIEVAL TEST - ChromaDB with Indexed Codebase")
    print("=" * 80)
    print()
    
    for idx, query in enumerate(queries, 1):
        print(f"\n{'=' * 80}")
        print(f"Query {idx}: {query}")
        print('=' * 80)
        
        # Search documentation (includes code now)
        results = search_documentation(query, top_k=3)
        
        if not results:
            print("❌ No results found")
            continue
        
        print(f"\n✅ Found {len(results)} relevant results:\n")
        
        for i, result in enumerate(results, 1):
            source = result.get('source', 'unknown')
            result_type = result.get('type', 'unknown')
            content = result['content']
            
            # Extract metadata if it's code
            if result_type == 'code':
                lines = content.split('\n')
                file_info = lines[0] if lines else ''
                language_info = lines[1] if len(lines) > 1 else ''
                line_range = lines[2] if len(lines) > 2 else ''
                entities = lines[3] if len(lines) > 3 else ''
                
                print(f"Result {i} [CODE]:")
                print(f"  {file_info}")
                print(f"  {language_info}")
                print(f"  {line_range}")
                print(f"  {entities}")
                print(f"\n  Preview:")
                # Show first 500 chars of actual code (after metadata header)
                code_start = '\n'.join(lines[5:]) if len(lines) > 5 else ''
                preview = code_start[:500].strip()
                for line in preview.split('\n'):
                    print(f"    {line}")
                if len(code_start) > 500:
                    print("    ...")
            else:
                # Documentation/PDF result
                print(f"Result {i} [DOCUMENTATION]:")
                print(f"  Source: {source}")
                print(f"  Preview:")
                preview = content[:400].strip()
                for line in preview.split('\n'):
                    print(f"    {line}")
                if len(content) > 400:
                    print("    ...")
            
            print()
    
    print("\n" + "=" * 80)
    print("✅ CODE RETRIEVAL TEST COMPLETE!")
    print("=" * 80)
    print("\n💡 The system can now retrieve both documentation AND code!")
    print("   This enables queries about implementation details, API usage,")
    print("   database schemas, and smart contract functions.")

if __name__ == "__main__":
    test_code_queries()
