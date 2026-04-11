"""
Hybrid RAG Router

Intelligently routes queries to appropriate data sources:
- ChromaDB: Documentation, technical specs, research papers
- PostgreSQL: Live operational data (batches, transactions, users)

Combines results for comprehensive context-aware responses.
"""

import logging
import os
from typing import List, Dict, Any, Literal, Optional
from enum import Enum

try:
    import chromadb
    import chromadb.utils.embedding_functions as embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("chromadb not installed. RAG features will be disabled.")

from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import (
    EMBEDDING_MODEL,
    DEFAULT_TOP_K,
    get_chroma_client,
)

# Import database session
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database.connection import SessionLocal

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class QueryType(Enum):
    """Types of queries that require different routing strategies"""
    TRANSACTIONAL = "transactional"  # Execute command (record, ship, etc.)
    OPERATIONAL = "operational"      # Query live data (my batches, status, etc.)
    DOCUMENTATION = "documentation"  # Search docs/guides (how to, what is)
    HYBRID = "hybrid"                # Needs both docs + live data


class DataSource(Enum):
    """Available data sources for retrieval"""
    CHROMADB = "chromadb"
    POSTGRESQL = "postgresql"
    BOTH = "both"


def classify_query_type(query: str) -> QueryType:
    """
    Classify user query to determine routing strategy.
    
    Args:
        query: User's question or statement
        
    Returns:
        QueryType enum indicating how to handle the query
    """
    query_lower = query.lower()
    
    # Transactional indicators (execute command)
    transactional_indicators = [
        "record", "ship", "receive", "pack", "unpack", "split",
        "create batch", "new batch", "harvested", "roasted",
        "send", "deliver", "transform", "register", "verify"
    ]
    if any(ind in query_lower for ind in transactional_indicators):
        return QueryType.TRANSACTIONAL
    
    # Operational indicators (query live data)
    operational_indicators = [
        "my batches", "my transactions", "show me", "list",
        "status of", "what's the status", "find batch",
        "who verified", "when was", "where is",
        "how many batches", "total quantity", "recent",
        "last transaction", "pending", "verified farmers"
    ]
    if any(ind in query_lower for ind in operational_indicators):
        return QueryType.OPERATIONAL
    
    # Documentation indicators (search guides/specs)
    documentation_indicators = [
        "how to", "how do i", "what is", "explain",
        "guide", "tutorial", "specification", "standard",
        "epcis", "gs1", "blockchain", "eudr",
        "what does", "why", "when should", "best practice"
    ]
    if any(ind in query_lower for ind in documentation_indicators):
        return QueryType.DOCUMENTATION
    
    # Hybrid indicators (needs both sources)
    hybrid_indicators = [
        "why is my", "how can i fix", "what's wrong with",
        "help me understand", "explain my", "troubleshoot"
    ]
    if any(ind in query_lower for ind in hybrid_indicators):
        return QueryType.HYBRID
    
    # Default to documentation for questions
    if "?" in query:
        return QueryType.DOCUMENTATION
    
    return QueryType.TRANSACTIONAL


def search_documentation(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Search ChromaDB for relevant documentation.
    
    Args:
        query: Search query
        top_k: Number of results to return
        include_metadata: Whether to include source metadata
        
    Returns:
        List of relevant document chunks with metadata
    """
    if not CHROMADB_AVAILABLE:
        logger.warning("ChromaDB not available. Returning empty results.")
        return []
    
    # Try cache first (RAG query optimization)
    try:
        from voice.cache.rag_cache import get_cached_rag_results, set_cached_rag_results
        cached = get_cached_rag_results(query, query_type="documentation", top_k=top_k)
        if cached is not None and len(cached) > 0:
            return cached
    except Exception as cache_error:
        logger.debug(f"RAG cache check failed (non-fatal): {cache_error}")
        # Continue with normal ChromaDB search
    
    try:
        # Get ChromaDB client
        print(f"DEBUG search_documentation: Getting ChromaDB client for query: '{query}'")
        chroma_client = get_chroma_client()
        print(f"DEBUG search_documentation: Got client: {type(chroma_client).__name__}")
        
        # Get collection with OpenAI embeddings
        print(f"DEBUG search_documentation: Creating OpenAI embedding function")
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=EMBEDDING_MODEL
        )
        
        print(f"DEBUG search_documentation: Getting collection 'voice_ledger_docs_v2'")
        collection = chroma_client.get_collection(
            name="voice_ledger_docs_v2",
            embedding_function=openai_ef
        )
        print(f"DEBUG search_documentation: Successfully got collection")
        
        # Search
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        # Format results
        documents = []
        if results['documents'] and results['documents'][0]:
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                documents.append({
                    'content': doc,
                    'source': metadata.get('source', 'unknown'),
                    'type': metadata.get('type', 'unknown'),
                    'filename': metadata.get('filename', ''),
                })
        
        # Store in cache for future lookups
        set_cached_rag_results(query, query_type="documentation", top_k=top_k, results=documents)
        return documents
        
    except Exception as e:
        logger.error(f"ChromaDB search error: {e}")
        return []


def query_operational_data(
    query: str,
    user_id: Optional[int] = None,
    top_k: int = 10
) -> Dict[str, Any]:
    """
    Query PostgreSQL for live operational data.
    
    Args:
        query: Natural language query
        user_id: Optional user ID to filter results
        top_k: Maximum number of records to return
        
    Returns:
        Dictionary with query results and metadata
    """
    db = SessionLocal()
    results = {
        'batches': [],
        'transactions': [],
        'users': [],
        'summary': ''
    }
    
    try:
        query_lower = query.lower()
        
        # Query batches
        if any(word in query_lower for word in ['batch', 'batches', 'coffee', 'harvest']):
            batch_query = text("""
                SELECT 
                    batch_id,
                    farm_name,
                    quantity_kg,
                    variety,
                    harvest_date,
                    status,
                    token_id
                FROM coffee_batches
                WHERE (:user_id IS NULL OR farmer_id = :user_id)
                ORDER BY harvest_date DESC
                LIMIT :limit
            """)
            
            batch_results = db.execute(
                batch_query,
                {"user_id": user_id, "limit": top_k}
            ).fetchall()
            
            results['batches'] = [
                {
                    'batch_id': row[0],
                    'farm_name': row[1],
                    'quantity_kg': float(row[2]) if row[2] else 0,
                    'variety': row[3],
                    'harvest_date': str(row[4]) if row[4] else None,
                    'status': row[5],
                    'token_id': row[6]
                }
                for row in batch_results
            ]
            
            if results['batches']:
                total_quantity = sum(b['quantity_kg'] for b in results['batches'])
                verified_count = sum(1 for b in results['batches'] if 'VERIFIED' in b['status'])
                results['summary'] = f"Found {len(results['batches'])} batches, {total_quantity}kg total, {verified_count} verified"
        
        # Query users/farmers
        if any(word in query_lower for word in ['farmer', 'farmers', 'user', 'verified', 'registered']):
            user_query = text("""
                SELECT 
                    id,
                    full_name,
                    phone_number,
                    kebele,
                    verification_status,
                    created_at
                FROM farmer_identities
                WHERE verification_status = 'approved'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            user_results = db.execute(user_query, {"limit": top_k}).fetchall()
            
            results['users'] = [
                {
                    'id': row[0],
                    'name': row[1],
                    'phone': row[2],
                    'kebele': row[3],
                    'status': row[4],
                    'registered': str(row[5]) if row[5] else None
                }
                for row in user_results
            ]
            
            if results['users'] and not results['summary']:
                results['summary'] = f"Found {len(results['users'])} verified farmers"
        
        # Query transactions/events
        if any(word in query_lower for word in ['transaction', 'event', 'ship', 'receive', 'recent']):
            event_query = text("""
                SELECT 
                    event_type,
                    batch_id,
                    event_time,
                    biz_location
                FROM epcis_events
                ORDER BY event_time DESC
                LIMIT :limit
            """)
            
            event_results = db.execute(event_query, {"limit": top_k}).fetchall()
            
            results['transactions'] = [
                {
                    'type': row[0],
                    'batch_id': row[1],
                    'time': str(row[2]) if row[2] else None,
                    'location': row[3]  # biz_location (GLN)
                }
                for row in event_results
            ]
            
            if results['transactions'] and not results['summary']:
                results['summary'] = f"Found {len(results['transactions'])} recent events"
        
    except Exception as e:
        logger.error(f"PostgreSQL query error: {e}")
        results['error'] = str(e)
    finally:
        db.close()
    
    return results


def hybrid_search(
    query: str,
    user_id: Optional[int] = None,
    doc_top_k: int = 3,
    data_top_k: int = 5
) -> Dict[str, Any]:
    """
    Perform hybrid search across both ChromaDB and PostgreSQL.
    
    Args:
        query: Natural language query
        user_id: Optional user ID for personalized results
        doc_top_k: Number of documentation results
        data_top_k: Number of operational data results
        
    Returns:
        Combined results from both sources
    """
    # Classify query
    query_type = classify_query_type(query)
    
    results = {
        'query': query,
        'query_type': query_type.value,
        'documentation': [],
        'operational_data': {},
        'combined_context': ''
    }
    
    # Route based on query type
    if query_type == QueryType.TRANSACTIONAL:
        # Don't retrieve anything, let existing command handler execute
        results['action'] = 'execute_command'
        return results
    
    elif query_type == QueryType.DOCUMENTATION:
        # Only search documentation
        results['documentation'] = search_documentation(query, top_k=doc_top_k)
        results['data_source'] = DataSource.CHROMADB.value
    
    elif query_type == QueryType.OPERATIONAL:
        # Only query live data
        results['operational_data'] = query_operational_data(query, user_id, top_k=data_top_k)
        results['data_source'] = DataSource.POSTGRESQL.value
    
    elif query_type == QueryType.HYBRID:
        # Query both sources
        results['documentation'] = search_documentation(query, top_k=doc_top_k)
        results['operational_data'] = query_operational_data(query, user_id, top_k=data_top_k)
        results['data_source'] = DataSource.BOTH.value
    
    # Format combined context for LLM
    results['combined_context'] = format_combined_context(
        documentation=results['documentation'],
        operational_data=results['operational_data']
    )
    
    return results


def format_combined_context(
    documentation: List[Dict[str, Any]],
    operational_data: Dict[str, Any]
) -> str:
    """
    Format retrieved data into context string for LLM prompt.
    
    Args:
        documentation: Results from ChromaDB
        operational_data: Results from PostgreSQL
        
    Returns:
        Formatted context string
    """
    context_parts = []
    
    # Add documentation context
    if documentation:
        context_parts.append("=== DOCUMENTATION CONTEXT ===\n")
        for i, doc in enumerate(documentation, 1):
            source = doc.get('filename') or doc.get('source', 'Unknown')
            content = doc['content'][:500]  # Truncate long content
            context_parts.append(f"{i}. [{source}]\n{content}\n")
    
    # Add operational data context
    if operational_data:
        context_parts.append("\n=== LIVE OPERATIONAL DATA ===\n")
        
        if operational_data.get('summary'):
            context_parts.append(f"Summary: {operational_data['summary']}\n\n")
        
        if operational_data.get('batches'):
            context_parts.append("Recent Batches:\n")
            for batch in operational_data['batches'][:5]:
                context_parts.append(
                    f"- {batch['batch_id']}: {batch['quantity_kg']}kg {batch['variety']} "
                    f"from {batch.get('farm_name', 'Unknown')} ({batch['status']})\n"
                )
        
        if operational_data.get('users'):
            context_parts.append("\nVerified Farmers:\n")
            for user in operational_data['users'][:5]:
                context_parts.append(
                    f"- {user['name']} ({user['phone']}) - {user['kebele']}\n"
                )
        
        if operational_data.get('transactions'):
            context_parts.append("\nRecent Events:\n")
            for txn in operational_data['transactions'][:5]:
                context_parts.append(
                    f"- {txn['type']}: {txn['batch_id']} at {txn['location']}\n"
                )
    
    return "".join(context_parts)


def check_knowledge_base() -> bool:
    """
    Health check for RAG system.
    
    Returns:
        True if both ChromaDB and PostgreSQL are accessible
    """
    chromadb_ok = False
    postgresql_ok = False
    
    # Check ChromaDB
    if CHROMADB_AVAILABLE:
        try:
            client = get_chroma_client()
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name=EMBEDDING_MODEL
            )
            collection = client.get_collection(
                name="voice_ledger_docs_v2",
                embedding_function=openai_ef
            )
            count = collection.count()
            chromadb_ok = count > 0
            logger.info(f"ChromaDB health check: {count} documents")
        except Exception as e:
            logger.warning(f"ChromaDB health check failed: {e}")
    
    # Check PostgreSQL
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT COUNT(*) FROM coffee_batches")).scalar()
        postgresql_ok = result is not None
        logger.info(f"PostgreSQL health check: {result} batches")
        db.close()
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
    
    return chromadb_ok and postgresql_ok
