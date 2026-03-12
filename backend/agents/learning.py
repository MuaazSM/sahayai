import logging
from datetime import datetime
from agents.state import AssistState

logger = logging.getLogger("sahayai.agent.learning")


async def learning_agent(state: AssistState) -> AssistState:
    """
    Last agent in the pipeline. Logs what happened, updates RAG
    with new observations, adjusts AAC baselines over time.

    For now it's mostly a logger — the full feedback loop
    (adjusting CCT baselines, refining EMR effectiveness scores,
    tuning CBD thresholds) gets built after the core demo works.
    """
    logger.info("Learning Agent running")

    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["learning"],
        "pipeline_completed_at": datetime.utcnow().isoformat(),
    }

    # Track what we'd want to learn from this interaction
    learning_notes_parts = []

    # Was the response appropriate for the risk level?
    if state.get("risk_level") in ("high", "critical") and not state.get("alert_caregiver"):
        learning_notes_parts.append("WARNING: high risk but no caregiver alert — check reasoning thresholds")

    # Did EMR get used? Track effectiveness for future retrieval tuning
    if state.get("emr_memory_used"):
        learning_notes_parts.append(f"EMR used: {state['emr_memory_used'].get('text', '')[:60]}")

    # CCT trend note
    if state.get("cct_composite"):
        composite = state["cct_composite"]
        if composite < 0.5:
            learning_notes_parts.append(f"CCT low ({composite:.2f}) — consider increasing monitoring")
        elif composite > 0.8:
            learning_notes_parts.append(f"CCT healthy ({composite:.2f}) — patient doing well")

    # CBD note
    if state.get("cbd_intervention"):
        learning_notes_parts.append(f"CBD intervention suggested: {state['cbd_intervention'][:60]}")

    updates["learning_notes"] = " | ".join(learning_notes_parts) if learning_notes_parts else "Normal interaction, no adjustments needed"
    updates["rag_updates"] = []  # placeholder for when we wire RAG writes
    updates["aac_adjustment"] = 0  # placeholder for AAC baseline shifts

    # Calculate total pipeline latency
    if state.get("pipeline_started_at"):
        try:
            started = datetime.fromisoformat(state["pipeline_started_at"])
            ended = datetime.fromisoformat(updates["pipeline_completed_at"])
            latency = int((ended - started).total_seconds() * 1000)
            updates["total_latency_ms"] = latency
            logger.info(f"Pipeline latency: {latency}ms")
        except Exception:
            pass

    logger.info(f"Learning done | notes: {updates['learning_notes'][:100]}")
    return {**state, **updates}