"""
Knowledge Base Retriever

Provides semantic search across documentation and research papers.
Classifies queries and retrieves relevant context for RAG.
"""

import logging
import os
from typing import List, Dict, Any, Literal

try:
    import chromadb
    from chromadb.config import Settings
    import chromadb.utils.embedding_functions as embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("chromadb not installed. RAG features will be disabled.")

from openai import OpenAI
from dotenv import load_dotenv

from .config import (
    CHROMA_DB_PATH,
    EMBEDDING_MODEL,
    DEFAULT_TOP_K,
    MIN_SIMILARITY_SCORE,
    TECHNICAL_KEYWORDS,
    DESIGN_KEYWORDS,
    HOWTO_KEYWORDS,
    get_chroma_client,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def classify_query(query: str) -> Literal["technical", "design", "howto", "transactional"]:
    """
    Classify user query into one of four categories.
    
    Args:
        query: User's question or statement
        
    Returns:
        Query type: "technical", "design", "howto", or "transactional"
    """
    query_lower = query.lower()
    
    # Check for transactional indicators (commands)
    transactional_indicators = [
        "record", "ship", "receive", "pack", "unpack", "split",
        "create batch", "new batch", "harvested", "roasted",
        "sent", "delivered", "transform"
    ]
    
    if any(ind in query_lower for ind in transactional_indicators):
        return "transactional"
    
    # Check for "how-to" questions
    if any(keyword in query_lower for keyword in HOWTO_KEYWORDS):
        return "howto"
    
    # Check for technical questions
    tech_score = sum(1 for keyword in TECHNICAL_KEYWORDS if keyword in query_lower)
    design_score = sum(1 for keyword in DESIGN_KEYWORDS if keyword in query_lower)
    
    if tech_score > design_score and tech_score > 0:
        return "technical"
    elif design_score > 0:
        return "design"
    
    # Default to howto for questions
    if "?" in query or query_lower.startswith(("what", "how", "why", "when", "where", "who")):
        return "howto"
    
    return "transactional"


def search_knowledge_base(
    query: str,
    query_type: str = None,
    top_k: int = DEFAULT_TOP_K,
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Search knowledge base for relevant context.
    
    Args:
        query: Search query
        query_type: Type of query (technical, design, howto, transactional)
        top_k: Number of results to return
        include_metadata: Whether to include source metadata
        
    Returns:
        List of relevant document chunks with metadata
    """
    if not CHROMADB_AVAILABLE:
        logger.warning("ChromaDB not available. Returning empty results.")
        return []
    
    try:
        # Initialize ChromaDB client (local or cloud based on config)
        chroma_client = get_chroma_client()
        
        # Get collection
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=EMBEDDING_MODEL
        )
        
        try:
            collection = chroma_client.get_collection(
                name="voice_ledger_docs_v2",
                embedding_function=openai_ef
            )
        except Exception as e:
            logger.warning(f"Knowledge base not indexed yet: {e}")
            return []
        
        # Auto-classify if not provided
        if query_type is None:
            query_type = classify_query(query)
        
        # Adjust retrieval strategy based on query type
        if query_type == "transactional":
            # Don't retrieve for transactional queries
            return []
        
        # Search with different filters based on query type
        where_filter = None
        if query_type == "technical":
            # Prioritize PDFs for technical questions
            where_filter = {"type": "pdf"}
            results_pdf = collection.query(
                query_texts=[query],
                n_results=min(top_k, 3),
                where=where_filter
            )
            # Also get some markdown results
            results_md = collection.query(
                query_texts=[query],
                n_results=min(top_k - len(results_pdf['documents'][0]), 2),
                where={"type": "markdown"}
            )
            # Combine results
            documents = results_pdf['documents'][0] + results_md['documents'][0]
            metadatas = results_pdf['metadatas'][0] + results_md['metadatas'][0]
            distances = results_pdf['distances'][0] + results_md['distances'][0]
        else:
            # For design and howto, search everything
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0]
        
        # Format results
        formatted_results = []
        for doc, metadata, distance in zip(documents, metadatas, distances):
            # Convert distance to similarity score (lower distance = higher similarity)
            similarity = 1 - distance  # ChromaDB uses L2 distance
            
            if similarity < MIN_SIMILARITY_SCORE:
                continue
            
            result = {
                "content": doc,
                "similarity": similarity,
                "distance": distance
            }
            
            if include_metadata:
                result["metadata"] = metadata
            
            formatted_results.append(result)
        
        logger.info(f"Retrieved {len(formatted_results)} relevant documents for query type '{query_type}'")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return []


def check_knowledge_base() -> bool:
    """
    Check if knowledge base is indexed (for Railway startup checks).
    
    Returns:
        True if knowledge base exists and has documents, False otherwise
    """
    if not CHROMADB_AVAILABLE:
        return False
    
    try:
        client = get_chroma_client()
        
        # Get collection with OpenAI embeddings
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=EMBEDDING_MODEL
        )
        
        collection = client.get_collection(
            name="voice_ledger_docs_v2",
            embedding_function=openai_ef
        )
        count = collection.count()
        return count > 0
    except:
        return False


def format_context_for_prompt(
    query: str,
    results: List[Dict[str, Any]],
    max_tokens: int = 2000
) -> str:
    """
    Format retrieved documents into context string for LLM prompt.
    
    Args:
        query: Original query
        results: Search results from search_knowledge_base()
        max_tokens: Maximum tokens for context (approximate)
        
    Returns:
        Formatted context string
    """
    if not results:
        return ""
    
    context_parts = [
        "=== RELEVANT KNOWLEDGE BASE CONTEXT ===\n",
        f"The following information was retrieved for the query: \"{query}\"\n\n"
    ]
    
    char_limit = max_tokens * 4  # Rough approximation: 1 token ≈ 4 chars
    current_chars = sum(len(p) for p in context_parts)
    
    for i, result in enumerate(results, 1):
        content = result['content']
        metadata = result.get('metadata', {})
        
        # Add source citation
        source = metadata.get('filename', 'Unknown')
        doc_type = metadata.get('type', 'document')
        
        chunk_text = (
            f"Source {i}: {source} ({doc_type})\n"
            f"{content}\n\n"
        )
        
        # Check if adding this chunk would exceed limit
        if current_chars + len(chunk_text) > char_limit:
            context_parts.append("... (additional context truncated)\n")
            break
        
        context_parts.append(chunk_text)
        current_chars += len(chunk_text)
    
    context_parts.append("=== END KNOWLEDGE BASE CONTEXT ===\n\n")
    
    return "".join(context_parts)


def enhance_query_with_rag(
    query: str,
    base_prompt: str,
    max_context_tokens: int = 2000
) -> str:
    """
    Enhance base system prompt with RAG-retrieved context.
    
    This is the main integration point for adding RAG to conversations.
    
    Args:
        query: User's query
        base_prompt: Original system prompt
        max_context_tokens: Maximum tokens for retrieved context
        
    Returns:
        Enhanced prompt with relevant context injected
    """
    # Classify query
    query_type = classify_query(query)
    
    # Don't use RAG for transactional queries
    if query_type == "transactional":
        return base_prompt
    
    # Search knowledge base
    results = search_knowledge_base(query, query_type=query_type)
    
    if not results:
        # No relevant context found, return original prompt
        return base_prompt
    
    # Format context
    context = format_context_for_prompt(query, results, max_tokens=max_context_tokens)
    
    # Inject context into prompt
    # Add context after the main instructions but before examples
    enhanced_prompt = base_prompt + "\n\n" + context + "\n\n" + """
USE THE ABOVE CONTEXT TO ANSWER QUESTIONS:
- If the user asks about EPCIS standards, GS1 specifications, or technical details, cite the relevant source
- If the user asks about design principles or socio-technical considerations, reference the research
- If the user asks how to do something, combine documentation with conversational guidance
- Always prefer factual information from the knowledge base over general knowledge
- If the context doesn't contain the answer, say so honestly and offer to help find it
"""
    
    return enhanced_prompt
