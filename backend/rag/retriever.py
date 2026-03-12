import logging
from rag.chromadb_setup import get_collection
from rag.embeddings import embed_text

logger = logging.getLogger("sahayai.rag.retriever")


def retrieve_profile(user_id: str) -> list[dict]:
    """
    Get everything we know about this person — name, age, conditions,
    family, address. Usually just 1-3 documents.
    """
    collection = get_collection("user_profile")
    results = collection.get(
        where={"user_id": user_id},
        limit=10,
    )
    return _format_results(results)


def retrieve_routines(user_id: str, time_of_day: str = None) -> list[dict]:
    """
    Get the person's daily routines. If time_of_day is provided,
    we do a semantic search to find routines relevant to that time
    (e.g., "morning" finds medication + walk routines).
    """
    collection = get_collection("routines")

    if time_of_day:
        # Semantic search — "morning" matches "8 AM medication"
        query_embedding = embed_text(f"{time_of_day} routine activity")
        results = collection.query(
            query_embeddings=[query_embedding],
            where={"user_id": user_id},
            n_results=5,
        )
        return _format_query_results(results)
    else:
        results = collection.get(
            where={"user_id": user_id},
            limit=20,
        )
        return _format_results(results)


def retrieve_recent_events(user_id: str, query: str = "recent events", n: int = 5) -> list[dict]:
    """
    Semantic search over past events. Finds events related to whatever
    is happening now — e.g., if user is wandering, pulls up past
    wandering episodes so the Reasoning Agent has history.
    """
    collection = get_collection("past_events")
    query_embedding = embed_text(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        where={"user_id": user_id},
        n_results=n,
    )
    return _format_query_results(results)


def retrieve_caregiver_prefs(caregiver_id: str) -> list[dict]:
    """
    How does the caregiver want to be notified? Quiet hours?
    Alert sensitivity? This shapes how the Caregiver Agent behaves.
    """
    collection = get_collection("caregiver_prefs")
    results = collection.get(
        where={"caregiver_id": caregiver_id},
        limit=10,
    )
    return _format_results(results)


def retrieve_communication_prefs(user_id: str) -> list[dict]:
    """
    How does this person like to be talked to? Short sentences?
    Formal or casual? Uses their name a lot? The Assistance Agent
    adapts its tone based on this.
    """
    collection = get_collection("communication")
    results = collection.get(
        where={"user_id": user_id},
        limit=5,
    )
    return _format_results(results)


def retrieve_emr_memories(user_id: str, emotion: str, n: int = 3) -> list[dict]:
    """
    EMR — Emotional Memory Reinforcement.
    When the person is distressed/confused/agitated, we search for
    personal memories tagged with positive emotions that might calm them.
    
    e.g., user is confused → retrieve memory about "Priya learning to ride
    a bicycle" because that's tagged as joy/comfort and has been effective before.
    """
    collection = get_collection("emr_memories")

    # Search for memories that match a calming context for this emotion
    query_map = {
        "confused": "comforting familiar memory, family, home, safety",
        "distressed": "happy memory, joy, love, warmth, family togetherness",
        "agitated": "calm peaceful memory, relaxation, nature, music",
        "calm": "pleasant memory, everyday happiness",
        "happy": "shared joy, celebration, family",
    }
    search_query = query_map.get(emotion, "comforting memory")
    query_embedding = embed_text(search_query)

    results = collection.query(
        query_embeddings=[query_embedding],
        where={"user_id": user_id},
        n_results=n,
    )
    return _format_query_results(results)


def add_document(collection_name: str, doc_id: str, text: str, metadata: dict):
    """
    Add a new document to any collection. Used by the Learning Agent
    to update RAG with new events, adjusted routines, etc.
    """
    collection = get_collection(collection_name)
    embedding = embed_text(text)
    collection.add(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )
    logger.info(f"Added doc {doc_id} to {collection_name}")


def update_document(collection_name: str, doc_id: str, text: str, metadata: dict):
    """Update an existing document in a collection"""
    collection = get_collection(collection_name)
    embedding = embed_text(text)
    collection.update(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )


# =====================================================
# Result formatting helpers
# =====================================================

def _format_results(results: dict) -> list[dict]:
    """Turn ChromaDB .get() results into a clean list of dicts"""
    if not results or not results.get("ids"):
        return []

    docs = []
    for i, doc_id in enumerate(results["ids"]):
        docs.append({
            "id": doc_id,
            "text": results["documents"][i] if results.get("documents") else "",
            "metadata": results["metadatas"][i] if results.get("metadatas") else {},
        })
    return docs


def _format_query_results(results: dict) -> list[dict]:
    """Turn ChromaDB .query() results into a clean list of dicts"""
    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        docs.append({
            "id": doc_id,
            "text": results["documents"][0][i] if results.get("documents") else "",
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })
    return docs