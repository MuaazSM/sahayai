import json
import logging
from agents.state import AssistState
from utils.llm import chat_completion

logger = logging.getLogger("sahayai.agent.reasoning")

# Load prompt once
try:
    with open("prompts/reasoning_agent.txt", "r") as f:
        REASONING_PROMPT = f.read()
except FileNotFoundError:
    REASONING_PROMPT = "You are a reasoning agent. Assess risk and decide actions. Return JSON."


async def reasoning_agent(state: AssistState) -> AssistState:
    """
    The brain of the pipeline. Looks at everything Perception and Context
    gathered and makes the big decisions:
    - How risky is this situation?
    - Should we bother the caregiver?
    - Should EMR kick in with a calming memory?
    - What's the general direction of our response?

    Uses the quality model (70b) because bad judgment here means
    either missing a real emergency or crying wolf and burning out
    the caregiver with false alarms. Both are bad.
    """
    logger.info(f"Reasoning Agent running | user={state.get('user_name', 'unknown')}")

    # If Context Agent said skip reasoning, we bail with safe defaults
    if not state.get("needs_reasoning", True):
        logger.info("Reasoning skipped — Context Agent short-circuited")
        return {
            **state,
            "request_type": "passive",
            "risk_level": "none",
            "alert_caregiver": False,
            "alert_priority": "routine",
            "alert_message": "",
            "trigger_emr": False,
            "reasoning_text": "Normal wearable reading, no input. No action needed.",
            "suggested_response_direction": "",
            "agents_executed": state.get("agents_executed", []) + ["reasoning(skipped)"],
        }

    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["reasoning"],
    }

    # ---------------------------------------------------------------
    # Build the big context dump for the Reasoning Agent
    # Everything it needs to make a good decision in one shot
    # ---------------------------------------------------------------
    aac = state.get("aac_score", 70)

    situation_parts = []

    # What the user said (if anything)
    if state.get("user_message"):
        situation_parts.append(f'User message: "{state["user_message"]}"')

    # Camera results
    if state.get("scene_description"):
        situation_parts.append(f"Camera: {state['scene_description']}")
        if state.get("obstacles"):
            obs_str = ", ".join([
                f"{o.get('type', '?')} {o.get('distance', '?')} {o.get('direction', '?')}"
                for o in state["obstacles"]
            ])
            situation_parts.append(f"Obstacles: {obs_str}")

    # Wearable classification
    if state.get("wearable_classification"):
        situation_parts.append(
            f"Wearable: {state['wearable_classification']} "
            f"(confidence={state.get('wearable_confidence', 0):.0%}), "
            f"HR={state.get('heart_rate', '?')}bpm"
        )

    # Emotion detected from voice
    if state.get("detected_emotion") and state["detected_emotion"] != "calm":
        situation_parts.append(f"Detected emotion: {state['detected_emotion']}")

    # EMR candidates available
    if state.get("emr_candidates"):
        mem_previews = [m.get("text", "")[:60] for m in state["emr_candidates"][:2]]
        situation_parts.append(f"EMR memories available: {mem_previews}")

    situation_text = "\n".join(situation_parts) if situation_parts else "No specific situation data."

    # Profile context from the Context Agent
    profile_context = state.get("user_profile_context", f"User: {state.get('user_name', 'unknown')}, AAC: {aac}")

    prompt = f"""{profile_context}

--- CURRENT SITUATION ---
{situation_text}

Perception summary: {state.get('perception_summary', 'none')}
Trigger type: {state.get('trigger_type', 'unknown')}

Analyze this situation and decide what to do."""

    messages = [
        {"role": "system", "content": REASONING_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # ---------------------------------------------------------------
    # Call the quality model — this decision matters
    # ---------------------------------------------------------------
    raw = await chat_completion(
        messages=messages,
        model_preference="quality",  # 70b — judgment calls need the big model
        temperature=0.2,             # low temp for consistent decisions
        max_tokens=512,
    )
    updates["llm_calls_made"] = state.get("llm_calls_made", 0) + 1

    # ---------------------------------------------------------------
    # Parse the structured JSON response
    # ---------------------------------------------------------------
    parsed = _parse_reasoning_output(raw)

    updates["request_type"] = parsed.get("request_type", "chat")
    updates["risk_level"] = parsed.get("risk_level", "none")
    updates["alert_caregiver"] = parsed.get("alert_caregiver", False)
    updates["alert_priority"] = parsed.get("alert_priority", "routine")
    updates["alert_message"] = parsed.get("alert_message", "")
    updates["trigger_emr"] = parsed.get("trigger_emr", False)
    updates["reasoning_text"] = parsed.get("reasoning", "No reasoning provided")
    updates["suggested_response_direction"] = parsed.get("response_text", "")

    # ---------------------------------------------------------------
    # AAC-based overrides — the score modulates our decisions
    # Even if the Reasoning Agent says "no alert", a very low AAC
    # with any non-normal situation should still ping the caregiver
    # ---------------------------------------------------------------
    if aac < 40 and updates["risk_level"] in ("low", "medium") and state.get("wearable_classification", "normal") != "normal":
        updates["alert_caregiver"] = True
        updates["alert_priority"] = "attention"
        updates["alert_message"] = updates["alert_message"] or f"{state.get('user_name', 'Patient')}'s AAC score is low ({aac}). Monitoring a {state.get('wearable_classification', 'situation')}."
        logger.info(f"AAC override: score={aac}, forcing caregiver alert")

    # If emotion is distressed/agitated and EMR candidates exist, force EMR
    if state.get("detected_emotion") in ("distressed", "agitated") and state.get("emr_candidates"):
        updates["trigger_emr"] = True
        logger.info("Emotion override: forcing EMR trigger")

    logger.info(
        f"Reasoning done | type={updates['request_type']} | risk={updates['risk_level']} | "
        f"alert={updates['alert_caregiver']} | emr={updates['trigger_emr']}"
    )

    return {**state, **updates}


def _parse_reasoning_output(raw: str) -> dict:
    """Parse the JSON from the reasoning model, with safe fallbacks"""
    cleaned = raw.strip()

    # Strip markdown code blocks if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Some models (deepseek) put thinking in <think> tags before the JSON
    if "<think>" in cleaned:
        think_end = cleaned.find("</think>")
        if think_end != -1:
            cleaned = cleaned[think_end + 8:].strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Reasoning returned non-JSON: {raw[:200]}")
        return {
            "request_type": "chat",
            "risk_level": "low",
            "alert_caregiver": False,
            "alert_priority": "routine",
            "alert_message": None,
            "trigger_emr": False,
            "response_text": "I'm here if you need me.",
            "reasoning": "Fallback — couldn't parse reasoning output",
        }