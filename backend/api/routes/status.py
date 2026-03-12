"""
POST /check-status — Receives wearable sensor data (heart rate, accelerometer,
steps, GPS), runs it through the trained Random Forest classifier, and returns
risk classification. If risk is medium+, also generates a caregiver alert.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/check-status")
async def check_status(request: dict):
    # TODO: Muaaz — wire up classifier + Reasoning Agent
    return {
        "classification": "normal",
        "confidence": 0.95,
        "risk_level": "none",
        "user_message": None,
        "caregiver_alert": None,
    }