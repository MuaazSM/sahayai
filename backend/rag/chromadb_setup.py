import os
import logging
import chromadb

logger = logging.getLogger("sahayai.rag")

# Global client — initialized once on startup, used everywhere
_client = None
_collections = {}

# The 6 collections that make up Ramesh's "memory"
COLLECTION_NAMES = [
    "user_profile",       # name, age, disability, medical conditions, family
    "routines",           # daily patterns — meds, walks, meals, sleep
    "past_events",        # what happened before — falls, conversations, alerts
    "caregiver_prefs",    # Priya's alert preferences, quiet hours, sensitivity
    "communication",      # how Ramesh likes to be talked to — tone, length
    "emr_memories",       # personal memories tagged with emotions for EMR
]


def init_chromadb():
    """
    Called once on server startup. Creates the ChromaDB client and
    ensures all 6 collections exist. Uses persistent storage so
    data survives server restarts during the hackathon.
    """
    global _client, _collections

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    _client = chromadb.PersistentClient(path=persist_dir)

    for name in COLLECTION_NAMES:
        _collections[name] = _client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity for semantic search
        )
        count = _collections[name].count()
        logger.info(f"Collection '{name}' ready ({count} documents)")

    logger.info(f"ChromaDB initialized at {persist_dir} with {len(_collections)} collections")


def get_collection(name: str):
    """Grab a specific collection by name for querying or inserting"""
    if name not in _collections:
        raise ValueError(f"Unknown collection: {name}. Available: {list(_collections.keys())}")
    return _collections[name]


def get_client():
    return _client