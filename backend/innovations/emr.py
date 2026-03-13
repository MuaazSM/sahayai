"""
EMR — Emotional Memory Reinforcement
======================================
When a patient is distressed, confused, or agitated, we retrieve personal
memories from ChromaDB and weave the best-matching one into the AI's response.

The science: Autobiographical memories (your daughter's first bicycle, your
wedding, your favourite song) remain accessible even when working memory is
severely impaired. Recalling a positive personal memory can interrupt a
distress spiral and provide a moment of calm orientation.

The system:
1. Context Agent pre-fetches 3 EMR candidates from ChromaDB on every turn
   where emotion is confused/distressed/agitated.
2. Assistance Agent calls select_best_memory() to pick the top candidate.
3. The selected memory text is woven into the response naturally.
4. record_emr_use() logs the event so Learning Agent can track effectiveness.
"""
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("sahayai.emr")

# Emotion → search query mapping for ChromaDB retrieval
# (This mirrors the map in rag/retriever.py::retrieve_emr_memories)
EMOTION_QUERIES = {
    "confused": "comforting familiar memory, family, home, safety",
    "distressed": "happy memory, joy, love, warmth, family togetherness",
    "agitated": "calm peaceful memory, relaxation, nature, music",
    "calm": "pleasant memory, everyday happiness",
    "happy": "shared joy, celebration, family",
}


def select_best_memory(candidates: list[dict], emotion: str) -> dict | None:
    """
    Pick the single best EMR memory from pre-fetched candidates.

    Selection criteria (in priority order):
    1. Lowest ChromaDB distance (most semantically similar to current state)
    2. Higher past effectiveness count (worked well before)
    3. Fallback: first candidate

    Args:
        candidates: List of ChromaDB result dicts with keys:
                    id, text, metadata (dict), distance (float, lower=better)
        emotion: Current detected emotion (confused/distressed/agitated/etc.)

    Returns:
        Best candidate dict, or None if no candidates.
    """
    if not candidates:
        return None

    # Sort by distance ascending, then by effectiveness count descending
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            c.get("distance") if c.get("distance") is not None else 1.0,
            -(c.get("metadata", {}).get("effectiveness_count", 0)),
        )
    )

    best = sorted_candidates[0]
    logger.info(
        f"EMR selected: '{best.get('text', '')[:60]}' "
        f"(dist={best.get('distance', 'N/A')}, emotion={emotion})"
    )
    return best


def extract_memory_text(memory: dict | None) -> str:
    """
    Safely extract the display text from an EMR memory dict.
    Handles ChromaDB format, plain strings, and None.
    """
    if memory is None:
        return ""
    if isinstance(memory, str):
        return memory
    return memory.get("text", "") or memory.get("content", "") or ""


async def retrieve_for_emotion(
    user_id: str,
    emotion: str,
    n: int = 3,
) -> list[dict]:
    """
    Fetch EMR candidates for a given emotion directly (bypassing Context Agent
    pre-fetch). Used when emotion changes mid-pipeline or in tests.
    """
    try:
        from rag.retriever import retrieve_emr_memories
        return retrieve_emr_memories(user_id, emotion=emotion, n=n)
    except Exception as e:
        logger.warning(f"Direct EMR retrieval failed: {e}")
        return []


async def record_emr_use(
    user_id: str,
    memory: dict,
    emotion_at_trigger: str,
    response_text: str,
    db,
) -> None:
    """
    Log an EMR use event so the Learning Agent can track effectiveness.

    We write to the events table (not a dedicated EMR table) because:
    - The events table is already the audit trail for everything
    - The Learning Agent already reads events to learn
    - Keeps the DB schema simple

    The metadata_json captures enough detail for the Learning Agent to
    update the memory's effectiveness_count in ChromaDB later.
    """
    if db is None:
        return

    try:
        import json
        from api.models.tables import Event

        memory_id = memory.get("id", "unknown") if isinstance(memory, dict) else "unknown"
        memory_text = extract_memory_text(memory)

        event = Event(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type="emr_triggered",
            severity="info",
            description=f"EMR memory used for emotion: {emotion_at_trigger}",
            metadata_json=json.dumps({
                "memory_id": memory_id,
                "memory_text": memory_text[:200],
                "emotion": emotion_at_trigger,
                "response_preview": response_text[:150],
            }),
            timestamp=datetime.utcnow(),
        )
        db.add(event)
        logger.info(f"EMR use recorded: memory_id={memory_id}, emotion={emotion_at_trigger}")

    except Exception as e:
        logger.warning(f"Failed to record EMR use: {e}")


async def get_emr_history(
    user_id: str,
    limit: int = 10,
    db=None,
) -> list[dict]:
    """
    Return recent EMR events for a user.
    Used by the Learning Agent to identify:
    - Which memories are triggered most often
    - Which emotions occur most frequently
    - Whether to add more memories to ChromaDB

    Returns list of dicts with: event_id, memory_id, emotion, timestamp
    """
    if db is None:
        return []

    try:
        import json
        from sqlalchemy import select
        from api.models.tables import Event

        result = await db.execute(
            select(Event)
            .where(Event.user_id == user_id, Event.event_type == "emr_triggered")
            .order_by(Event.timestamp.desc())
            .limit(limit)
        )
        events = result.scalars().all()

        history = []
        for e in events:
            meta = {}
            try:
                meta = json.loads(e.metadata_json or "{}")
            except Exception:
                pass
            history.append({
                "event_id": e.id,
                "memory_id": meta.get("memory_id"),
                "emotion": meta.get("emotion"),
                "memory_text": meta.get("memory_text", ""),
                "timestamp": e.timestamp.isoformat(),
            })
        return history

    except Exception as e:
        logger.warning(f"EMR history retrieval failed: {e}")
        return []


async def get_emr_effectiveness_summary(
    user_id: str,
    db=None,
) -> dict:
    """
    Summarize EMR effectiveness metrics for the Learning Agent.
    Returns counts by emotion and frequency of EMR triggering over 30 days.
    """
    history = await get_emr_history(user_id, limit=100, db=db)

    by_emotion: dict[str, int] = {}
    by_memory: dict[str, int] = {}

    for entry in history:
        emotion = entry.get("emotion", "unknown")
        memory_id = entry.get("memory_id", "unknown")
        by_emotion[emotion] = by_emotion.get(emotion, 0) + 1
        by_memory[memory_id] = by_memory.get(memory_id, 0) + 1

    return {
        "total_triggers": len(history),
        "by_emotion": by_emotion,
        "most_used_memories": sorted(
            by_memory.items(), key=lambda x: x[1], reverse=True
        )[:5],
    }
