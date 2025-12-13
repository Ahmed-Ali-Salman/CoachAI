"""Configuration settings for CoachAI (Multimodal Learning Coach)

This module is intentionally framework-agnostic (no Streamlit/FastAPI imports).
"""

from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent

# Load .env from repository root so env vars are available to all modules.
_env_path = BASE_DIR / '.env'
if _env_path.exists():
    load_dotenv(str(_env_path))
else:
    load_dotenv()


class Config:
    """Configuration settings"""

    # Retrieval
    TOP_K = int(os.environ.get('TOP_K', '3'))

    # Generation
    TEMPERATURE = float(os.environ.get('TEMPERATURE', '0.7'))
    MAX_TOKENS = int(os.environ.get('MAX_TOKENS', '1024'))
    DO_SAMPLE = os.environ.get('DO_SAMPLE', 'true').lower() in ('1', 'true', 'yes')
    TOP_P = float(os.environ.get('TOP_P', '0.9'))
    REPETITION_PENALTY = float(os.environ.get('REPETITION_PENALTY', '1.05'))
    LENGTH_PENALTY = float(os.environ.get('LENGTH_PENALTY', '1.0'))

    # Embeddings
    EMBED_MODEL_NAME = os.environ.get('EMBED_MODEL_NAME', 'all-MiniLM-L6-v2')

    # Vision constraints (used when sending images)
    MIN_PIXELS = int(os.environ.get('MIN_PIXELS', str(224 * 224)))
    MAX_PIXELS = int(os.environ.get('MAX_PIXELS', str(1280 * 1280)))

    # --- Mistral (remote) inference configuration ---
    USE_REMOTE_MODEL = os.environ.get('USE_REMOTE_MODEL', 'true').lower() in ('1', 'true', 'yes')

    MISTRAL_API_URL = os.environ.get('MISTRAL_API_URL', 'https://api.mistral.ai')
    MODEL_NAME = os.environ.get('MODEL_NAME', 'mistral-medium-2508')
    # Backwards/compat alias used by some code paths
    MISTRAL_MODEL = MODEL_NAME

    MISTRAL_OCR_MODEL = os.environ.get('MISTRAL_OCR_MODEL', 'mistral-ocr-latest')
    MISTRAL_TIMEOUT_SECONDS = int(os.environ.get('MISTRAL_TIMEOUT_SECONDS', '60'))

    # Max image bytes to send as base64/multipart
    MISTRAL_IMAGE_MAX_BYTES = int(os.environ.get('MISTRAL_IMAGE_MAX_BYTES', str(5 * 1024 * 1024)))
    # Prefer sending image URLs when available
    MISTRAL_USE_IMAGE_URLS = os.environ.get('MISTRAL_USE_IMAGE_URLS', 'true').lower() in ('1', 'true', 'yes')

    MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')

    # Supabase
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    SUPABASE_DB_URL = os.environ.get('SUPABASE_DB_URL', '')
    SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'attachments')

    # pgvector
    PGVECTOR_DIMENSION = int(os.environ.get('PGVECTOR_DIMENSION', '384'))

    # Cohere embeddings
    COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
    COHERE_MODEL = os.environ.get('COHERE_MODEL', 'embed-english-light-v3.0')

    # Use server-side protected RAG endpoints
    USE_SERVER_SIDE_RAG = os.environ.get('USE_SERVER_SIDE_RAG', 'false').lower() in ('1', 'true', 'yes')
