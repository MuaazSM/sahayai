import json
import uuid
import logging
from datetime import datetime

from agents.state import AssistState
from utils.llm import chat_completion

logger = logging.getLogger("sahayai.agent.assistance")

# Load prompt once
try:
    with open("prompts/assistance_agent.txt", "r") as f:
        ASSISTANCE_PROMPT = f.read()
except FileNotFoundError:
    ASSISTANCE_PROMPT = "You are SahayAI, a kind AI companion. Keep responses short and warm."


async def assistance_agent(state: AssistState) -> AssistState:
    """
    User-facing agent. Takes everything the Reasoning Agent decided
    and turns it into actual words the person hears through TTS.

    Uses the fast model (8b) because latency = everything here.
    The user is standing on a street corner or sitting confused in
    their living room — every second of silence feels like an eternity.

    Also runs CCT scoring silently on every patient message.
    """
    logger.info(f"Assistance Agent running | user={state.get('user_name', 'unknown')}")

    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["assistance"],
    }

    user_name = state.get("user_name", "there")
    aac = state.get("aac_score", 70)
    trigger = state.get("trigger_type", "voice")

    # ---------------------------------------------------------------
    # 1. If EMR was triggered, pick the best memory to surface
    # ---------------------------------------------------------------
    emr_memory_text = ""
    emr_memory_used = None

    if state.get("trigger_emr") and state.get("emr_candidates"):
        # Pick the top candidate (closest semantic match to current emotion)
        best_memory = state["emr_candidates"][0]
        emr_memory_text = best_memory.get("text", "")
        emr_memory_used = best_memory
        updates["emr_memory_used"] = best_memory
        logger.info(f"EMR triggered — using memory: {emr_memory_text[:60]}...")

    # ---------------------------------------------------------------
    # 2. Build the prompt for the Assistance Agent
    #    Give it the reasoning output + EMR memory + conversation context
    # ---------------------------------------------------------------
    context_parts = [
        f"You are talking to {user_name}.",
        f"AAC score: {aac}/100.",
        f"Situation: {state.get('request_type', 'chat')}, risk: {state.get('risk_level', 'none')}.",
    ]

    # Communication preferences from RAG
    comm_prefs = state.get("communication_prefs", {})
    if comm_prefs:
        tone = comm_prefs.get("preferred_tone", "warm")
        length = comm_prefs.get("sentence_length", "short")
        context_parts.append(f"Communication style: {tone} tone, {length} sentences.")

    # EMR memory to weave in
    if emr_memory_text:
        context_parts.append(
            f'EMR MEMORY TRIGGERED — weave this in naturally: "{emr_memory_text}"'
        )

    # Camera guidance if present
    if state.get("scene_description"):
        context_parts.append(f"Camera sees: {state['scene_description']}")
        if state.get("guidance_text"):
            context_parts.append(f"Safety guidance: {state['guidance_text']}")

    # Wearable status if abnormal
    if state.get("wearable_classification") and state["wearable_classification"] != "normal":
        context_parts.append(
            f"Wearable detected: {state['wearable_classification']} "
            f"(HR={state.get('heart_rate', '?')}bpm)"
        )

    # What the reasoning agent suggested
    if state.get("suggested_response_direction"):
        context_parts.append(f"Suggested direction: {state['suggested_response_direction']}")

    # The user's actual message
    if state.get("user_message"):
        context_parts.append(f'\nUser just said: "{state["user_message"]}"')
    elif trigger == "wearable":
        context_parts.append("\nThis was triggered by wearable data, not a voice message. Speak first.")
    elif trigger == "camera":
        context_parts.append("\nUser pointed their camera. Describe what you see.")

    context_parts.append("\nRespond now. Warm, short, spoken aloud via TTS.")

    messages = [
        {"role": "system", "content": ASSISTANCE_PROMPT},
        {"role": "user", "content": "\n".join(context_parts)},
    ]

    # ---------------------------------------------------------------
    # 3. Generate the response — fast model for low latency
    # ---------------------------------------------------------------
    response_text = await chat_completion(
        messages=messages,
        model_preference="fast",  # 8b — speed over quality for voice
        temperature=0.5,
        max_tokens=150,           # hard cap so TTS doesn't drone on
    )
    updates["response_text"] = response_text
    updates["llm_calls_made"] = state.get("llm_calls_made", 0) + 1

    # ---------------------------------------------------------------
    # 4. CCT Scoring — silent cognitive tracking on patient messages
    #    Runs in parallel conceptually (doesn't block the response)
    #    but we await it here since we need the score for the API response
    # ---------------------------------------------------------------
    if state.get("role") == "patient" and state.get("user_message"):
        cct_result = await _run_cct_scoring(
            user_message=state["user_message"],
            user_name=user_name,
            perception_summary=state.get("perception_summary", ""),
        )
        updates["cct_scores"] = cct_result
        updates["cct_composite"] = cct_result.get("composite", 0.0)
        updates["llm_calls_made"] = updates["llm_calls_made"] + 1
        logger.info(f"CCT composite: {updates['cct_composite']:.2f}")

    logger.info(f"Assistance done | response: {response_text[:80]}...")
    return {**state, **updates}


async def _run_cct_scoring(user_message: str, user_name: str, perception_summary: str) -> dict:
    """
    CCT — Conversational Cognitive Tracking
    Scores 6 dimensions from the user's speech. The user never knows
    this is happening — it's completely silent background analysis.
    
    We use the structured model (qwen 32b) because it needs to output
    reliable JSON with consistent float scores.
    """
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

Composite = average of all 6. Be realistic — healthy elderly people score 0.65-0.85, not perfect 1.0s."""

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_preference="structured",  # qwen 32b — good at JSON
            temperature=0.1,
            max_tokens=256,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        # Handle deepseek <think> blocks
        if "<think>" in cleaned:
            think_end = cleaned.find("</think>")
            if think_end != -1:
                cleaned = cleaned[think_end + 8:]

        cleaned = cleaned.strip()
        scores = json.loads(cleaned)

        # Sanity check — clamp everything to 0-1
        for key in ["recall_accuracy", "response_latency", "vocabulary_richness",
                     "temporal_orientation", "narrative_coherence", "semantic_consistency", "composite"]:
            if key in scores:
                scores[key] = max(0.0, min(1.0, float(scores[key])))

        return scores

    except Exception as e:
        logger.warning(f"CCT scoring failed: {e}")
        return {
            "recall_accuracy": 0.0,
            "response_latency": 0.0,
            "vocabulary_richness": 0.0,
            "temporal_orientation": 0.0,
            "narrative_coherence": 0.0,
            "semantic_consistency": 0.0,
            "composite": 0.0,
        }