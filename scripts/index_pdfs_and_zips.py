#!/usr/bin/env python3
"""
PDF and ZIP Indexer for ChromaDB Cloud

Indexes PDF research papers to ChromaDB Cloud, including:
- Direct PDF files from Research directory
- PDFs extracted from ZIP archives
- Memory-efficient processing (one file at a time)
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import gc
import tempfile
import zipfile
import shutil

# Load environment first
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

# Try to import PyPDF2
try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    print("⚠️  PyPDF2 not installed. Run: pip install PyPDF2")
    PYPDF2_AVAILABLE = False
    sys.exit(1)

# Configuration
RESEARCH_DIR = Path(__file__).parent.parent / "documentation" / "Research"
MAX_PDF_SIZE_MB = 15  # Skip PDFs larger than this
CHUNK_SIZE = 4000  # Characters per chunk

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

def find_pdfs_in_directory(directory: Path, max_size_mb: float):
    """Find all PDFs in directory, excluding those too large"""
    pdfs = []
    for pdf_path in directory.rglob("*.pdf"):
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if size_mb <= max_size_mb:
            pdfs.append((pdf_path, size_mb))
        else:
            print(f"⚠️  Skipping large PDF ({size_mb:.1f}MB): {pdf_path.name}")
    return pdfs

def extract_pdfs_from_zip(zip_path: Path, temp_dir: Path, max_size_mb: float):
    """Extract PDFs from ZIP file to temporary directory"""
    extracted_pdfs = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # List all PDF files in the zip
            pdf_files = [f for f in zip_ref.namelist() if f.lower().endswith('.pdf')]
            
            print(f"   Found {len(pdf_files)} PDFs in ZIP")
            
            for pdf_file in pdf_files:
                # Get file info to check size
                file_info = zip_ref.getinfo(pdf_file)
                size_mb = file_info.file_size / (1024 * 1024)
                
                if size_mb > max_size_mb:
                    print(f"   ⚠️  Skipping large PDF in ZIP ({size_mb:.1f}MB): {pdf_file}")
                    continue
                
                # Extract to temp directory
                extracted_path = temp_dir / Path(pdf_file).name
                with zip_ref.open(pdf_file) as source, open(extracted_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                
                extracted_pdfs.append((extracted_path, size_mb, pdf_file))
                
    except Exception as e:
        print(f"   ❌ Error extracting ZIP: {e}")
    
    return extracted_pdfs

def main():
    print("=" * 70)
    print("PDF and ZIP Indexer - ChromaDB Cloud")
    print("=" * 70)
    print()
    
    # Connect to ChromaDB Cloud
    print("Connecting to ChromaDB Cloud...")
    client = chromadb.CloudClient(
        api_key=os.getenv("CHROMA_API_KEY"),
        tenant=os.getenv("CHROMA_TENANT"),
        database=os.getenv("CHROMA_DATABASE")
    )
    print("✅ Connected")
    print()
    
    # Get or create collection with OpenAI embeddings
    collection_name = "voice_ledger_docs_v2"
    print(f"Using collection: {collection_name}")
    
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
    print(f"  - Max PDF size: {MAX_PDF_SIZE_MB} MB")
    print(f"  - Chunk size: {CHUNK_SIZE} characters")
    print(f"  - Research dir: {RESEARCH_DIR}")
    print()
    
    # Find all PDFs in directory
    print("Scanning for PDFs...")
    direct_pdfs = find_pdfs_in_directory(RESEARCH_DIR, MAX_PDF_SIZE_MB)
    print(f"Found {len(direct_pdfs)} PDFs to index")
    print()
    
    # Find ZIP files and extract PDFs
    zip_files = list(RESEARCH_DIR.rglob("*.zip"))
    zip_pdfs = []
    
    if zip_files:
        print(f"Found {len(zip_files)} ZIP file(s)")
        temp_dir = Path(tempfile.mkdtemp())
        
        for zip_path in zip_files:
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"Processing ZIP: {zip_path.name} ({size_mb:.1f}MB)")
            extracted = extract_pdfs_from_zip(zip_path, temp_dir, MAX_PDF_SIZE_MB)
            zip_pdfs.extend(extracted)
        
        print(f"Extracted {len(zip_pdfs)} PDFs from ZIP files")
        print()
    
    # Combine all PDFs
    all_pdfs = [(pdf_path, size_mb, str(pdf_path.relative_to(RESEARCH_DIR))) 
                for pdf_path, size_mb in direct_pdfs]
    all_pdfs.extend(zip_pdfs)
    
    total_pdfs = len(all_pdfs)
    print(f"Total PDFs to process: {total_pdfs}")
    print("=" * 70)
    print()
    
    # Process PDFs one at a time
    total_chunks = 0
    successful_pdfs = 0
    failed_pdfs = []
    
    for idx, (pdf_path, size_mb, source_path) in enumerate(all_pdfs, 1):
        try:
            print(f"[{idx}/{total_pdfs}] Processing: {pdf_path.name} ({size_mb:.1f}MB)")
            
            # Extract text
            text = extract_pdf_text(pdf_path)
            
            if not text or len(text.strip()) < 100:
                print(f"   ⚠️  Insufficient text extracted (likely scanned/image PDF)")
                continue
            
            # Chunk text
            chunks = chunk_text(text)
            
            if len(chunks) == 0:
                print(f"   ⚠️  No chunks created")
                continue
            
            # Add to collection
            doc_id = pdf_path.stem.replace(" ", "_")[:50]
            ids = [f"pdf_{doc_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "source": source_path,
                    "filename": pdf_path.name,
                    "type": "pdf",
                    "chunk": i,
                    "size_mb": round(size_mb, 2)
                } 
                for i in range(len(chunks))
            ]
            
            collection.add(
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
            
            total_chunks += len(chunks)
            successful_pdfs += 1
            print(f"   ✅ Indexed {len(chunks)} chunks")
            
            # Explicit garbage collection
            del text, chunks, ids, metadatas
            gc.collect()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_pdfs.append((pdf_path.name, str(e)))
            continue
    
    # Cleanup temp directory if we extracted ZIPs
    if zip_pdfs:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    # Final summary
    final_count = collection.count()
    added_chunks = final_count - initial_count
    
    print()
    print("=" * 70)
    print("🎉 Indexing Complete!")
    print("=" * 70)
    print(f"PDFs processed: {successful_pdfs}/{total_pdfs}")
    print(f"New chunks added: {added_chunks}")
    print(f"Total collection size: {final_count} chunks")
    
    if failed_pdfs:
        print(f"\n⚠️  Failed PDFs ({len(failed_pdfs)}):")
        for name, error in failed_pdfs[:5]:
            print(f"   - {name}: {error[:60]}")
        if len(failed_pdfs) > 5:
            print(f"   ... and {len(failed_pdfs) - 5} more")
    
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
