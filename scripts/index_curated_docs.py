#!/usr/bin/env python3
"""
Index Curated Documentation to ChromaDB Cloud

Indexes the 29 curated markdown files to ChromaDB Cloud.
Uses the CloudClient configuration from .env
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.rag.config import get_chroma_client
from voice.rag.indexer import index_markdown_files

# Import ChromaDB's OpenAI embedding function
import chromadb.utils.embedding_functions as embedding_functions

def main():
    """Index curated documentation files"""
    print("=" * 60)
    print("Indexing Curated Documentation to ChromaDB Cloud")
    print("=" * 60)
    print()
    
    # Get ChromaDB client (automatically uses cloud or local based on .env)
    try:
        client = get_chroma_client()
        print("✅ Connected to ChromaDB")
        print()
    except Exception as e:
        print(f"❌ Failed to connect to ChromaDB: {e}")
        return 1
    
    # Get or create collection with OpenAI embeddings (no local model download)
    collection_name = "voice_ledger_docs"
    try:
        # Delete existing collection if it exists with wrong embedding function
        try:
            client.delete_collection(name=collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except:
            pass  # Collection doesn't exist, that's fine
        
        # Use OpenAI for embeddings (no local model, no OOM)
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
        
        collection = client.create_collection(
            name=collection_name,
            embedding_function=openai_ef,
            metadata={"description": "Voice Ledger documentation - Labs 1-17 + key guides"}
        )
        print(f"✅ Created collection: {collection_name}")
        print("✅ Using OpenAI embeddings (no local model)")
        print()
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")
        return 1
    
    # Index markdown files (29 curated files, batch size 1 to avoid OOM)
    try:
        print("Starting indexing (this may take a few minutes)...")
        print("Processing 1 file at a time to avoid memory issues...")
        print()
        indexed_count = index_markdown_files(
            collection=collection,
            max_file_size_mb=5,  # Skip files larger than 5 MB
            batch_size=1  # Process 1 file at a time (slower but safer)
        )
        print()
        print("=" * 60)
        print(f"🎉 Successfully indexed {indexed_count} documents!")
        print("=" * 60)
        print()
        print("You can now use RAG queries in the voice UI.")
        return 0
    except Exception as e:
        print()
        print(f"❌ Indexing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
