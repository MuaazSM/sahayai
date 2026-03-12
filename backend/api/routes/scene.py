"""
POST /analyze-scene — Takes a camera frame (base64) + GPS location,
runs it through vision LLM (Groq Llama-4-Scout or Gemini Flash),
and returns scene description + obstacle warnings for the user.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/analyze-scene")
async def analyze_scene(request: dict):
    # TODO: Muaaz — wire up Perception Agent with vision model
    return {
        "scene_description": "You are on a sidewalk. There is a busy road ahead.",
        "obstacles": [
            {"type": "road", "distance": "5 meters", "direction": "ahead"}
        ],
        "guidance_text": "Stop. Busy road 5 meters ahead. Wait for traffic to clear.",
        "risk_level": "medium",
    }