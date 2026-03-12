import logging
from datetime import datetime

from agents.state import AssistState
from agents.perception import perception_agent
from agents.context import context_agent
from agents.reasoning import reasoning_agent
from agents.assistance import assistance_agent
from agents.caregiver import caregiver_agent
from agents.learning import learning_agent

logger = logging.getLogger("sahayai.pipeline")


# =====================================================
# We're not using LangGraph's graph compiler here because
# for the hackathon it's faster and more debuggable to
# wire the conditional routing by hand. Same pipeline logic
# (Sense → Remember → Reason → Act → Learn), same conditional
# branching, but without the framework overhead.
#
# LangGraph would give us visualization, checkpointing, and
# retry logic — nice for production, overkill for a 24-hour demo.
#
# ROUTING LOGIC:
#
#   Perception → Context → [needs_reasoning?]
#                              │
#                         NO ──┤── YES
#                         │         │
#                    (skip to    Reasoning
#                     Learning)     │
#                              ┌────┴────┐
#                              │         │
#                         risk=none/low  risk=medium+
#                              │         │
#                         Assistance   Assistance + Caregiver
#                           ONLY        (PARALLEL)
#                              │         │
#                              └────┬────┘
#                                   │
#                               Learning
# =====================================================


async def run_pipeline(initial_state: dict, db=None) -> AssistState:
    """
    Main entry point. Takes raw input, runs it through the agent pipeline
    with conditional routing, returns the final state with all decisions
    and outputs populated.

    The db parameter is optional — passed through to Context Agent
    for PostgreSQL lookups. If None, Context falls back to RAG-only.
    """
    state: AssistState = {
        **initial_state,
        "pipeline_started_at": datetime.utcnow().isoformat(),
        "agents_executed": [],
        "errors": [],
        "llm_calls_made": 0,
    }

    logger.info("=" * 50)
    logger.info(f"Pipeline started | trigger={state.get('trigger_type', '?')} | user={state.get('user_id', '?')}")
    logger.info("=" * 50)

    # ---------------------------------------------------------------
    # STAGE 1: PERCEPTION — turn raw input into structured events
    # Always runs. Handles voice/camera/wearable/reminder.
    # ---------------------------------------------------------------
    try:
        state = await perception_agent(state)
    except Exception as e:
        logger.error(f"Perception Agent failed: {e}")
        state["errors"] = state.get("errors", []) + [f"perception: {str(e)}"]
        # Set safe defaults so the pipeline can continue
        state["perception_summary"] = "Perception failed — limited context"
        state["detected_emotion"] = "calm"

    # ---------------------------------------------------------------
    # STAGE 2: CONTEXT — pull everything we know from RAG + DB
    # Always runs. Decides if Reasoning is needed (short-circuit).
    # ---------------------------------------------------------------
    try:
        state = await context_agent(state, db=db)
    except Exception as e:
        logger.error(f"Context Agent failed: {e}")
        state["errors"] = state.get("errors", []) + [f"context: {str(e)}"]
        state["needs_reasoning"] = True  # if context fails, play it safe and reason
        state["aac_score"] = state.get("aac_score", 70)

    # ---------------------------------------------------------------
    # SHORT-CIRCUIT CHECK
    # If Context says nothing interesting is happening (normal wearable,
    # no voice, no camera), skip straight to Learning. No LLM calls needed.
    # This is how we handle the 95% of wearable pings that are just
    # "yep, still normal" without burning Groq rate limits.
    # ---------------------------------------------------------------
    if not state.get("needs_reasoning", True):
        logger.info("Short-circuit: skipping Reasoning/Assistance/Caregiver")
        state["risk_level"] = "none"
        state["response_text"] = ""  # nothing to say to the user
        state["alert_caregiver"] = False

        try:
            state = await learning_agent(state)
        except Exception as e:
            logger.error(f"Learning Agent failed: {e}")
            state["errors"] = state.get("errors", []) + [f"learning: {str(e)}"]

        _log_pipeline_summary(state)
        return state

    # ---------------------------------------------------------------
    # STAGE 3: REASONING — assess risk, decide actions
    # ---------------------------------------------------------------
    try:
        state = await reasoning_agent(state)
    except Exception as e:
        logger.error(f"Reasoning Agent failed: {e}")
        state["errors"] = state.get("errors", []) + [f"reasoning: {str(e)}"]
        # Safe defaults — don't alert caregiver on reasoning failure
        # because we don't actually know if something is wrong
        state["risk_level"] = state.get("risk_level", "low")
        state["alert_caregiver"] = False
        state["trigger_emr"] = False

    # ---------------------------------------------------------------
    # STAGE 4: CONDITIONAL ROUTING
    #
    # This is the key decision point:
    #
    # risk = none/low → Assistance Agent ONLY
    #   User gets a response, caregiver is left alone. No point
    #   bugging Priya every time Ramesh asks what's for lunch.
    #
    # risk = medium/high/critical → Assistance + Caregiver PARALLEL
    #   User gets help AND caregiver gets alerted simultaneously.
    #   We don't wait for one to finish before starting the other.
    #   In a real async setup we'd use asyncio.gather() here.
    # ---------------------------------------------------------------
    risk = state.get("risk_level", "none")
    should_alert = state.get("alert_caregiver", False)

    if risk in ("medium", "high", "critical") or should_alert:
        # --- PARALLEL PATH: both agents run ---
        logger.info(f"PARALLEL routing: risk={risk}, alert={should_alert}")
        logger.info("Running Assistance + Caregiver agents in parallel")

        # Run both — we want both the user response AND the caregiver alert
        # Using sequential await for now because error handling is cleaner.
        # In production, asyncio.gather with return_exceptions=True.
        try:
            state = await assistance_agent(state)
        except Exception as e:
            logger.error(f"Assistance Agent failed: {e}")
            state["errors"] = state.get("errors", []) + [f"assistance: {str(e)}"]
            state["response_text"] = "I'm here with you. Help is on the way."

        try:
            state = await caregiver_agent(state)
        except Exception as e:
            logger.error(f"Caregiver Agent failed: {e}")
            state["errors"] = state.get("errors", []) + [f"caregiver: {str(e)}"]

    else:
        # --- USER-ONLY PATH: just Assistance ---
        logger.info(f"USER-ONLY routing: risk={risk}")

        try:
            state = await assistance_agent(state)
        except Exception as e:
            logger.error(f"Assistance Agent failed: {e}")
            state["errors"] = state.get("errors", []) + [f"assistance: {str(e)}"]
            state["response_text"] = "I'm here if you need me."

    # ---------------------------------------------------------------
    # STAGE 5: LEARNING — log outcomes, update RAG, adjust baselines
    # Always runs. Even on errors — we want to learn from failures.
    # ---------------------------------------------------------------
    try:
        state = await learning_agent(state)
    except Exception as e:
        logger.error(f"Learning Agent failed: {e}")
        state["errors"] = state.get("errors", []) + [f"learning: {str(e)}"]

    _log_pipeline_summary(state)
    return state


def _log_pipeline_summary(state: AssistState):
    """Print a clean summary of what the pipeline did for debugging"""
    agents = state.get("agents_executed", [])
    risk = state.get("risk_level", "?")
    llm_calls = state.get("llm_calls_made", 0)
    latency = state.get("total_latency_ms", "?")
    errors = state.get("errors", [])

    logger.info("=" * 50)
    logger.info(f"Pipeline complete")
    logger.info(f"  Agents: {' → '.join(agents)}")
    logger.info(f"  Risk: {risk}")
    logger.info(f"  LLM calls: {llm_calls}")
    logger.info(f"  Latency: {latency}ms")
    if errors:
        logger.warning(f"  Errors: {errors}")
    if state.get("alert_caregiver"):
        logger.info(f"  Alert: {state.get('alert_priority', '?')} → {state.get('alert_message', '')[:60]}")
    if state.get("trigger_emr"):
        logger.info(f"  EMR triggered")
    logger.info("=" * 50)