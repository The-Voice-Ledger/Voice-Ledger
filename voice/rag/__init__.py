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
        
        # For DOCUMENTATION queries, use a knowledge-focused prompt instead of operational prompt
        if query_type == QueryType.DOCUMENTATION:
            doc_prompt = f"""You are a knowledgeable assistant helping Ethiopian coffee farmers and supply chain workers understand their system.

=== YOUR KNOWLEDGE (USE THESE SPECIFIC DETAILS) ===
{context}
=== END KNOWLEDGE ===

User's question: {query}

CRITICAL INSTRUCTIONS:
- The information above contains SPECIFIC TECHNICAL DETAILS about how the system actually works
- You MUST use these specific details in your answer (exact process steps, specific technologies like "Telegram deep link", "QR code", specific field names, etc.)
- DO NOT give generic, vague answers - use the EXACT implementation details from your knowledge above
- Present these details as if you know them directly - NEVER cite sources
- NEVER say: "according to...", "the documentation shows...", "as per Lab X", "based on the files"
- If your knowledge mentions specific technologies/steps (e.g., "Telegram bot", "verification token", "QR code", "48 hours", "cooperative manager"), USE THOSE EXACT DETAILS
- Be specific and technical where appropriate, but explain in simple terms

BAD (generic): "The verification process involves cross-checking with records and adding a digital signature..."
GOOD (specific): "The verification process works like this: When you create a batch, the system generates a QR code with a Telegram deep link. The cooperative manager scans it, which opens the Telegram bot and authenticates them. They physically inspect your coffee, confirm the quantity, and click verify. This creates a credential signed by the cooperative that proves your batch is authentic."

Response format (valid JSON only):
{{
  "message_text": "[Specific, detailed answer using exact information from your knowledge]",
  "message_spoken": "[Same specific answer in natural spoken form]",
  "ready_to_execute": false
}}

Answer with SPECIFIC DETAILS from your knowledge:"""
            
            logger.info(f"Using documentation-focused prompt with {len(context)} chars of RAG context")
            return doc_prompt
        
        # For HYBRID queries, enhance the base prompt with context
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
