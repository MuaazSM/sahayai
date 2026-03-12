import asyncio
import logging
from datetime import datetime

from agents.state import AssistState
from agents.perception import perception_agent
from agents.context import context_agent
from agents.reasoning import reasoning_agent
from agents.assistance import assistance_agent
from agents.caregiver import caregiver_agent
from agents.learning import learning_agent
from utils.async_helpers import run_parallel, run_with_fallback

logger = logging.getLogger("sahayai.pipeline")

# =====================================================
# PIPELINE ROUTING (same logic, now truly parallel)
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
#                           ONLY        (TRULY PARALLEL)
#                              │         │
#                              └────┬────┘
#                                   │
#                               Learning (fire-and-forget)
# =====================================================


async def run_pipeline(initial_state: dict, db=None) -> AssistState:
    state: AssistState = {
        **initial_state,
        "pipeline_started_at": datetime.utcnow().isoformat(),
        "agents_executed": [],
        "errors": [],
        "llm_calls_made": 0,
    }

    logger.info(f"Pipeline started | trigger={state.get('trigger_type', '?')} | user={state.get('user_id', '?')}")

    # ---------------------------------------------------------------
    # STAGE 1 + 2: PERCEPTION → CONTEXT (sequential — each depends on previous)
    # These are fast: perception is local ML + one emotion LLM call,
    # context is DB queries + RAG lookups.
    # ---------------------------------------------------------------
    try:
        state = await asyncio.wait_for(
            perception_agent(state),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        logger.error("Perception timed out after 10s")
        state["errors"] = state.get("errors", []) + ["perception: timeout"]
        state["perception_summary"] = "Perception timed out"
        state["detected_emotion"] = "calm"
    except Exception as e:
        logger.error(f"Perception failed: {e}")
        state["errors"] = state.get("errors", []) + [f"perception: {str(e)}"]
        state["perception_summary"] = "Perception failed"
        state["detected_emotion"] = "calm"

    try:
        state = await asyncio.wait_for(
            context_agent(state, db=db),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        logger.error("Context timed out after 8s")
        state["errors"] = state.get("errors", []) + ["context: timeout"]
        state["needs_reasoning"] = True
        state["aac_score"] = state.get("aac_score", 70)
    except Exception as e:
        logger.error(f"Context failed: {e}")
        state["errors"] = state.get("errors", []) + [f"context: {str(e)}"]
        state["needs_reasoning"] = True
        state["aac_score"] = state.get("aac_score", 70)

    # ---------------------------------------------------------------
    # SHORT-CIRCUIT — normal wearable ping, nothing to do
    # Zero LLM calls, returns in <100ms
    # ---------------------------------------------------------------
    if not state.get("needs_reasoning", True):
        logger.info("Short-circuit: normal reading, skipping all LLM agents")
        state["risk_level"] = "none"
        state["response_text"] = ""
        state["alert_caregiver"] = False
        state["pipeline_completed_at"] = datetime.utcnow().isoformat()
        state["agents_executed"] = state.get("agents_executed", []) + ["learning(skipped)"]
        _log_pipeline_summary(state)
        return state

    # ---------------------------------------------------------------
    # STAGE 3: REASONING (sequential — everything after depends on its output)
    # This is the one LLM call we can't parallelize because Assistance
    # and Caregiver both need its risk assessment.
    # ---------------------------------------------------------------
    try:
        state = await asyncio.wait_for(
            reasoning_agent(state),
            timeout=12.0,
        )
    except asyncio.TimeoutError:
        logger.error("Reasoning timed out — defaulting to safe low risk")
        state["errors"] = state.get("errors", []) + ["reasoning: timeout"]
        state["risk_level"] = "low"
        state["alert_caregiver"] = False
        state["trigger_emr"] = False
        state["suggested_response_direction"] = "I'm here to help."
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        state["errors"] = state.get("errors", []) + [f"reasoning: {str(e)}"]
        state["risk_level"] = "low"
        state["alert_caregiver"] = False
        state["trigger_emr"] = False

    # ---------------------------------------------------------------
    # STAGE 4: CONDITIONAL PARALLEL ROUTING
    # This is where the real speed win happens.
    #
    # LOW RISK: just Assistance (one fast LLM call)
    # MEDIUM+ RISK: Assistance + Caregiver run AT THE SAME TIME
    #   instead of sequentially. Saves ~2-3 seconds on critical alerts.
    # ---------------------------------------------------------------
    risk = state.get("risk_level", "none")
    should_alert = state.get("alert_caregiver", False)

    if risk in ("medium", "high", "critical") or should_alert:
        logger.info(f"PARALLEL routing: risk={risk}")

        # Both agents get the same state snapshot and run simultaneously.
        # asyncio.gather fires both coroutines concurrently.
        results = await run_parallel(
            _run_assistance_safe(state),
            _run_caregiver_safe(state, db=db),
            timeout=15.0,
        )

        assistance_result, caregiver_result = results

        # Merge results — assistance owns response_text, caregiver owns alerts
        if isinstance(assistance_result, dict):
            state = {**state, **assistance_result}
        else:
            logger.error(f"Assistance parallel failed: {assistance_result}")
            state["response_text"] = "I'm here with you. Help is on the way."
            state["agents_executed"] = state.get("agents_executed", []) + ["assistance(failed)"]

        if isinstance(caregiver_result, dict):
            # Don't let caregiver overwrite response_text — that's the user's response
            response_text = state.get("response_text", "")
            state = {**state, **caregiver_result}
            if response_text:
                state["response_text"] = response_text
        else:
            logger.error(f"Caregiver parallel failed: {caregiver_result}")
            state["agents_executed"] = state.get("agents_executed", []) + ["caregiver(failed)"]

    else:
        logger.info(f"USER-ONLY routing: risk={risk}")

        try:
            state = await asyncio.wait_for(
                assistance_agent(state),
                timeout=12.0,
            )
        except asyncio.TimeoutError:
            logger.error("Assistance timed out")
            state["errors"] = state.get("errors", []) + ["assistance: timeout"]
            state["response_text"] = "I'm here if you need me."
        except Exception as e:
            logger.error(f"Assistance failed: {e}")
            state["errors"] = state.get("errors", []) + [f"assistance: {str(e)}"]
            state["response_text"] = "I'm here if you need me."

    # ---------------------------------------------------------------
    # STAGE 5: LEARNING — fire and don't wait
    # Learning just logs stuff and updates RAG. No reason to make
    # the user wait for it. We kick it off and move on.
    # ---------------------------------------------------------------
    asyncio.create_task(_run_learning_background(state))

    state["pipeline_completed_at"] = datetime.utcnow().isoformat()
    _log_pipeline_summary(state)
    return state


# =====================================================
# SAFE WRAPPERS — for use in asyncio.gather
# These catch exceptions and return them as dicts with error info
# instead of letting them bubble up and kill the whole gather
# =====================================================

async def _run_assistance_safe(state: AssistState) -> dict:
    """Wrapper so assistance failures don't kill the parallel gather"""
    try:
        result = await assistance_agent(state)
        # Return only the fields assistance owns
        return {
            "response_text": result.get("response_text", ""),
            "emr_memory_used": result.get("emr_memory_used"),
            "cct_scores": result.get("cct_scores", {}),
            "cct_composite": result.get("cct_composite"),
            "agents_executed": result.get("agents_executed", []),
            "llm_calls_made": result.get("llm_calls_made", 0),
        }
    except Exception as e:
        logger.error(f"Assistance agent failed in parallel: {e}")
        return {
            "response_text": "I'm here with you.",
            "agents_executed": state.get("agents_executed", []) + ["assistance(failed)"],
            "llm_calls_made": state.get("llm_calls_made", 0),
        }


async def _run_caregiver_safe(state: AssistState, db=None) -> dict:
    """Wrapper so caregiver failures don't kill the parallel gather"""
    try:
        result = await caregiver_agent(state, db=db)
        return {
            "caregiver_alert_payload": result.get("caregiver_alert_payload"),
            "caregiver_summary": result.get("caregiver_summary"),
            "cbd_score": result.get("cbd_score", 0),
            "cbd_intervention": result.get("cbd_intervention"),
            "agents_executed": result.get("agents_executed", []),
            "llm_calls_made": result.get("llm_calls_made", 0),
        }
    except Exception as e:
        logger.error(f"Caregiver agent failed in parallel: {e}")
        return {
            "caregiver_alert_payload": None,
            "cbd_score": 0,
            "agents_executed": state.get("agents_executed", []) + ["caregiver(failed)"],
            "llm_calls_made": state.get("llm_calls_made", 0),
        }


async def _run_learning_background(state: AssistState):
    """
    Fire-and-forget learning. Runs after the response is already
    sent to the user so it adds zero latency to the user experience.
    """
    try:
        await learning_agent(state)
    except Exception as e:
        logger.warning(f"Background learning failed (non-critical): {e}")


def _log_pipeline_summary(state: AssistState):
    agents = state.get("agents_executed", [])
    risk = state.get("risk_level", "?")
    llm_calls = state.get("llm_calls_made", 0)
    errors = state.get("errors", [])

    # Calculate latency
    latency_str = "?"
    try:
        started = datetime.fromisoformat(state["pipeline_started_at"])
        ended = datetime.fromisoformat(state["pipeline_completed_at"])
        latency_ms = int((ended - started).total_seconds() * 1000)
        state["total_latency_ms"] = latency_ms
        latency_str = f"{latency_ms}ms"
    except Exception:
        pass

    logger.info("=" * 50)
    logger.info(f"Pipeline complete | {latency_str}")
    logger.info(f"  Agents: {' → '.join(agents)}")
    logger.info(f"  Risk: {risk} | LLM calls: {llm_calls}")
    if errors:
        logger.warning(f"  Errors: {errors}")
    if state.get("alert_caregiver"):
        logger.info(f"  Alert: {state.get('alert_priority', '?')}")
    logger.info("=" * 50)