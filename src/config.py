import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

CORPUS_DIR = Path(os.getenv("CORPUS_DIR", ROOT / "gen_ai_takehome_sample_corpus"))
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "lexcite-index")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "high")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "6"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "2"))