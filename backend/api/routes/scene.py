import json
import base64
import logging
from fastapi import APIRouter, UploadFile, File, Form
from api.models.schemas import SceneResponse
from utils.llm import vision_completion

router = APIRouter()
logger = logging.getLogger("sahayai.scene")

try:
    with open("prompts/scene_analysis.txt", "r") as f:
        SCENE_PROMPT = f.read()
except FileNotFoundError:
    SCENE_PROMPT = (
        "Describe this scene for a visually impaired person. "
        "Return JSON with keys: description (string), objects_detected (list of strings), "
        "safety_concerns (list of strings), confidence (float 0-1)."
    )
    logger.warning("scene_analysis.txt not found — using fallback prompt")


@router.post("/analyze-scene", response_model=SceneResponse)
async def analyze_scene(user_id: str = Form(...), image: UploadFile = File(...)):
    """Android sends multipart/form-data: user_id as form field, image as binary file."""
    try:
        image_bytes = await image.read()
        if len(image_bytes) < 10:
            return SceneResponse(
                description="I didn't receive a clear image. Please try pointing your camera again.",
                objects_detected=[],
                safety_concerns=["No image received"],
                confidence=0.0,
            )

        logger.info(f"Scene analysis for user {user_id} (image size: {len(image_bytes)} bytes)")

        b64 = base64.b64encode(image_bytes).decode()

        raw_response = await vision_completion(
            base64_image=b64,
            prompt=SCENE_PROMPT,
            temperature=0.2,
            max_tokens=512,
        )

        # Strip markdown code fences if model added them
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
            # Support both Android format and legacy format from old prompts
            description = parsed.get("description") or parsed.get("scene_description", "I see a scene but couldn't fully analyze it.")
            objects_detected = parsed.get("objects_detected") or [
                f"{obs.get('type', 'object')} ({obs.get('distance', 'nearby')})"
                for obs in parsed.get("obstacles", [])
            ]
            safety_concerns = parsed.get("safety_concerns") or (
                [parsed["guidance_text"]] if parsed.get("guidance_text") else []
            )
            confidence = float(parsed.get("confidence", 0.9))
            return SceneResponse(
                description=description,
                objects_detected=objects_detected,
                safety_concerns=safety_concerns,
                confidence=confidence,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Vision response parse failed: {e}. Raw: {raw_response[:200]}")
            return SceneResponse(
                description=raw_response[:200] if raw_response else "I had trouble analyzing the scene.",
                objects_detected=[],
                safety_concerns=["Could not fully analyze the scene"],
                confidence=0.3,
            )

    except Exception as e:
        logger.error(f"Scene analysis failed completely: {e}", exc_info=True)
        return SceneResponse(
            description="I'm having trouble with my vision right now.",
            objects_detected=[],
            safety_concerns=["Scene analysis unavailable — please be careful"],
            confidence=0.0,
        )
