import json
import logging
from fastapi import APIRouter, HTTPException
from api.models.schemas import SceneRequest, SceneResponse, Obstacle
from utils.llm import vision_completion

router = APIRouter()
logger = logging.getLogger("sahayai.scene")

try:
    with open("prompts/scene_analysis.txt", "r") as f:
        SCENE_PROMPT = f.read()
except FileNotFoundError:
    SCENE_PROMPT = "Describe this scene for a visually impaired person. Return JSON with scene_description, obstacles, guidance_text, risk_level."
    logger.warning("scene_analysis.txt not found — using fallback prompt")


@router.post("/analyze-scene", response_model=SceneResponse)
async def analyze_scene(request: SceneRequest):
    try:
        # Validate the image isn't empty — Flutter sometimes sends empty
        # strings if camera permission was denied or capture failed
        if not request.image or len(request.image) < 100:
            return SceneResponse(
                scene_description="I didn't receive a clear image. Please try pointing your camera again.",
                obstacles=[],
                guidance_text="Try taking another photo.",
                risk_level="low",
            )

        logger.info(f"Scene analysis for user {request.user_id} (image size: {len(request.image)} chars)")

        prompt = f"""{SCENE_PROMPT}

User's current GPS: lat={request.location.lat}, lng={request.location.lng}
Analyze the image now."""

        raw_response = await vision_completion(
            base64_image=request.image,
            prompt=prompt,
            temperature=0.2,
            max_tokens=512,
        )

        # Parse JSON — strip markdown code fences if model added them
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
            return SceneResponse(
                scene_description=parsed.get("scene_description", "I see a scene but couldn't fully analyze it."),
                obstacles=[Obstacle(**obs) for obs in parsed.get("obstacles", [])],
                guidance_text=parsed.get("guidance_text", "Please try pointing the camera again."),
                risk_level=parsed.get("risk_level", "low"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Vision response parse failed: {e}. Raw: {raw_response[:200]}")
            # Return the raw text as description — better than nothing
            return SceneResponse(
                scene_description=raw_response[:200] if raw_response else "I had trouble analyzing the scene.",
                obstacles=[],
                guidance_text="I couldn't fully analyze the scene. Please try again.",
                risk_level="low",
            )

    except Exception as e:
        # Total failure — LLM down, network error, whatever.
        # Still return a valid response so the user isn't left hanging.
        logger.error(f"Scene analysis failed completely: {e}", exc_info=True)
        return SceneResponse(
            scene_description="I'm having trouble with my vision right now.",
            obstacles=[],
            guidance_text="My scene analysis isn't working at the moment. Please be careful and ask someone nearby for help.",
            risk_level="medium",
        )