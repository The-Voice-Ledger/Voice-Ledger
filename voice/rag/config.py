"""
RAG Configuration

Settings for knowledge base indexing and retrieval.
Works for both local development and Railway deployment.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for logging config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging first
from voice.logging_config import get_logger
logger = get_logger(__name__)

# Load environment variables after logging setup
load_dotenv()

# Paths - Railway compatible with local fallback
VOICE_LEDGER_ROOT = Path(__file__).parent.parent.parent
DOCUMENTATION_DIR = VOICE_LEDGER_ROOT / "documentation"
RESEARCH_DIR = DOCUMENTATION_DIR / "Research"

# Curated documentation - only relevant, up-to-date files
# Reflects what we've actually built (Labs 1-17 + key guides)
CURATED_MARKDOWN_FILES = [
    # === LABS (Complete build history) ===
    "labs/LABS_1-2_GS1_EPCIS_Voice_AI.md",
    "labs/LABS_3-4_SSI_Blockchain.md",
    "labs/LABS_5-6_DPP_Docker.md",
    "labs/LABS_7_Voice_Interface.md",
    "labs/LABS_8_IVR_Telegram.md",
    "labs/LABS_8_WHY_THIS_DESIGN.md",
    "labs/LABS_9-10_Verification_Registration.md",
    "labs/LABS_11_Conversational_AI.md",
    "labs/LABS_12_Aggregation_Events.md",
    "labs/LABS_13_Post_Verification_Token_Minting.md",
    "labs/LABS_14_Multi_Actor_Marketplace.md",
    "labs/LABS_15_RFQ_Marketplace_API.md",
    "labs/LABS_16_EUDR_GPS_Deforestation.md",
    "labs/LABS_17_Bilingual_Voice_UI.md",
    "labs/LAB17_COMPLETION_SUMMARY.md",
    "labs/LABS_UPDATE_SUMMARY.md",
    
    # === GUIDES (Current implementation details) ===
    "guides/VOICE_LEDGER_OVERVIEW.md",
    "guides/Technical_Guide.md",
    "guides/REGISTRATION_VERIFICATION_IDENTITY.md",
    "guides/TELEGRAM_WEB_AUTHENTICATION_INTEGRATION.md",
    "guides/BILINGUAL_ASR_GUIDE.md",
    "guides/BILINGUAL_QUICKSTART.md",
    "guides/EUDR_COMPLIANCE_GUIDE.md",
    "guides/SERVICE_COMMANDS.md",
    "guides/CHROMADB_CLOUD_SETUP.md",
    "guides/RAILWAY_DEPLOYMENT_GUIDE.md",
    
    # === IDEAS (Architecture & design) ===
    "ideas/VoiceFirst_Interface_Design.md",
    
    # === ROOT (Key system docs) ===
    "INDEX.md",
    "TODO_MARKETPLACE_COMPLETION.md",
]

# ChromaDB Configuration - Cloud-first (more reliable, no OOM)
CHROMA_CLIENT_TYPE = os.getenv("CHROMA_CLIENT_TYPE", "cloud")  # "cloud" (default) or "local"

# Local ChromaDB (default)
CHROMA_DB_PATH = Path(os.getenv("CHROMA_DB_PATH", str(VOICE_LEDGER_ROOT / "voice" / "rag" / "chroma_db")))
if CHROMA_CLIENT_TYPE == "local":
    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

# ChromaDB Cloud (for large datasets, no OOM issues)
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")  # Your ChromaDB Cloud API key
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "default_tenant")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "default_database")

# Embedding settings
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI embedding model
EMBEDDING_DIMENSION = 1536  # Dimensions for text-embedding-3-small
CHUNK_SIZE = 1000  # Tokens per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks

# Retrieval settings
DEFAULT_TOP_K = 5  # Number of results to retrieve
MIN_SIMILARITY_SCORE = 0.5  # Minimum similarity threshold

# Query classification keywords
TECHNICAL_KEYWORDS = [
    "epcis", "gs1", "gtin", "sscc", "standard", "spec", "specification",
    "event", "schema", "json-ld", "xml", "sensor", "blockchain",
    "transformation", "aggregation", "disaggregation", "traceability"
]

DESIGN_KEYWORDS = [
    "design", "architecture", "socio-technical", "farmer", "power",
    "governance", "access", "inclusion", "literacy", "voice-first",
    "ethiopia", "smallholder", "cooperative", "did", "identity"
]

HOWTO_KEYWORDS = [
    "how to", "how do i", "guide", "tutorial", "step", "create",
    "register", "record", "ship", "marketplace", "rfq", "offer"
]


def get_chroma_client():
    """
    Get ChromaDB client based on configuration.
    
    Returns local PersistentClient or cloud HttpClient based on
    CHROMA_CLIENT_TYPE environment variable.
    
    Environment Variables:
        CHROMA_CLIENT_TYPE: "local" (default) or "cloud"
        
        For local:
            CHROMA_DB_PATH: Local database path
        
        For cloud:
            CHROMA_HOST: ChromaDB Cloud host (e.g., api.trychroma.com)
            CHROMA_PORT: Port (default 443)
            CHROMA_API_KEY: Your API key
            CHROMA_TENANT: Tenant name (default "default_tenant")
            CHROMA_DATABASE: Database name (default "default_database")
    
    Returns:
        ChromaDB client (PersistentClient or HttpClient)
    """
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        raise ImportError("chromadb not installed. Run: pip install chromadb")
    
    if CHROMA_CLIENT_TYPE == "cloud":
        if not CHROMA_API_KEY or not CHROMA_TENANT or not CHROMA_DATABASE:
            raise ValueError(
                "ChromaDB Cloud requires CHROMA_API_KEY, CHROMA_TENANT, and CHROMA_DATABASE environment variables. "
                "Sign up at https://www.trychroma.com/"
            )
        
        print(f"Using ChromaDB Cloud")
        print(f"Tenant: {CHROMA_TENANT}")
        print(f"Database: {CHROMA_DATABASE}")
        print(f"API Key: {CHROMA_API_KEY[:15]}...")
        
        # Use CloudClient for ChromaDB Cloud (not HttpClient)
        return chromadb.CloudClient(
            api_key=CHROMA_API_KEY,
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE
        )
    else:
        print(f"Using local ChromaDB: {CHROMA_DB_PATH}")
        return chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
