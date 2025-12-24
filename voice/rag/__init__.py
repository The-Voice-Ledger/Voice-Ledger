"""
RAG (Retrieval-Augmented Generation) Module

Provides knowledge retrieval from documentation and research papers
to enhance conversational AI responses with accurate, grounded information.

Lab 18: RAG-Enhanced Conversational AI
Date: December 24, 2025
"""

from .retriever import search_knowledge_base, classify_query
from .indexer import index_all_documents, get_index_stats

__all__ = [
    'search_knowledge_base',
    'classify_query',
    'index_all_documents',
    'get_index_stats',
]
