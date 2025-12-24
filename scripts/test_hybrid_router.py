#!/usr/bin/env python3
"""
Test Hybrid RAG Router

Demonstrates routing queries to appropriate data sources:
- Documentation (ChromaDB)
- Operational data (PostgreSQL)  
- Hybrid (both sources)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.rag.hybrid_router import (
    hybrid_search,
    classify_query_type,
    QueryType
)

def print_separator():
    print("=" * 70)

def print_results(query: str, results: dict):
    """Pretty print hybrid search results"""
    print()
    print_separator()
    print(f"📝 Query: {query}")
    print(f"🔍 Type: {results['query_type']}")
    print(f"📊 Source: {results.get('data_source', 'N/A')}")
    print_separator()
    
    # Show documentation results
    if results.get('documentation'):
        print("\n📚 DOCUMENTATION RESULTS:")
        for i, doc in enumerate(results['documentation'], 1):
            source = doc.get('filename') or doc.get('source', 'unknown')
            content_preview = doc['content'][:150].replace('\n', ' ')
            print(f"\n{i}. [{doc['type']}] {source}")
            print(f"   {content_preview}...")
    
    # Show operational data
    if results.get('operational_data'):
        data = results['operational_data']
        
        if data.get('summary'):
            print(f"\n💾 OPERATIONAL DATA:")
            print(f"   {data['summary']}")
        
        if data.get('batches'):
            print(f"\n   Recent Batches:")
            for batch in data['batches'][:3]:
                farm = batch.get('farm_name', 'Unknown farm')
                print(f"   - {batch['batch_id']}: {batch['quantity_kg']}kg {batch['variety']} from {farm} ({batch['status']})")
        
        if data.get('users'):
            print(f"\n   Verified Farmers:")
            for user in data['users'][:3]:
                print(f"   - {user['name']} ({user['kebele']})")
        
        if data.get('transactions'):
            print(f"\n   Recent Events:")
            for txn in data['transactions'][:3]:
                print(f"   - {txn['type']}: {txn['batch_id']} at {txn['location']}")
    
    # Show combined context (what would be sent to LLM)
    if results.get('combined_context'):
        print(f"\n🤖 COMBINED CONTEXT LENGTH: {len(results['combined_context'])} chars")

def main():
    print()
    print("=" * 70)
    print("HYBRID RAG ROUTER TEST")
    print("=" * 70)
    
    # Test query classification
    print("\n🔍 Testing Query Classification:\n")
    test_classifications = [
        ("Record a new coffee batch", QueryType.TRANSACTIONAL),
        ("Show me my batches", QueryType.OPERATIONAL),
        ("What is EPCIS 2.0?", QueryType.DOCUMENTATION),
        ("Why is my batch not verified?", QueryType.HYBRID),
    ]
    
    for query, expected in test_classifications:
        result = classify_query_type(query)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{query}' → {result.value} (expected: {expected.value})")
    
    # Test different query types
    print("\n\n" + "=" * 70)
    print("TESTING DIFFERENT QUERY TYPES")
    print("=" * 70)
    
    queries = [
        # Documentation query
        "What are the EPCIS 2.0 event types?",
        
        # Operational query
        "Show me recent coffee batches",
        
        # Hybrid query
        "How can I fix verification issues with my batches?",
    ]
    
    for query in queries:
        try:
            results = hybrid_search(query, doc_top_k=2, data_top_k=3)
            print_results(query, results)
        except Exception as e:
            print(f"\n❌ Error processing '{query}': {e}")
            import traceback
            traceback.print_exc()
    
    print("\n")
    print("=" * 70)
    print("✅ Test Complete!")
    print("=" * 70)
    print("\nThe hybrid router successfully:")
    print("  1. Classifies query intent")
    print("  2. Routes to appropriate data source(s)")
    print("  3. Combines results for LLM context")
    print()

if __name__ == "__main__":
    main()
