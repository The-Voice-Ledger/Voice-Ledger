"""Test RAG classification fix"""
import sys
sys.path.insert(0, '.')

from voice.rag.hybrid_router import classify_query_type, QueryType

# Test queries
operational_query = "I bought 50 kilograms of Sidama coffee"
documentation_query = "What are the types of EPCIS events?"

print("Testing query classification...")
print()

print(f"Operational query: '{operational_query}'")
op_type = classify_query_type(operational_query)
print(f"Classification: {op_type}")
print(f"Type: {type(op_type)}")
print(f"Is TRANSACTIONAL: {op_type == QueryType.TRANSACTIONAL}")
print(f"Is string 'TRANSACTIONAL': {op_type == 'TRANSACTIONAL'}")
print()

print(f"Documentation query: '{documentation_query}'")
doc_type = classify_query_type(documentation_query)
print(f"Classification: {doc_type}")
print(f"Type: {type(doc_type)}")
print(f"Is DOCUMENTATION: {doc_type == QueryType.DOCUMENTATION}")
print(f"Is string 'DOCUMENTATION': {doc_type == 'DOCUMENTATION'}")
print(f"In [QueryType.DOCUMENTATION, QueryType.HYBRID]: {doc_type in [QueryType.DOCUMENTATION, QueryType.HYBRID]}")
