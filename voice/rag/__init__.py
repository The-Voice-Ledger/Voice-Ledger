"""
RAG (Retrieval-Augmented Generation) Module

Provides knowledge retrieval from documentation and research papers
to enhance conversational AI responses with accurate, grounded information.

Lab 18: RAG-Enhanced Conversational AI
Date: December 24, 2025
"""

from .retriever import search_knowledge_base, classify_query
from .indexer import index_all_documents, get_index_stats
from .hybrid_router import hybrid_search, classify_query_type, QueryType

# Conversational AI integration functions
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def enhance_query_with_rag(
    query: str, 
    base_prompt: str, 
    user_id: Optional[int] = None,
    max_context_tokens: int = 2000
) -> str:
    """
    Enhance system prompt with RAG-retrieved context.
    
    Args:
        query: User's question/command
        base_prompt: Base system prompt
        user_id: Optional user ID for personalized data
        max_context_tokens: Maximum tokens for context (approx 4 chars = 1 token)
    
    Returns:
        Enhanced system prompt with relevant context
    """
    try:
        # Get query type
        query_type = classify_query_type(query)
        
        # Don't add RAG for pure transactional commands
        if query_type == QueryType.TRANSACTIONAL:
            return base_prompt
        
        # Perform hybrid search
        results = hybrid_search(
            query=query,
            user_id=user_id,
            doc_top_k=3,
            data_top_k=5
        )
        
        # Get combined context
        context = results.get('combined_context', '')
        
        if not context:
            return base_prompt
        
        # Limit context size (approximate tokens)
        max_chars = max_context_tokens * 4
        if len(context) > max_chars:
            context = context[:max_chars] + "\n... [context truncated]"
        
        # Build enhanced prompt - inject RAG context as reference material
        # Key: Context informs response CONTENT, not response FORMAT
        enhanced_prompt = f"""{base_prompt}

=== KNOWLEDGE BASE REFERENCE ===
The following information from our documentation and codebase is provided as REFERENCE MATERIAL to help you answer the user's query. Use this to inform your response content, but DO NOT change your response format:

{context}

=== END REFERENCE ===

CRITICAL REMINDER: Your response MUST still be in the EXACT JSON format specified above. Do NOT provide prose or explanatory text. The retrieved reference material above should inform the CONTENT of your JSON response (specifically the "message_text" and "message_spoken" fields), but you MUST maintain the JSON structure.

Example of correct format when answering with retrieved context:
{{
  "message_text": "Based on our documentation: [answer using context]",
  "message_spoken": "Based on our documentation: [answer using context]",
  "ready_to_execute": false
}}

DO NOT return prose. DO NOT return markdown. ONLY return valid JSON.
"""
        
        logger.info(f"Enhanced prompt with {len(context)} chars of RAG context (query type: {query_type.value})")
        return enhanced_prompt
        
    except Exception as e:
        logger.error(f"RAG enhancement error: {e}")
        return base_prompt


__all__ = [
    'search_knowledge_base',
    'classify_query',
    'index_all_documents',
    'get_index_stats',
    'hybrid_search',
    'enhance_query_with_rag',
]
