"""
Multi-Turn RAG Query Handler

Enables multi-turn conversations for documentation queries by:
1. Detecting follow-up questions
2. Using previous context to refine queries
3. Maintaining conversation history for coherent responses

Example:
    User: "What are EPCIS events?"
    Bot: [Explains EPCIS events]
    User: "Show me examples"  ← Detected as follow-up
    Bot: [Shows EPCIS event code examples, building on previous context]
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio

from voice.integrations.conversation_manager import ConversationManager
from voice.rag.retriever import search_knowledge_base

logger = logging.getLogger(__name__)


class MultiTurnRAG:
    """
    Multi-turn RAG query processor with context awareness.
    
    Handles:
    - New documentation queries (fresh RAG search)
    - Follow-up questions (reuse previous context)
    - Context expiration (return to fresh queries after timeout)
    """
    
    @staticmethod
    async def process_rag_query(
        user_id: int,
        query: str,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Process RAG query with multi-turn context awareness.
        
        Args:
            user_id: Database user ID
            query: User's query text
            language: Language code ('en' or 'am')
            
        Returns:
            Dict with:
                - 'message': Response text
                - 'sources': List of source documents
                - 'is_follow_up': Bool indicating if this was a follow-up
        """
        # Check if this is a follow-up question
        is_follow_up = ConversationManager.is_follow_up_question(user_id, query)
        
        if is_follow_up:
            logger.info(f"Processing follow-up query for user {user_id}: {query}")
            result = await MultiTurnRAG._handle_follow_up(user_id, query, language)
        else:
            logger.info(f"Processing new RAG query for user {user_id}: {query}")
            result = await MultiTurnRAG._handle_new_query(user_id, query, language)
        
        result['is_follow_up'] = is_follow_up
        return result
    
    @staticmethod
    async def _handle_new_query(
        user_id: int,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Handle new RAG query (not a follow-up).
        
        Performs fresh RAG search and stores context for potential follow-ups.
        
        Args:
            user_id: Database user ID
            query: User's query
            language: Language code
            
        Returns:
            Dict with message and sources
        """
        # Perform RAG search
        try:
            rag_results = search_knowledge_base(
                query=query,
                query_type="documentation",
                top_k=5
            )
            
            if not rag_results:
                return {
                    'message': (
                        "I couldn't find relevant information. "
                        "Try rephrasing your question or ask about:\n"
                        "- EPCIS events\n"
                        "- GS1 identifiers\n"
                        "- Blockchain anchoring\n"
                        "- Digital Product Passports"
                    ),
                    'sources': []
                }
            
            # Extract context and sources
            retrieved_context = "\n\n".join([
                f"Source {i+1}: {result['text']}"
                for i, result in enumerate(rag_results)
            ])
            
            sources = [
                {
                    'file': result.get('metadata', {}).get('source', 'Unknown'),
                    'score': result.get('score', 0.0)
                }
                for result in rag_results
            ]
            
            # Generate response using LLM (if available) or return raw context
            response_message = await MultiTurnRAG._generate_response(
                query=query,
                context=retrieved_context,
                language=language,
                is_follow_up=False
            )
            
            # Store RAG context for potential follow-ups
            ConversationManager.store_rag_context(
                user_id=user_id,
                query=query,
                query_type='documentation',
                retrieved_context=retrieved_context,
                sources=sources
            )
            
            logger.info(
                f"RAG search completed for user {user_id}: "
                f"{len(rag_results)} results, {len(sources)} sources"
            )
            
            return {
                'message': response_message,
                'sources': sources
            }
            
        except Exception as e:
            logger.error(f"Error in RAG search: {e}", exc_info=True)
            return {
                'message': (
                    "Sorry, I encountered an error searching the knowledge base. "
                    "Please try again or rephrase your question."
                ),
                'sources': []
            }
    
    @staticmethod
    async def _handle_follow_up(
        user_id: int,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Handle follow-up query using previous RAG context.
        
        Uses stored context to:
        1. Determine if new search is needed
        2. Refine query with previous context
        3. Generate coherent follow-up response
        
        Args:
            user_id: Database user ID
            query: Follow-up query
            language: Language code
            
        Returns:
            Dict with message and sources
        """
        # Get previous RAG context
        rag_context = ConversationManager.get_rag_context(user_id)
        
        if not rag_context:
            logger.warning(
                f"Follow-up detected but no RAG context for user {user_id}, "
                f"treating as new query"
            )
            return await MultiTurnRAG._handle_new_query(user_id, query, language)
        
        previous_query = rag_context.get('last_query', '')
        previous_context = rag_context.get('retrieved_context', '')
        previous_sources = rag_context.get('sources', [])
        
        # Determine if we need a new search or can use previous context
        needs_new_search = MultiTurnRAG._needs_new_search(query)
        
        if needs_new_search:
            logger.info(f"Follow-up requires new search for user {user_id}")
            
            # Refine query with previous context
            refined_query = f"{previous_query} {query}"
            
            # Perform new RAG search with refined query
            try:
                rag_results = search_knowledge_base(
                    query=refined_query,
                    query_type="documentation",
                    top_k=5
                )
                
                if rag_results:
                    retrieved_context = "\n\n".join([
                        f"Source {i+1}: {result['text']}"
                        for i, result in enumerate(rag_results)
                    ])
                    
                    sources = [
                        {
                            'file': result.get('metadata', {}).get('source', 'Unknown'),
                            'score': result.get('score', 0.0)
                        }
                        for result in rag_results
                    ]
                else:
                    # Fallback to previous context
                    retrieved_context = previous_context
                    sources = previous_sources
                    
            except Exception as e:
                logger.error(f"Error in follow-up RAG search: {e}")
                # Fallback to previous context
                retrieved_context = previous_context
                sources = previous_sources
        else:
            logger.info(f"Follow-up uses previous context for user {user_id}")
            # Reuse previous context
            retrieved_context = previous_context
            sources = previous_sources
        
        # Generate follow-up response
        response_message = await MultiTurnRAG._generate_response(
            query=query,
            context=retrieved_context,
            language=language,
            is_follow_up=True,
            previous_query=previous_query
        )
        
        # Update RAG context with new query
        ConversationManager.store_rag_context(
            user_id=user_id,
            query=query,  # Store current query as last query
            query_type='documentation',
            retrieved_context=retrieved_context,
            sources=sources
        )
        
        return {
            'message': response_message,
            'sources': sources
        }
    
    @staticmethod
    def _needs_new_search(follow_up_query: str) -> bool:
        """
        Determine if follow-up query needs a new RAG search.
        
        Queries like "show examples" or "explain more" can use previous context.
        Queries like "what about shipments" need new search.
        
        Args:
            follow_up_query: The follow-up query text
            
        Returns:
            True if new search needed, False if previous context sufficient
        """
        query_lower = follow_up_query.lower()
        
        # Queries that can use previous context (no new search needed)
        reuse_context_phrases = [
            'example', 'more detail', 'elaborate', 'explain', 'tell me more',
            'how do i', 'how to', 'show me', 'describe', 'clarify',
            'what does', 'what is', 'why',
            # Amharic
            'ምሳሌ', 'በዝርዝር'
        ]
        
        for phrase in reuse_context_phrases:
            if phrase in query_lower:
                return False  # Can reuse context
        
        # If query introduces new topic, need new search
        return True
    
    @staticmethod
    async def _generate_response(
        query: str,
        context: str,
        language: str,
        is_follow_up: bool,
        previous_query: Optional[str] = None
    ) -> str:
        """
        Generate response using LLM or format retrieved context.
        
        Args:
            query: User's query
            context: Retrieved context from RAG
            language: Language code ('en' or 'am')
            is_follow_up: Whether this is a follow-up question
            previous_query: Previous query if follow-up
            
        Returns:
            Formatted response message
        """
        try:
            # Use OpenAI for English, AddisAI for Amharic
            if language == 'am':
                from voice.integrations.amharic_conversation import call_addis_ai
                
                # Build prompt for Amharic LLM
                if is_follow_up and previous_query:
                    prompt = (
                        f"በመጀመሪያ ጥያቄ: {previous_query}\n"
                        f"ተከታይ ጥያቄ: {query}\n\n"
                        f"መረጃ:\n{context}\n\n"
                        f"መልስ ይስጡ:"
                    )
                else:
                    prompt = f"ጥያቄ: {query}\n\nመረጃ:\n{context}\n\nመልስ:"
                
                # Call AddisAI
                response = await call_addis_ai(prompt)
                return response.get('message', context[:500])
                
            else:  # English - use OpenAI
                from openai import OpenAI
                import os
                
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                
                # Build system prompt
                system_prompt = """You are a helpful assistant for the Voice Ledger coffee supply chain system.
Use the provided context to give clear, accurate answers. If the context doesn't contain the answer, say so."""
                
                # Build user prompt
                if is_follow_up and previous_query:
                    user_prompt = f"""Previous question: {previous_query}
Current question: {query}

Context:
{context}

Please provide a clear, concise answer based on the context."""
                else:
                    user_prompt = f"""Question: {query}

Context:
{context}

Please provide a clear, concise answer based on the context."""
                
                # Call OpenAI GPT-4
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                return response.choices[0].message.content.strip()
                    
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            # Fallback to returning context
            if len(context) > 1000:
                context = context[:1000] + "..."
            
            if is_follow_up:
                return f"Building on the previous topic:\n\n{context}"
            else:
                return context
