#!/usr/bin/env python3
"""
Large PDF Indexer - Handles files that exceed token limits

Processes large PDFs by adding chunks in smaller batches to avoid
the 300K token limit per API request.
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import gc

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from PyPDF2 import PdfReader

# Configuration
RESEARCH_DIR = Path(__file__).parent.parent / "documentation" / "Research"
CHUNK_SIZE = 4000  # Characters per chunk
MAX_CHUNKS_PER_BATCH = 50  # Add max 50 chunks per API call (prevents token limit issues)

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(str(pdf_path))
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n\n".join(text)
    except Exception as e:
        print(f"   ⚠️  Error extracting text: {e}")
        return ""

def chunk_text(text, max_chars=CHUNK_SIZE):
    """Simple chunking by character count"""
    chunks = []
    for i in range(0, len(text), max_chars):
        chunk = text[i:i+max_chars].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def add_chunks_in_batches(collection, chunks, doc_id, source_path, filename, size_mb, batch_size=MAX_CHUNKS_PER_BATCH):
    """Add chunks to collection in smaller batches to avoid token limits"""
    total_chunks = len(chunks)
    total_added = 0
    
    for batch_start in range(0, total_chunks, batch_size):
        batch_end = min(batch_start + batch_size, total_chunks)
        batch_chunks = chunks[batch_start:batch_end]
        
        # Create IDs and metadata for this batch
        ids = [f"pdf_{doc_id}_chunk_{i}" for i in range(batch_start, batch_end)]
        metadatas = [
            {
                "source": source_path,
                "filename": filename,
                "type": "pdf",
                "chunk": i,
                "size_mb": round(size_mb, 2)
            } 
            for i in range(batch_start, batch_end)
        ]
        
        try:
            collection.add(
                documents=batch_chunks,
                ids=ids,
                metadatas=metadatas
            )
            total_added += len(batch_chunks)
            print(f"      Batch {batch_start//batch_size + 1}/{(total_chunks-1)//batch_size + 1}: Added {len(batch_chunks)} chunks")
            
            # Cleanup after each batch
            del batch_chunks, ids, metadatas
            gc.collect()
            
        except Exception as e:
            print(f"      ❌ Batch failed: {e}")
            continue
    
    return total_added

def main():
    print("=" * 70)
    print("Large PDF Indexer - Batch Processing")
    print("=" * 70)
    print()
    
    # Specific large PDFs to process
    large_pdfs = [
        "BCT Enabled SCM - Course/Standards/GS1 General Specifications.pdf"
    ]
    
    # Connect to ChromaDB Cloud
    print("Connecting to ChromaDB Cloud...")
    client = chromadb.CloudClient(
        api_key=os.getenv("CHROMA_API_KEY"),
        tenant=os.getenv("CHROMA_TENANT"),
        database=os.getenv("CHROMA_DATABASE")
    )
    print("✅ Connected")
    print()
    
    # Get collection
    collection_name = "voice_ledger_docs_v2"
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        initial_count = collection.count()
        print(f"✅ Collection exists ({initial_count} existing chunks)")
    except:
        print("❌ Collection not found. Please run lightweight_indexer.py first.")
        return 1
    
    print()
    print(f"Configuration:")
    print(f"  - Chunk size: {CHUNK_SIZE} characters")
    print(f"  - Max chunks per batch: {MAX_CHUNKS_PER_BATCH}")
    print(f"  - PDFs to process: {len(large_pdfs)}")
    print()
    
    # Process each large PDF
    total_chunks_added = 0
    
    for idx, rel_path in enumerate(large_pdfs, 1):
        pdf_path = RESEARCH_DIR / rel_path
        
        if not pdf_path.exists():
            print(f"[{idx}/{len(large_pdfs)}] ⚠️  Not found: {rel_path}")
            continue
        
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print(f"[{idx}/{len(large_pdfs)}] Processing: {pdf_path.name} ({size_mb:.1f}MB)")
        
        try:
            # Extract text
            print(f"   Extracting text...")
            text = extract_pdf_text(pdf_path)
            
            if not text or len(text.strip()) < 100:
                print(f"   ⚠️  Insufficient text extracted")
                continue
            
            print(f"   Extracted {len(text):,} characters")
            
            # Chunk text
            chunks = chunk_text(text)
            print(f"   Created {len(chunks)} chunks")
            
            if len(chunks) == 0:
                print(f"   ⚠️  No chunks created")
                continue
            
            # Add chunks in batches
            print(f"   Adding chunks in batches of {MAX_CHUNKS_PER_BATCH}...")
            doc_id = pdf_path.stem.replace(" ", "_")[:50]
            
            added = add_chunks_in_batches(
                collection=collection,
                chunks=chunks,
                doc_id=doc_id,
                source_path=rel_path,
                filename=pdf_path.name,
                size_mb=size_mb
            )
            
            total_chunks_added += added
            print(f"   ✅ Successfully added {added} chunks")
            
            # Cleanup
            del text, chunks
            gc.collect()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Final summary
    final_count = collection.count()
    
    print()
    print("=" * 70)
    print("🎉 Indexing Complete!")
    print("=" * 70)
    print(f"New chunks added: {total_chunks_added}")
    print(f"Total collection size: {final_count} chunks")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
