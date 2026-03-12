import logging
import os

logger = logging.getLogger("sahayai.rag.embeddings")

# We use sentence-transformers locally — free, no API key, good enough for RAG.
# It downloads a ~90MB model on first run, then it's cached.
_model = None


def get_embedding_model():
    """
    Lazy-load the embedding model. First call takes ~2 seconds,
    subsequent calls are instant. We do this lazily because importing
    sentence_transformers is slow and we don't want to block server startup
    if RAG isn't seeded yet.
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded: all-MiniLM-L6-v2")
        except ImportError:
            logger.error("sentence-transformers not installed! pip install sentence-transformers")
            raise
    return _model


def embed_text(text: str) -> list[float]:
    """Turn a string into a 384-dimensional vector for ChromaDB"""
    model = get_embedding_model()
    return model.encode(text).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed — more efficient than calling embed_text in a loop"""
    model = get_embedding_model()
    return model.encode(texts).tolist()