import json
import logging
import math
from datetime import datetime

from agents.state import AssistState
from classifier.predict import classify_wearable
from utils.llm import vision_completion, chat_completion

logger = logging.getLogger("sahayai.agent.perception")

# Load scene prompt once
try:
    with open("prompts/scene_analysis.txt", "r") as f:
        SCENE_PROMPT = f.read()
except FileNotFoundError:
    SCENE_PROMPT = "Describe this scene for a visually impaired person. Return JSON with scene_description, obstacles, guidance_text, risk_level."


async def perception_agent(state: AssistState) -> AssistState:
    """
    First agent in the pipeline. Takes whatever raw input came in
    (voice, camera, wearable, or any combo) and turns it into
    structured data the rest of the pipeline can work with.

    It's like a triage nurse — looks at what came in, figures out
    what's going on, writes it down in a standard format, passes
    the chart along.
    """
    logger.info(f"Perception Agent running | trigger={state.get('trigger_type', 'unknown')}")

    trigger = state.get("trigger_type", "voice")
    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["perception"],
        "llm_calls_made": state.get("llm_calls_made", 0),
    }

    # ---------------------------------------------------------------
    # VOICE INPUT — user said something
    # Not much to do here since STT already happened on the Flutter side.
    # We just detect emotion from the text so EMR knows if it should
    # kick in later. Also builds the perception summary.
    # ---------------------------------------------------------------
    if state.get("user_message"):
        emotion = await _detect_emotion(state["user_message"])
        updates["detected_emotion"] = emotion
        updates["llm_calls_made"] = updates["llm_calls_made"] + 1

        summary_parts = [f'User said: "{state["user_message"][:100]}"']
        if emotion != "calm":
            summary_parts.append(f"Detected emotion: {emotion}")
        updates["perception_summary"] = " | ".join(summary_parts)

    # ---------------------------------------------------------------
    # CAMERA INPUT — user pointed their phone at something
    # Send to vision model, parse the structured response
    # ---------------------------------------------------------------
    if state.get("image_base64"):
        scene_result = await _process_camera(
            state["image_base64"],
            state.get("gps_lat", 0),
            state.get("gps_lng", 0),
        )
        updates["scene_description"] = scene_result.get("scene_description", "")
        updates["obstacles"] = scene_result.get("obstacles", [])
        updates["guidance_text"] = scene_result.get("guidance_text", "")
        updates["llm_calls_made"] = updates["llm_calls_made"] + 1

        # Camera results feed into the perception summary
        obs_count = len(updates["obstacles"])
        prev_summary = updates.get("perception_summary", "")
        cam_summary = f"Camera: {updates['scene_description'][:80]}. {obs_count} obstacles detected."
        updates["perception_summary"] = f"{prev_summary} | {cam_summary}" if prev_summary else cam_summary

    # ---------------------------------------------------------------
    # WEARABLE INPUT — smartwatch data came in
    # Run through the classifier (ML model or rule-based fallback)
    # No LLM call needed — this is pure local ML, <5ms
    # ---------------------------------------------------------------
    if state.get("heart_rate") is not None:
        classification_result = classify_wearable(
            heart_rate=state["heart_rate"],
            accel_x=state.get("accel_x", 0),
            accel_y=state.get("accel_y", 0),
            accel_z=state.get("accel_z", 0),
            steps=state.get("steps", 0),
            gps_lat=state.get("gps_lat", 0),
            gps_lng=state.get("gps_lng", 0),
            home_lat=state.get("home_lat", 19.1136),
            home_lng=state.get("home_lng", 72.8697),
            window_seconds=state.get("window_seconds", 30),
        )
        updates["wearable_classification"] = classification_result["classification"]
        updates["wearable_confidence"] = classification_result["confidence"]

        prev_summary = updates.get("perception_summary", "")
        wear_summary = f"Wearable: {classification_result['classification']} (conf={classification_result['confidence']:.0%}), HR={state['heart_rate']}bpm"
        updates["perception_summary"] = f"{prev_summary} | {wear_summary}" if prev_summary else wear_summary

    # ---------------------------------------------------------------
    # REMINDER TRIGGER — no real perception needed, just pass through
    # ---------------------------------------------------------------
    if trigger == "reminder":
        updates["perception_summary"] = updates.get("perception_summary", "Scheduled reminder triggered")
        updates["detected_emotion"] = "calm"

    # If we still don't have a summary, something weird happened
    if not updates.get("perception_summary"):
        updates["perception_summary"] = "No input data received"

    logger.info(f"Perception done: {updates.get('perception_summary', '')[:120]}")
    return {**state, **updates}


# =====================================================
# HELPERS
# =====================================================

async def _detect_emotion(text: str) -> str:
    """
    Quick emotion classification from text. Uses the fast model
    because this runs on every single message and we need it quick.
    Returns one of: calm, confused, distressed, agitated, happy
    """
    prompt = f"""Classify the emotion in this message from a person who may have dementia or disabilities.
Return ONLY one word: calm, confused, distressed, agitated, or happy.

Message: "{text}"

Emotion:"""

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_preference="fast",
            temperature=0.1,
            max_tokens=10,
        )
        # Clean up — model might return "Emotion: confused" or just "confused"
        emotion = raw.strip().lower().rstrip(".").split(":")[-1].strip()
        valid = {"calm", "confused", "distressed", "agitated", "happy"}
        return emotion if emotion in valid else "calm"
    except Exception as e:
        logger.warning(f"Emotion detection failed: {e}")
        return "calm"


async def _process_camera(base64_image: str, lat: float, lng: float) -> dict:
    """
    Send camera frame to vision model, get structured scene analysis back.
    Same logic as the /analyze-scene endpoint but returns a dict instead
    of a Pydantic model so it fits into the pipeline state.
    """
    prompt = f"""{SCENE_PROMPT}

User's current GPS: lat={lat}, lng={lng}
Analyze the image now."""

    try:
        raw = await vision_completion(
            base64_image=base64_image,
            prompt=prompt,
            temperature=0.2,
            max_tokens=512,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Camera processing failed: {e}")
        return {
            "scene_description": "I had trouble seeing clearly. Try pointing the camera again.",
            "obstacles": [],
            "guidance_text": "Please try again.",
            "risk_level": "low",
        }