#!/usr/bin/env python3
"""
Lightweight Indexer - One File at a Time

Indexes curated documentation to ChromaDB Cloud with minimal memory usage.
Processes one file at a time with explicit garbage collection.
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import gc

# Load environment first
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

# Configuration
DOCUMENTATION_DIR = Path(__file__).parent.parent / "documentation"
CURATED_FILES = [
    "labs/LABS_1-2_GS1_EPCIS_Voice_AI.md",
    "labs/LABS_3-4_SSI_Blockchain.md",
    "labs/LABS_5-6_DPP_Docker.md",
    "labs/LABS_7_Voice_Interface.md",
    "labs/LABS_8_IVR_Telegram.md",
    "labs/LABS_9-10_Verification_Registration.md",
    "labs/LABS_11_Conversational_AI.md",
    "labs/LABS_12_Aggregation_Events.md",
    "labs/LABS_13_Post_Verification_Token_Minting.md",
    "labs/LABS_14_Multi_Actor_Marketplace.md",
    "labs/LABS_15_RFQ_Marketplace_API.md",
    "labs/LABS_16_EUDR_GPS_Deforestation.md",
    "labs/LABS_17_Bilingual_Voice_UI.md",
    "labs/LAB17_COMPLETION_SUMMARY.md",
    "guides/VOICE_LEDGER_OVERVIEW.md",
    "guides/Technical_Guide.md",
    "guides/REGISTRATION_VERIFICATION_IDENTITY.md",
    "guides/TELEGRAM_WEB_AUTHENTICATION_INTEGRATION.md",
    "guides/BILINGUAL_ASR_GUIDE.md",
    "guides/EUDR_COMPLIANCE_GUIDE.md",
    "INDEX.md",
]

def chunk_text(text, max_chars=4000):
    """Simple chunking by character count"""
    chunks = []
    for i in range(0, len(text), max_chars):
        chunk = text[i:i+max_chars].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def main():
    print("=" * 60)
    print("Lightweight Indexer - ChromaDB Cloud")
    print("=" * 60)
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
    
    # Create collection with OpenAI embeddings
    collection_name = "voice_ledger_docs_v2"
    print(f"Creating collection: {collection_name}")
    
    # Delete if exists
    try:
        client.delete_collection(collection_name)
        print("Deleted existing collection")
    except:
        pass
    
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    
    collection = client.create_collection(
        name=collection_name,
        embedding_function=openai_ef
    )
    print("✅ Collection created")
    print()
    
    # Process files one at a time
    total_chunks = 0
    successful_files = 0
    
    for idx, rel_path in enumerate(CURATED_FILES, 1):
        file_path = DOCUMENTATION_DIR / rel_path
        
        if not file_path.exists():
            print(f"[{idx}/{len(CURATED_FILES)}] ⚠️  Missing: {rel_path}")
            continue
        
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                print(f"[{idx}/{len(CURATED_FILES)}] ⚠️  Empty: {file_path.name}")
                continue
            
            # Chunk
            chunks = chunk_text(content)
            
            # Add to collection
            ids = [f"{file_path.stem}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"source": rel_path, "chunk": i} for i in range(len(chunks))]
            
            collection.add(
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
            
            total_chunks += len(chunks)
            successful_files += 1
            print(f"[{idx}/{len(CURATED_FILES)}] ✅ {file_path.name} ({len(chunks)} chunks)")
            
            # Explicit garbage collection to free memory
            del content, chunks, ids, metadatas
            gc.collect()
            
        except Exception as e:
            print(f"[{idx}/{len(CURATED_FILES)}] ❌ {file_path.name}: {e}")
            continue
    
    print()
    print("=" * 60)
    print(f"🎉 Completed!")
    print(f"Files: {successful_files}/{len(CURATED_FILES)}")
    print(f"Chunks: {total_chunks}")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
