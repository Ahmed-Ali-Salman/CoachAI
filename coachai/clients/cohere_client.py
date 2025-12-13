"""Simple Cohere embeddings client wrapper."""

from typing import List, Optional

try:
    import cohere
except Exception:
    cohere = None

from coachai.core.config import Config


class CohereClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or Config.COHERE_API_KEY
        # Prefer a 384-dim embed model by default to match PGVECTOR_DIMENSION=384.
        cfg_model = Config.COHERE_MODEL
        if isinstance(cfg_model, str) and cfg_model.strip().lower() in ('small', 'medium', 'large'):
            cfg_model = ''
        self.model = model or cfg_model or 'embed-english-light-v3.0'
        self._client = None
        if self.api_key and cohere is not None:
            try:
                self._client = cohere.Client(self.api_key)
            except Exception:
                self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.is_available():
            raise RuntimeError('Cohere client is not available or COHERE_API_KEY not set')
        # Support multiple Cohere SDK versions.
        try:
            resp = self._client.embeddings.create(model=self.model, texts=texts)
            vectors = [e.embedding for e in resp.embeddings]
        except Exception:
            # Older SDKs
            resp = self._client.embed(model=self.model, texts=texts)
            vectors = resp.embeddings

        dim = getattr(Config, 'PGVECTOR_DIMENSION', 384) or 384
        if vectors and len(vectors[0]) != int(dim):
            raise RuntimeError(f'Cohere embedding dimension {len(vectors[0])} does not match PGVECTOR_DIMENSION={dim}. Update COHERE_MODEL or PGVECTOR_DIMENSION.')
        return vectors
