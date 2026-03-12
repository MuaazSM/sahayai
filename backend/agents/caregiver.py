import json
import uuid
import logging
from datetime import datetime

from agents.state import AssistState
from utils.llm import chat_completion

logger = logging.getLogger("sahayai.agent.caregiver")

# Load prompt once
try:
    with open("prompts/caregiver_agent.txt", "r") as f:
        CAREGIVER_PROMPT = f.read()
except FileNotFoundError:
    CAREGIVER_PROMPT = "You are a caregiver alert system. Be clear and actionable."


async def caregiver_agent(state: AssistState) -> AssistState:
    """
    Runs in parallel with Assistance Agent when the Reasoning Agent
    decides the caregiver needs to know something.

    Two modes:
    1. ALERT MODE — something happened (fall, wandering, distress).
       Generates a smart alert with WHY/WHERE/HISTORY/WHAT-TO-DO.
    2. SUMMARY MODE — caregiver asked "how was dad's day?"
       Generates a nurse-handoff-style spoken summary.

    Also runs CBD (Caregiver Burnout Detection) silently on every
    interaction to track if the caregiver is getting overwhelmed.
    """
    logger.info(f"Caregiver Agent running | alert={state.get('alert_caregiver', False)}")

    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["caregiver"],
    }

    # ---------------------------------------------------------------
    # ALERT MODE — generate a smart contextual alert
    # ---------------------------------------------------------------
    if state.get("alert_caregiver"):
        alert_payload = await _generate_smart_alert(state)
        updates["caregiver_alert_payload"] = alert_payload
        updates["llm_calls_made"] = state.get("llm_calls_made", 0) + 1
        logger.info(f"Alert generated: priority={alert_payload.get('priority', '?')}")

    # ---------------------------------------------------------------
    # SUMMARY MODE — caregiver is asking about the patient's day
    # This is triggered when role=caregiver and they ask something like
    # "how was dad's day?" or "give me an update"
    # ---------------------------------------------------------------
    if state.get("role") == "caregiver" and state.get("user_message"):
        summary = await _generate_caregiver_response(state)
        updates["caregiver_summary"] = summary
        updates["response_text"] = summary  # overwrite the assistance response
        updates["llm_calls_made"] = state.get("llm_calls_made", 0) + 1

    # ---------------------------------------------------------------
    # CBD — Caregiver Burnout Detection
    # Track patterns that indicate the caregiver is wearing down.
    # For now we compute a simple score — the full CBD with rolling
    # 7-day windows comes later.
    # ---------------------------------------------------------------
    cbd_result = _compute_cbd_score(state)
    updates["cbd_score"] = cbd_result["score"]
    updates["cbd_intervention"] = cbd_result["intervention"]

    if cbd_result["intervention"]:
        logger.info(f"CBD intervention triggered: {cbd_result['intervention']}")

    return {**state, **updates}


async def _generate_smart_alert(state: AssistState) -> dict:
    """
    Not just "fall detected" — we generate alerts that tell the caregiver
    WHY we think something happened, WHERE it is, WHAT the patient was
    doing, and WHAT the caregiver should do about it.

    This is the difference between a dumb smartwatch notification and
    SahayAI's intelligent alerts.
    """
    user_name = state.get("user_name", "the patient")
    priority = state.get("alert_priority", "attention")

    # Gather all the context we have about what happened
    situation_parts = []

    if state.get("wearable_classification"):
        situation_parts.append(f"Wearable: {state['wearable_classification']} (HR={state.get('heart_rate', '?')}bpm)")

    if state.get("detected_emotion") and state["detected_emotion"] != "calm":
        situation_parts.append(f"Emotion: {state['detected_emotion']}")

    if state.get("user_message"):
        situation_parts.append(f'They said: "{state["user_message"][:100]}"')

    if state.get("scene_description"):
        situation_parts.append(f"Camera: {state['scene_description'][:100]}")

    if state.get("gps_lat"):
        situation_parts.append(f"GPS: {state['gps_lat']}, {state['gps_lng']}")

    # Past similar events from RAG
    past_events = state.get("recent_events", [])
    if past_events:
        past_text = "; ".join([e.get("text", "")[:60] for e in past_events[:3]])
        situation_parts.append(f"History: {past_text}")

    situation_text = "\n".join(situation_parts) or "No additional context"

    prompt = f"""Generate a caregiver alert for {user_name}.

Priority: {priority}
AAC Score: {state.get('aac_score', 70)}/100
Reasoning: {state.get('reasoning_text', 'no reasoning available')}

Situation:
{situation_text}

Write TWO things:
1. ALERT (under 40 words): What happened, where, how urgent. Be specific.
2. ACTION (under 40 words): What the caregiver should do RIGHT NOW.

Format:
ALERT: <text>
ACTION: <text>

Be specific and human. Not "anomaly detected" but "Ramesh may have fallen near the kitchen — heart rate jumped to 110bpm."
"""

    raw = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model_preference="quality",  # 70b — alert quality matters a lot
        temperature=0.3,
        max_tokens=200,
    )

    # Parse ALERT: and ACTION: lines
    alert_text = state.get("alert_message", f"{state.get('wearable_classification', 'Event')} detected for {user_name}")
    action_text = "Please check on them when you can."

    try:
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("ALERT:"):
                alert_text = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ACTION:"):
                action_text = line.split(":", 1)[1].strip()
    except Exception:
        pass

    return {
        "alert_type": state.get("wearable_classification", state.get("request_type", "alert")),
        "priority": priority,
        "message": alert_text,
        "context": action_text,
        "patient_id": state.get("user_id", ""),
        "timestamp": datetime.utcnow().isoformat(),
        "event_id": str(uuid.uuid4()),
        "aac_score": state.get("aac_score", 70),
        "reasoning": state.get("reasoning_text", ""),
    }


async def _generate_caregiver_response(state: AssistState) -> str:
    """
    When the caregiver talks to SahayAI — "how was dad's day?",
    "any issues today?", "should I come home early?"

    Uses the quality model because caregivers read these carefully
    and trust what we say to make real decisions.
    """
    user_name = state.get("user_name", "your loved one")

    # Build context from what we know
    context_parts = [f"The caregiver is asking about {user_name}."]

    if state.get("relevant_routines"):
        routines = "\n".join([f"- {r.get('text', '')[:80]}" for r in state["relevant_routines"][:5]])
        context_parts.append(f"Today's routines:\n{routines}")

    if state.get("recent_events"):
        events = "\n".join([f"- {e.get('text', '')[:80]}" for e in state["recent_events"][:5]])
        context_parts.append(f"Recent events:\n{events}")

    context_parts.append(f"AAC Score: {state.get('aac_score', 70)}/100")
    context_parts.append(f"CBD (caregiver burnout): {state.get('cbd_score', 0):.0f}/100")

    prompt = f"""{"\n\n".join(context_parts)}

Caregiver's question: "{state.get('user_message', 'How are things?')}"

Respond like a thoughtful nurse doing a handoff. Warm but factual.
Under 100 words — this gets read aloud or skimmed on a phone.
If burnout score is high (>60), gently suggest they take care of themselves too."""

    messages = [
        {"role": "system", "content": CAREGIVER_PROMPT},
        {"role": "user", "content": prompt},
    ]

    return await chat_completion(
        messages=messages,
        model_preference="quality",
        temperature=0.5,
        max_tokens=250,
    )


def _compute_cbd_score(state: AssistState) -> dict:
    """
    CBD — Caregiver Burnout Detection (simplified for hackathon)

    Full version uses rolling 7-day windows of:
    - Alert response times
    - Message tone shifts
    - Login frequency
    - Late-night usage patterns

    For now we use a simpler heuristic based on what's available
    in the current state. The Learning Agent will build the full
    behavioral model over time.
    """
    score = state.get("cbd_score", 0.0)
    intervention = None

    # Late night usage bump — if it's between midnight and 5 AM,
    # that's a sign the caregiver isn't sleeping well
    hour = datetime.utcnow().hour
    if 0 <= hour < 5 and state.get("role") == "caregiver":
        score += 10
        logger.info("CBD: late night usage detected (+10)")

    # High alert volume bump — lots of alerts means stressful day
    # which means the caregiver is probably frazzled
    if state.get("alert_caregiver"):
        score += 5

    # Clamp to 0-100
    score = max(0.0, min(100.0, score))

    # Graduated interventions based on burnout level
    if score >= 80:
        intervention = "You've been incredibly dedicated. Please consider asking a family member or friend to help for a few hours. You need rest too."
    elif score >= 60:
        intervention = "You're doing an amazing job. Remember to take some time for yourself today — even a 15-minute walk can help."
    elif score >= 40:
        intervention = "Just a gentle reminder — taking care of yourself helps you take better care of them."

    return {"score": score, "intervention": intervention}