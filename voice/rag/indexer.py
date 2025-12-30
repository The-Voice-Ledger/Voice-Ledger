"""
Document Indexer

Indexes markdown documentation and PDF research papers into ChromaDB
for semantic search.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("chromadb not installed. RAG features will be disabled.")

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 not installed. PDF indexing will be disabled.")

from openai import OpenAI
from dotenv import load_dotenv

from .config import (
    DOCUMENTATION_DIR,
    RESEARCH_DIR,
    CHROMA_DB_PATH,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    get_chroma_client,
    CURATED_MARKDOWN_FILES,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client for embeddings
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Input text to chunk
        chunk_size: Target size per chunk (characters, rough approximation of tokens)
        overlap: Overlap between chunks (characters)
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < text_len:
            # Look for period, question mark, or exclamation mark
            sentence_end = text.rfind('.', start, end)
            if sentence_end == -1:
                sentence_end = text.rfind('?', start, end)
            if sentence_end == -1:
                sentence_end = text.rfind('!', start, end)
            if sentence_end != -1 and sentence_end > start:
                end = sentence_end + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap if end < text_len else text_len
    
    return chunks


def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text content
    """
    if not PYPDF2_AVAILABLE:
        logger.error("PyPDF2 not available. Cannot extract PDF text.")
        return ""
    
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for text chunks using OpenAI.
    
    Args:
        texts: List of text strings to embed
        
    Returns:
        List of embedding vectors
    """
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return []


def index_markdown_files(collection, max_file_size_mb: int = 5, batch_size: int = 3) -> int:
    """curated markdown files (only relevant, up-to-date documentation).
    
    Uses CURATED_MARKDOWN_FILES list from config to index only:
    - Labs 1-17 (complete build history)
    - Current implementation guides
    - Key architecture documents
    
    This avoids contradictory/outdated docs and reduces memory usage.
    
    Args:
        collection: ChromaDB collection
        max_file_size_mb: Maximum markdown file size in MB (default 5MB)
        batch_size: Process files in batches to avoid OOM (default 3)
        
    Returns:
        Number of chunks indexed
    """
    logger.info(f"Indexing curated markdown files from {DOCUMENTATION_DIR}")
    
    # Use curated file list instead of glob
    markdown_files = []
    missing_files = []
    
    for rel_path in CURATED_MARKDOWN_FILES:
        md_path = DOCUMENTATION_DIR / rel_path
        if not md_path.exists():
            missing_files.append(rel_path)
            logger.warning(f"Curated file not found: {rel_path}")
            continue
            
        # Check file size
        file_size_mb = md_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            logger.warning(f"Skipping large markdown ({file_size_mb:.1f}MB): {md_path.name}")
            continue
            
        markdown_files.append(md_path)
    
    if missing_files:
        logger.warning(f"Missing {len(missing_files)} curated files")
    
    logger.info(f"Found {len(markdown_files)}/{len(CURATED_MARKDOWN_FILES)} curated markdown files")
    total_chunks = 0
    
    # Process in batches to avoid OOM
    for batch_idx in range(0, len(markdown_files), batch_size):
        batch = markdown_files[batch_idx:batch_idx+batch_size]
        logger.info(f"Processing batch {batch_idx//batch_size + 1}/{(len(markdown_files)-1)//batch_size + 1}")
        
        for md_path in batch:
            try:
                # Read file
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Skip empty files
                if not content.strip():
                    continue
                
                # Chunk the content
                chunks = chunk_text(content)
                
                # Generate unique IDs for each chunk
                relative_path = md_path.relative_to(DOCUMENTATION_DIR)
                doc_id = hashlib.md5(str(relative_path).encode()).hexdigest()[:8]
                
                # Prepare metadata
                metadatas = []
                ids = []
                for i, chunk in enumerate(chunks):
                    ids.append(f"{doc_id}_chunk_{i}")
                    metadatas.append({
                        "source": str(relative_path),
                        "filename": md_path.name,
                        "type": "markdown",
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    })
                
                # Add to collection (ChromaDB will generate embeddings via OpenAI)
                collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_chunks += len(chunks)
                logger.info(f"Indexed {md_path.name}: {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"Error indexing {md_path}: {e}")
                continue
    
    logger.info(f"Indexed {len(markdown_files)} markdown files, {total_chunks} chunks total")
    return total_chunks


def index_pdf_files(collection, max_file_size_mb: int = 20, batch_size: int = 5) -> int:
    """
    Index all PDF files in documentation/Research/ directory.
    
    Args:
        collection: ChromaDB collection
        max_file_size_mb: Maximum PDF file size in MB (default 20MB)
        batch_size: Number of files to process in each batch (default 5)
        
    Returns:
        Number of chunks indexed
    """
    if not PYPDF2_AVAILABLE:
        logger.warning("PyPDF2 not available. Skipping PDF indexing.")
        return 0
    
    logger.info(f"Indexing PDF files from {RESEARCH_DIR}")
    
    # Get all PDF files, excluding certain directories
    exclude_dirs = {'Pictures', 'Systematic Review Data', '__pycache__', '.DS_Store'}
    pdf_files = []
    for pdf_path in RESEARCH_DIR.rglob("*.pdf"):
        # Skip if in excluded directory
        if any(excluded in pdf_path.parts for excluded in exclude_dirs):
            logger.debug(f"Skipping PDF in excluded directory: {pdf_path}")
            continue
        # Skip if file is too large
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            logger.warning(f"Skipping large PDF ({file_size_mb:.1f}MB): {pdf_path.name}")
            continue
        pdf_files.append(pdf_path)
    
    logger.info(f"Found {len(pdf_files)} PDF files to index")
    total_chunks = 0
    
    # Process in batches to avoid memory issues
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(pdf_files)-1)//batch_size + 1}")
        
        for pdf_path in batch:
            try:
                # Extract text
                text = extract_pdf_text(pdf_path)
                if not text.strip():
                    logger.warning(f"No text extracted from {pdf_path.name}")
                    continue
                
                # Chunk the content
                chunks = chunk_text(text)
                
                # Generate unique IDs for each chunk
                relative_path = pdf_path.relative_to(RESEARCH_DIR)
                doc_id = hashlib.md5(str(relative_path).encode()).hexdigest()[:8]
                
                # Prepare metadata
                metadatas = []
                ids = []
                for i, chunk in enumerate(chunks):
                    ids.append(f"pdf_{doc_id}_chunk_{i}")
                    metadatas.append({
                        "source": str(relative_path),
                        "filename": pdf_path.name,
                        "type": "pdf",
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    })
                
                # Add to collection
                collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_chunks += len(chunks)
                logger.info(f"Indexed {pdf_path.name}: {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"Error indexing {pdf_path}: {e}")
                continue
    
    logger.info(f"Indexed {len(pdf_files)} PDF files, {total_chunks} chunks total")
    return total_chunks


def index_all_documents(force_reindex: bool = False) -> Dict[str, Any]:
    """
    Index all documentation (markdown + PDFs) into ChromaDB.
    
    Args:
        force_reindex: If True, delete existing index and rebuild
        
    Returns:
        Statistics about indexed documents
    """
    if not CHROMADB_AVAILABLE:
        logger.error("ChromaDB not available. Cannot index documents.")
        return {"error": "ChromaDB not installed", "indexed": 0}
    
    try:
        # Initialize ChromaDB client (local or cloud based on config)
        client = get_chroma_client()
        
        # Get or create collection
        collection_name = "voice_ledger_knowledge"
        
        if force_reindex:
            try:
                client.delete_collection(name=collection_name)
                logger.info(f"Deleted existing collection: {collection_name}")
            except:
                pass
        
        # Use OpenAI embeddings function
        from chromadb.utils import embedding_functions
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=EMBEDDING_MODEL
        )
        
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef,
            metadata={"description": "Voice Ledger documentation and research papers"}
        )
        
        # Check if already indexed
        existing_count = collection.count()
        if existing_count > 0 and not force_reindex:
            logger.info(f"Collection already has {existing_count} documents. Skipping indexing.")
            return {
                "status": "already_indexed",
                "existing_count": existing_count,
                "collection": collection_name
            }
        
        # Index markdown files
        markdown_chunks = index_markdown_files(collection)
        
        # Index PDF files
        pdf_chunks = index_pdf_files(collection)
        
        total_chunks = markdown_chunks + pdf_chunks
        
        logger.info(f"Indexing complete: {total_chunks} chunks total")
        
        return {
            "status": "success",
            "markdown_chunks": markdown_chunks,
            "pdf_chunks": pdf_chunks,
            "total_chunks": total_chunks,
            "collection": collection_name,
            "database_path": str(CHROMA_DB_PATH)
        }
        
    except Exception as e:
        logger.error(f"Error indexing documents: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


def get_index_stats() -> Dict[str, Any]:
    """
    Get statistics about the current knowledge base index.
    
    Returns:
        Statistics dictionary
    """
    if not CHROMADB_AVAILABLE:
        return {"error": "ChromaDB not installed", "indexed": False}
    
    try:
        client = get_chroma_client()
        collection = client.get_collection(name="voice_ledger_knowledge")
        
        count = collection.count()
        
        # Sample metadata to see what's indexed
        if count > 0:
            sample = collection.get(limit=10)
            types = set(m.get('type', 'unknown') for m in sample['metadatas'])
        else:
            types = set()
        
        return {
            "indexed": True,
            "total_chunks": count,
            "document_types": list(types),
            "database_path": str(CHROMA_DB_PATH)
        }
        
    except Exception as e:
        return {
            "indexed": False,
            "error": str(e)
        }
