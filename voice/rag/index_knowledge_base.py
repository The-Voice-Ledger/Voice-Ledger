#!/usr/bin/env python3
"""
RAG Knowledge Base Indexer

Index all documentation and research papers for RAG-enhanced conversational AI.

Usage:
    python voice/rag/index_knowledge_base.py [--force-reindex]

Lab 18: RAG-Enhanced Conversational AI
Date: December 24, 2025
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from voice.rag.indexer import index_all_documents, get_index_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Index Voice Ledger documentation and research papers for RAG"
    )
    parser.add_argument(
        '--force-reindex',
        action='store_true',
        help='Delete existing index and rebuild from scratch'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Show index statistics without indexing'
    )
    
    args = parser.parse_args()
    
    try:
        if args.stats_only:
            logger.info("Fetching knowledge base statistics...")
            stats = get_index_stats()
            
            if stats.get('indexed'):
                print("\n=== Knowledge Base Statistics ===")
                print(f"Total chunks: {stats['total_chunks']}")
                print(f"Document types: {', '.join(stats['document_types'])}")
                print(f"Database path: {stats['database_path']}")
            else:
                print("\n❌ Knowledge base not indexed yet.")
                print(f"Error: {stats.get('error', 'Unknown')}")
            
            return
        
        logger.info("Starting knowledge base indexing...")
        logger.info(f"Force reindex: {args.force_reindex}")
        
        result = index_all_documents(force_reindex=args.force_reindex)
        
        if result['status'] == 'success':
            print("\n✅ Indexing completed successfully!")
            print(f"\nIndexed Documents:")
            print(f"  • Markdown files: {result['markdown_chunks']} chunks")
            print(f"  • PDF files: {result['pdf_chunks']} chunks")
            print(f"  • Total: {result['total_chunks']} chunks")
            print(f"\nDatabase: {result['database_path']}")
            print("\n🎉 RAG-enhanced conversational AI is ready!")
            
        elif result['status'] == 'already_indexed':
            print("\n✅ Knowledge base already indexed!")
            print(f"Existing documents: {result['existing_count']} chunks")
            print(f"Database: {result.get('database_path', 'N/A')}")
            print("\nUse --force-reindex to rebuild the index.")
            
        else:
            print(f"\n❌ Indexing failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Indexing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
