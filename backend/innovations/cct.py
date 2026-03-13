"""
CCT — Conversational Cognitive Tracking
=========================================
Silent, real-time cognitive scoring on every patient conversation turn.
Scores 6 dimensions: recall accuracy, response latency, vocabulary richness,
temporal orientation, narrative coherence, semantic consistency.

The user never knows this is happening — it's invisible background analysis.
The caregiver sees the composite trend on their dashboard as a 14-day line chart.

Called by the Assistance Agent on every patient voice turn.
Scores are persisted by the conversation route to the cct_scores table.
"""
import json
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("sahayai.cct")

CCT_DIMENSIONS = [
    "recall_accuracy",
    "response_latency",
    "vocabulary_richness",
    "temporal_orientation",
    "narrative_coherence",
    "semantic_consistency",
]


async def compute_cct_scores(
    user_message: str,
    user_name: str,
    perception_summary: str = "",
) -> dict:
    """
    Score a patient's message across all 6 CCT dimensions.
    Returns a dict with individual scores + composite (0.0 to 1.0 each).

    Scoring rubric:
    - 0.0-0.3: Significant impairment, flag for clinical review
    - 0.3-0.6: Moderate impairment, increase monitoring
    - 0.6-0.8: Mild impairment, typical for elderly
    - 0.8-1.0: Healthy range, back off assistance

    Called by assistance_agent._run_cct_scoring() and also directly
    importable for testing or batch scoring past conversations.
    """
    from utils.llm import chat_completion

    prompt = f"""Score this patient's cognitive state from their latest message.

Patient: {user_name}
Context: {perception_summary}
Message: "{user_message}"

Score each dimension 0.0 (severe impairment) to 1.0 (perfectly normal):
- recall_accuracy: Can they reference recent events correctly?
- response_latency: Is their speech/text fluent and appropriately paced?
- vocabulary_richness: Are they using varied, appropriate words?
- temporal_orientation: Do they know what time/day/place it is?
- narrative_coherence: Does their message follow a logical thread?
- semantic_consistency: Is it consistent with known facts and prior statements?

Return ONLY JSON:
{{"recall_accuracy": 0.0, "response_latency": 0.0, "vocabulary_richness": 0.0, "temporal_orientation": 0.0, "narrative_coherence": 0.0, "semantic_consistency": 0.0, "composite": 0.0}}

Composite = average of all 6. Healthy elderly people score 0.65-0.85, not perfect 1.0s."""

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_preference="structured",  # qwen 32b — reliable JSON output
            temperature=0.1,
            max_tokens=256,
        )

        cleaned = raw.strip()
        # Strip markdown code fences
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        # Strip deepseek <think> blocks
        if "<think>" in cleaned:
            think_end = cleaned.find("</think>")
            if think_end != -1:
                cleaned = cleaned[think_end + 8:]

        scores = json.loads(cleaned.strip())

        # Clamp all values to 0.0-1.0
        for key in CCT_DIMENSIONS + ["composite"]:
            if key in scores:
                scores[key] = max(0.0, min(1.0, float(scores[key])))

        # Recompute composite from dimensions if it's missing or zero
        dim_scores = [scores.get(k, 0.0) for k in CCT_DIMENSIONS]
        if not scores.get("composite") and any(s > 0 for s in dim_scores):
            scores["composite"] = round(sum(dim_scores) / len(dim_scores), 3)

        logger.debug(f"CCT scores: {scores}")
        return scores

    except Exception as e:
        logger.warning(f"CCT scoring failed: {e}")
        return _empty_scores()


async def save_cct_score(
    user_id: str,
    scores: dict,
    db,
    conversation_id: str | None = None,
) -> str | None:
    """
    Persist CCT scores to the cct_scores table.
    Returns the new row ID on success, None on failure.

    Called from the conversation route after the pipeline completes,
    so the route owns the DB commit — we just add the row here.
    """
    try:
        from api.models.tables import CCTScore

        score_row = CCTScore(
            id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=conversation_id,
            recall_accuracy=scores.get("recall_accuracy", 0.0),
            response_latency=scores.get("response_latency", 0.0),
            vocabulary_richness=scores.get("vocabulary_richness", 0.0),
            temporal_orientation=scores.get("temporal_orientation", 0.0),
            narrative_coherence=scores.get("narrative_coherence", 0.0),
            semantic_consistency=scores.get("semantic_consistency", 0.0),
            composite_score=scores.get("composite", 0.0),
            scored_at=datetime.utcnow(),
        )
        db.add(score_row)
        logger.info(
            f"CCT score queued for user={user_id} "
            f"composite={scores.get('composite', 0.0):.2f}"
        )
        return score_row.id
    except Exception as e:
        logger.warning(f"Failed to save CCT score: {e}")
        return None


async def get_cct_trend(
    user_id: str,
    days: int = 14,
    db=None,
) -> list[dict]:
    """
    Retrieve CCT composite scores for the last N days, grouped by day.
    Used by:
    - /caregiver/trends/{patient_id} endpoint
    - Caregiver Agent when generating summaries
    - Learning Agent when adjusting AAC baseline

    Returns a list of dicts: [{"date": "2026-03-13", "cct_score": 0.73, ...}]
    """
    if db is None:
        return []

    try:
        from sqlalchemy import select, and_, func
        from api.models.tables import CCTScore, AACScore

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get CCT scores grouped by day — pick max per day (best of day)
        result = await db.execute(
            select(CCTScore)
            .where(and_(
                CCTScore.user_id == user_id,
                CCTScore.scored_at >= cutoff,
            ))
            .order_by(CCTScore.scored_at.asc())
        )
        all_scores = result.scalars().all()

        # Group by date and average within each day
        by_day: dict[str, list[float]] = {}
        for s in all_scores:
            day = s.scored_at.strftime("%Y-%m-%d")
            by_day.setdefault(day, []).append(s.composite_score)

        # Get AAC scores for the same window to include in trend
        aac_result = await db.execute(
            select(AACScore)
            .where(and_(
                AACScore.user_id == user_id,
                AACScore.calculated_at >= cutoff,
            ))
            .order_by(AACScore.calculated_at.asc())
        )
        aac_scores = aac_result.scalars().all()

        aac_by_day: dict[str, list[int]] = {}
        for a in aac_scores:
            day = a.calculated_at.strftime("%Y-%m-%d")
            aac_by_day.setdefault(day, []).append(a.score)

        trend = []
        for day in sorted(by_day.keys()):
            cct_vals = by_day[day]
            aac_vals = aac_by_day.get(day, [])
            trend.append({
                "date": day,
                "cct_score": round(sum(cct_vals) / len(cct_vals), 3),
                "aac_score": round(sum(aac_vals) / len(aac_vals), 1) if aac_vals else None,
                "conversation_count": len(cct_vals),
            })

        return trend

    except Exception as e:
        logger.warning(f"CCT trend retrieval failed: {e}")
        return []


def _empty_scores() -> dict:
    """Return zeroed scores — used when the LLM call fails."""
    return {k: 0.0 for k in CCT_DIMENSIONS + ["composite"]}
