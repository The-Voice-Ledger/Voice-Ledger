#!/usr/bin/env python3
"""
Codebase Indexer for ChromaDB Cloud

Indexes Python, JavaScript, and Solidity code files to enable
code-aware RAG queries like:
- "How is batch verification implemented?"
- "Show me the marketplace API endpoints"
- "Where is GPS photo extraction done?"
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import gc
import re

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent

# Core directories to index (selective, not everything)
INCLUDE_DIRS = [
    "voice/",           # Voice processing, Telegram, marketplace
    "database/",        # Database models and CRUD
    "blockchain/",      # Smart contracts, token manager, anchoring
    "epcis/",          # EPCIS event builders
    "eudr/",           # GPS verification, deforestation
    "dpp/",            # Digital Product Passport
    "twin/",           # Digital twin builder
    "gs1/",            # GS1 identifiers
    "ssi/",            # Self-sovereign identity
    "ipfs/",           # IPFS storage
]

# File extensions to include
CODE_EXTENSIONS = [".py", ".js", ".sol", ".ts", ".jsx", ".tsx"]

# Directories to ALWAYS exclude
EXCLUDE_DIRS = {
    "venv", "node_modules", "__pycache__", ".git", 
    "cache", "broadcast", "lib", "build", "dist",
    "qrcodes", "passports", "logs", "events",
    ".pytest_cache", ".mypy_cache", "test/",
}

MAX_CHUNK_SIZE = 2000  # Smaller chunks for code (preserve context)
OVERLAP = 100

def should_exclude_path(path: Path) -> bool:
    """Check if path should be excluded"""
    parts = path.parts
    return any(excluded in parts for excluded in EXCLUDE_DIRS)

def find_code_files() -> list[Path]:
    """Find all code files in included directories"""
    code_files = []
    
    for include_dir in INCLUDE_DIRS:
        dir_path = PROJECT_ROOT / include_dir
        if not dir_path.exists():
            print(f"⚠️  Directory not found: {include_dir}")
            continue
        
        for ext in CODE_EXTENSIONS:
            for file_path in dir_path.rglob(f"*{ext}"):
                if not should_exclude_path(file_path):
                    code_files.append(file_path)
    
    return sorted(set(code_files))

def detect_language(file_path: Path) -> str:
    """Detect programming language from extension"""
    ext = file_path.suffix.lower()
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript-react",
        ".tsx": "typescript-react",
        ".sol": "solidity",
    }
    return lang_map.get(ext, "unknown")

def extract_functions_classes(code: str, language: str) -> list[dict]:
    """
    Extract functions and classes with their line ranges.
    Returns list of {name, start_line, end_line, type}
    """
    entities = []
    lines = code.split('\n')
    
    if language == "python":
        # Match function and class definitions
        for i, line in enumerate(lines, 1):
            # Class definitions
            class_match = re.match(r'^class\s+(\w+)', line)
            if class_match:
                entities.append({
                    'name': class_match.group(1),
                    'start_line': i,
                    'type': 'class'
                })
            
            # Function definitions
            func_match = re.match(r'^def\s+(\w+)', line)
            if func_match:
                entities.append({
                    'name': func_match.group(1),
                    'start_line': i,
                    'type': 'function'
                })
    
    elif language in ["javascript", "typescript", "javascript-react", "typescript-react"]:
        # Match function and class definitions
        for i, line in enumerate(lines, 1):
            # Class definitions
            class_match = re.match(r'^\s*class\s+(\w+)', line)
            if class_match:
                entities.append({
                    'name': class_match.group(1),
                    'start_line': i,
                    'type': 'class'
                })
            
            # Function definitions (various patterns)
            func_patterns = [
                r'^\s*function\s+(\w+)',  # function name()
                r'^\s*const\s+(\w+)\s*=\s*(?:async\s+)?\(',  # const name = (
                r'^\s*async\s+function\s+(\w+)',  # async function name()
            ]
            for pattern in func_patterns:
                func_match = re.match(pattern, line)
                if func_match:
                    entities.append({
                        'name': func_match.group(1),
                        'start_line': i,
                        'type': 'function'
                    })
    
    elif language == "solidity":
        # Match contract, function, and modifier definitions
        for i, line in enumerate(lines, 1):
            # Contract definitions
            contract_match = re.match(r'^\s*contract\s+(\w+)', line)
            if contract_match:
                entities.append({
                    'name': contract_match.group(1),
                    'start_line': i,
                    'type': 'contract'
                })
            
            # Function definitions
            func_match = re.match(r'^\s*function\s+(\w+)', line)
            if func_match:
                entities.append({
                    'name': func_match.group(1),
                    'start_line': i,
                    'type': 'function'
                })
    
    return entities

def chunk_code_smart(code: str, file_path: Path, language: str) -> list[dict]:
    """
    Smart code chunking that tries to keep functions/classes intact.
    Falls back to fixed-size chunking for large functions.
    """
    chunks = []
    lines = code.split('\n')
    entities = extract_functions_classes(code, language)
    
    if not entities:
        # No entities found, use fixed-size chunking
        return chunk_code_fixed(code, file_path, language)
    
    # Calculate end lines for each entity (start of next entity or EOF)
    for i, entity in enumerate(entities):
        if i + 1 < len(entities):
            entity['end_line'] = entities[i + 1]['start_line'] - 1
        else:
            entity['end_line'] = len(lines)
    
    current_chunk = []
    current_start_line = 1
    current_entities = []
    
    for entity in entities:
        entity_lines = lines[entity['start_line']-1:entity['end_line']]
        entity_text = '\n'.join(entity_lines)
        entity_size = len(entity_text)
        
        # If single entity is too large, chunk it separately
        if entity_size > MAX_CHUNK_SIZE * 1.5:
            # Save current chunk if exists
            if current_chunk:
                chunks.append({
                    'content': '\n'.join(current_chunk),
                    'start_line': current_start_line,
                    'end_line': entity['start_line'] - 1,
                    'entities': current_entities.copy()
                })
                current_chunk = []
                current_entities = []
            
            # Chunk large entity with fixed-size
            large_entity_chunks = chunk_text_fixed(entity_text, MAX_CHUNK_SIZE, OVERLAP)
            for idx, chunk_text in enumerate(large_entity_chunks):
                chunks.append({
                    'content': chunk_text,
                    'start_line': entity['start_line'],
                    'end_line': entity['end_line'],
                    'entities': [f"{entity['name']} (part {idx+1})"]
                })
            
            current_start_line = entity['end_line'] + 1
        
        # If adding entity would exceed chunk size, save current and start new
        elif current_chunk and len('\n'.join(current_chunk)) + entity_size > MAX_CHUNK_SIZE:
            chunks.append({
                'content': '\n'.join(current_chunk),
                'start_line': current_start_line,
                'end_line': entity['start_line'] - 1,
                'entities': current_entities.copy()
            })
            current_chunk = entity_lines
            current_start_line = entity['start_line']
            current_entities = [entity['name']]
        
        # Add entity to current chunk
        else:
            if not current_chunk:
                current_start_line = entity['start_line']
            current_chunk.extend(entity_lines)
            current_entities.append(entity['name'])
    
    # Save remaining chunk
    if current_chunk:
        chunks.append({
            'content': '\n'.join(current_chunk),
            'start_line': current_start_line,
            'end_line': len(lines),
            'entities': current_entities
        })
    
    return chunks

def chunk_text_fixed(text: str, max_size: int, overlap: int) -> list[str]:
    """Fixed-size text chunking with overlap"""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + max_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    
    return chunks

def chunk_code_fixed(code: str, file_path: Path, language: str) -> list[dict]:
    """Fallback fixed-size chunking"""
    text_chunks = chunk_text_fixed(code, MAX_CHUNK_SIZE, OVERLAP)
    return [
        {
            'content': chunk,
            'start_line': 1,  # Approximate
            'end_line': len(code.split('\n')),
            'entities': []
        }
        for chunk in text_chunks
    ]

def index_code_file(file_path: Path, collection, indexed_count: int, total_files: int):
    """Index a single code file"""
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        
        if not code.strip():
            return 0
        
        # Detect language
        language = detect_language(file_path)
        
        # Smart chunking
        chunks = chunk_code_smart(code, file_path, language)
        
        if not chunks:
            return 0
        
        # Prepare metadata
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        documents = []
        ids = []
        metadatas = []
        
        for idx, chunk_info in enumerate(chunks):
            chunk_id = f"code_{file_path.stem}_{idx}"
            
            # Format content with file header for context
            entities_str = ", ".join(chunk_info['entities']) if chunk_info['entities'] else "N/A"
            content = f"""# File: {rel_path}
# Language: {language}
# Lines: {chunk_info['start_line']}-{chunk_info['end_line']}
# Entities: {entities_str}

{chunk_info['content']}"""
            
            documents.append(content)
            ids.append(chunk_id)
            metadatas.append({
                'source': rel_path,
                'type': 'code',
                'language': language,
                'chunk': idx,
                'start_line': chunk_info['start_line'],
                'end_line': chunk_info['end_line'],
                'entities': entities_str,
                'file_name': file_path.name,
            })
        
        # Add to collection
        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
        
        print(f"[{indexed_count}/{total_files}] ✅ {rel_path} ({len(chunks)} chunks, {language})")
        return len(chunks)
    
    except Exception as e:
        print(f"[{indexed_count}/{total_files}] ❌ {file_path.name}: {e}")
        return 0

def main():
    print("=" * 70)
    print("CODEBASE INDEXER - ChromaDB Cloud")
    print("=" * 70)
    print()
    
    # Find code files
    print("🔍 Finding code files...")
    code_files = find_code_files()
    
    if not code_files:
        print("❌ No code files found!")
        return
    
    print(f"✅ Found {len(code_files)} code files\n")
    
    # Show breakdown by language
    by_language = {}
    for f in code_files:
        lang = detect_language(f)
        by_language[lang] = by_language.get(lang, 0) + 1
    
    print("📊 Files by language:")
    for lang, count in sorted(by_language.items()):
        print(f"   {lang}: {count} files")
    print()
    
    # Connect to ChromaDB Cloud
    print("🔌 Connecting to ChromaDB Cloud...")
    client = chromadb.CloudClient(
        api_key=os.getenv("CHROMA_API_KEY"),
        tenant=os.getenv("CHROMA_TENANT"),
        database=os.getenv("CHROMA_DATABASE")
    )
    print("✅ Connected!\n")
    
    # Get or create collection with OpenAI embeddings
    print("📚 Getting collection...")
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    
    collection = client.get_collection(
        name="voice_ledger_docs_v2",
        embedding_function=openai_ef
    )
    
    # Get current collection size
    try:
        current_count = collection.count()
        print(f"📊 Current collection size: {current_count} chunks\n")
    except:
        current_count = 0
    
    print(f"🚀 Indexing {len(code_files)} code files...\n")
    
    # Index files
    total_chunks = 0
    successful_files = 0
    
    for idx, file_path in enumerate(code_files, 1):
        chunks_added = index_code_file(file_path, collection, idx, len(code_files))
        if chunks_added > 0:
            total_chunks += chunks_added
            successful_files += 1
        
        # Explicit garbage collection
        gc.collect()
    
    print(f"\n{'=' * 70}")
    print("🎉 INDEXING COMPLETE!")
    print(f"{'=' * 70}")
    print(f"Files indexed: {successful_files}/{len(code_files)}")
    print(f"New chunks added: {total_chunks}")
    
    # Final collection size
    try:
        final_count = collection.count()
        print(f"Total collection size: {final_count} chunks")
    except:
        pass
    
    print()
    print("💡 Example queries you can now run:")
    print('   "How is batch verification implemented?"')
    print('   "Show me the marketplace API endpoints"')
    print('   "Where is GPS photo extraction done?"')
    print('   "Explain the token minting workflow"')
    print('   "How does the conversational AI work?"')

if __name__ == "__main__":
    main()
