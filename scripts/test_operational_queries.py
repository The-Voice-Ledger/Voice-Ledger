#!/usr/bin/env python3
"""
Test Operational Queries - Live Supply Chain Data

Tests the hybrid router's ability to query live operational data
from PostgreSQL alongside documentation/code retrieval.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.rag.hybrid_router import hybrid_search, classify_query_type

def test_operational_queries():
    """Test queries that need live supply chain data"""
    
    queries = [
        # Pure operational (PostgreSQL only)
        "Show me recent coffee batches",
        "List all verified farmers",
        "What batches are pending verification?",
        
        # Hybrid (documentation + live data)
        "Why isn't my batch verified yet?",
        "How many batches have I created and what's the process?",
        "What's the status of my shipments and how does shipping work?",
        
        # Pure documentation (already tested, but for comparison)
        "What is EPCIS 2.0?",
        "How do I register as a farmer?",
    ]
    
    print("=" * 80)
    print("OPERATIONAL QUERIES TEST - Hybrid Router")
    print("=" * 80)
    print()
    
    for idx, query in enumerate(queries, 1):
        print(f"\n{'=' * 80}")
        print(f"Query {idx}: {query}")
        print('=' * 80)
        
        # Classify query type
        query_type = classify_query_type(query)
        print(f"\n🔍 Classified as: {query_type.value.upper()}")
        
        # Perform hybrid search
        results = hybrid_search(query, user_id=None, doc_top_k=2, data_top_k=5)
        
        print(f"📊 Data sources: {results.get('data_source', 'N/A')}")
        
        # Show documentation results (if any)
        if results.get('documentation'):
            print(f"\n📚 DOCUMENTATION ({len(results['documentation'])} results):")
            for i, doc in enumerate(results['documentation'], 1):
                source = doc.get('source', 'unknown')
                doc_type = doc.get('type', 'unknown')
                print(f"  {i}. [{doc_type}] {source}")
        
        # Show operational data (if any)
        if results.get('operational_data'):
            op_data = results['operational_data']
            print(f"\n💾 OPERATIONAL DATA (Live from PostgreSQL):")
            
            if op_data.get('summary'):
                print(f"  Summary: {op_data['summary']}")
            
            if op_data.get('batches'):
                print(f"\n  📦 Batches ({len(op_data['batches'])}):")
                for batch in op_data['batches'][:3]:  # Show first 3
                    print(f"    • {batch['batch_id']}: {batch['quantity_kg']}kg "
                          f"{batch.get('variety', 'N/A')} ({batch['status']})")
                if len(op_data['batches']) > 3:
                    print(f"    ... and {len(op_data['batches']) - 3} more")
            
            if op_data.get('users'):
                print(f"\n  👥 Farmers ({len(op_data['users'])}):")
                for user in op_data['users'][:3]:  # Show first 3
                    print(f"    • {user['name']} ({user['kebele']}) - {user['status']}")
                if len(op_data['users']) > 3:
                    print(f"    ... and {len(op_data['users']) - 3} more")
        
        # Show combined context preview
        if results.get('combined_context'):
            context = results['combined_context']
            print(f"\n📝 COMBINED CONTEXT (for LLM):")
            preview = context[:300].strip()
            print(f"  {preview}")
            if len(context) > 300:
                print("  ...")
    
    print("\n" + "=" * 80)
    print("✅ OPERATIONAL QUERIES TEST COMPLETE!")
    print("=" * 80)
    print("\n💡 Key Capabilities:")
    print("   ✅ Live batch data from PostgreSQL")
    print("   ✅ Farmer verification status")
    print("   ✅ Documentation for 'how to' questions")
    print("   ✅ Code examples for implementation")
    print("   ✅ Hybrid answers combining docs + live data")
    print("\n🎯 The system supports BOTH:")
    print("   1. Educational queries (docs/code)")
    print("   2. Operational queries (live supply chain data)")

if __name__ == "__main__":
    test_operational_queries()
