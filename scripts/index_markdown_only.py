#!/usr/bin/env python3
"""
Index Markdown Only

Quick indexing of just markdown documentation (no PDFs).
Useful for testing RAG without processing large PDF files.

Usage:
    python scripts/index_markdown_only.py
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.rag.indexer import index_markdown_files, get_index_stats
import chromadb
from chromadb.config import Settings
from voice.rag.config import CHROMA_DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("\n=== Indexing Markdown Documentation Only ===\n")
    print("This is a quick test - PDFs will not be indexed.")
    print("For full indexing, use: python voice/rag/index_knowledge_base.py\n")
    
    try:
        # Initialize ChromaDB
        client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get collection
        collection_name = "voice_ledger_knowledge"
        
        try:
            # Try to get existing collection
            collection = client.get_collection(name=collection_name)
            existing_count = collection.count()
            print(f"Found existing collection with {existing_count} documents")
            
            response = input("\nDelete and rebuild? (y/N): ")
            if response.lower() == 'y':
                client.delete_collection(name=collection_name)
                print("Deleted existing collection")
                collection = client.create_collection(name=collection_name)
            else:
                print("Keeping existing collection")
        except:
            # Create new collection
            collection = client.create_collection(name=collection_name)
            print("Created new collection")
        
        # Index markdown files only
        print("\nIndexing markdown files...")
        markdown_chunks = index_markdown_files(collection, max_file_size_mb=5)
        
        print(f"\n✅ Indexing completed!")
        print(f"   Markdown chunks: {markdown_chunks}")
        print(f"   Database: {CHROMA_DB_PATH}")
        
        # Show stats
        stats = get_index_stats()
        if stats['indexed']:
            print(f"\nTotal documents in knowledge base: {stats['total_chunks']}")
        
        print("\n🎉 You can now test RAG with: python scripts/test_rag_simple.py\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Indexing interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
