import json
import logging
from fastapi import APIRouter
from api.models.schemas import SceneRequest, SceneResponse, Obstacle
from utils.llm import vision_completion

router = APIRouter()
logger = logging.getLogger("sahayai.scene")

# Load the scene analysis prompt once at import time
# It tells the vision model exactly how to analyze camera frames
# and what JSON format to respond in
with open("prompts/scene_analysis.txt", "r") as f:
    SCENE_PROMPT = f.read()


@router.post("/analyze-scene", response_model=SceneResponse)
async def analyze_scene(request: SceneRequest):
    """
    Takes a camera frame from the Flutter app, sends it to the cheapest
    available vision model (Groq llama-4-scout → Gemini Flash → GPT-4o-mini),
    and returns a structured scene description the user can hear via TTS.
    """
    logger.info(f"Scene analysis requested by user {request.user_id}")

    # Build the prompt — we include GPS coords so the model has location context
    # (e.g., if they're near a known busy intersection)
    prompt = f"""{SCENE_PROMPT}

User's current GPS: lat={request.location.lat}, lng={request.location.lng}
Analyze the image now."""

    # Call the vision model — llm.py handles the Groq → Gemini → OpenAI fallback
    raw_response = await vision_completion(
        base64_image=request.image,
        prompt=prompt,
        temperature=0.2,  # low temp = more reliable structured output
        max_tokens=512,
    )

    # Parse the JSON response from the vision model
    # Sometimes models wrap it in markdown code blocks, so we strip those
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        result = SceneResponse(
            scene_description=parsed.get("scene_description", "I couldn't clearly see the scene."),
            obstacles=[Obstacle(**obs) for obs in parsed.get("obstacles", [])],
            guidance_text=parsed.get("guidance_text", "Please try pointing the camera again."),
            risk_level=parsed.get("risk_level", "low"),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # If the model returned garbage or non-JSON, give a safe fallback
        # rather than crashing — the user is relying on us for guidance
        logger.warning(f"Failed to parse vision response: {e}. Raw: {raw_response[:200]}")
        result = SceneResponse(
            scene_description=raw_response[:200] if raw_response else "I had trouble analyzing the scene.",
            obstacles=[],
            guidance_text="I couldn't fully analyze the scene. Please try pointing your camera again.",
            risk_level="low",
        )

    logger.info(f"Scene result: risk={result.risk_level}, obstacles={len(result.obstacles)}")
    return result