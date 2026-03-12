import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.models.schemas import StatusRequest, StatusResponse, CaregiverAlertPayload
from api.models.database import get_db
from api.models.tables import User, Event, Alert, CaregiverLink
from classifier.predict import classify_wearable
from utils.llm import chat_completion

router = APIRouter()
logger = logging.getLogger("sahayai.status")


@router.post("/check-status", response_model=StatusResponse)
async def check_status(request: StatusRequest, db: AsyncSession = Depends(get_db)):
    """
    Wearable data comes in from the Flutter app every ~30 seconds.
    We classify it (fall? wandering? distress? normal?), decide what
    to do about it, and optionally fire off a caregiver alert.
    """
    logger.info(f"Status check for user {request.user_id}")

    wd = request.wearable_data

    # ---------------------------------------------------------------
    # 1. Get user profile — we need their home GPS for wandering
    #    detection and their name for generating human-readable alerts
    # ---------------------------------------------------------------
    user = await db.get(User, request.user_id)
    home_lat = user.home_lat if user else 19.1136
    home_lng = user.home_lng if user else 72.8697
    user_name = user.name if user else "the patient"

    # ---------------------------------------------------------------
    # 2. Run the classifier — ML model if available, rules otherwise
    # ---------------------------------------------------------------
    result = classify_wearable(
        heart_rate=wd.heart_rate,
        accel_x=wd.accelerometer.x,
        accel_y=wd.accelerometer.y,
        accel_z=wd.accelerometer.z,
        steps=wd.steps,
        gps_lat=wd.gps.lat,
        gps_lng=wd.gps.lng,
        home_lat=home_lat,
        home_lng=home_lng,
        window_seconds=request.window_seconds,
    )

    classification = result["classification"]
    confidence = result["confidence"]

    logger.info(f"Classified: {classification} (confidence={confidence:.2f})")

    # ---------------------------------------------------------------
    # 3. Map classification → risk level
    #    This determines how aggressively we respond
    # ---------------------------------------------------------------
    risk_map = {
        "normal": "none",
        "fall": "critical",        # falls are always critical — could be life-threatening
        "wandering": "high",       # wandering is dangerous but not immediately lethal
        "distress": "high",        # distress could escalate fast
    }
    risk_level = risk_map.get(classification, "low")

    # If confidence is low, downgrade risk one level — we're not sure enough
    # to trigger emergency protocols on a maybe
    if confidence < 0.6 and risk_level in ("critical", "high"):
        risk_level = "medium"
        logger.info(f"Low confidence ({confidence:.2f}) — downgraded risk to medium")

    # ---------------------------------------------------------------
    # 4. Generate user-facing message if something's wrong
    #    For normal status, we stay quiet — no need to bother them
    # ---------------------------------------------------------------
    user_message = None
    if classification != "normal":
        user_message = await _generate_user_message(
            classification=classification,
            user_name=user_name,
            heart_rate=wd.heart_rate,
            gps_lat=wd.gps.lat,
            gps_lng=wd.gps.lng,
        )

    # ---------------------------------------------------------------
    # 5. Generate caregiver alert if risk is medium or above
    #    Normal and low risk → no alert, don't bother the caregiver
    #    with noise, that's how you get alert fatigue and burnout
    # ---------------------------------------------------------------
    caregiver_alert = None
    if risk_level in ("medium", "high", "critical"):
        caregiver_alert = await _generate_caregiver_alert(
            classification=classification,
            confidence=confidence,
            risk_level=risk_level,
            user_name=user_name,
            heart_rate=wd.heart_rate,
            gps_lat=wd.gps.lat,
            gps_lng=wd.gps.lng,
            home_lat=home_lat,
            home_lng=home_lng,
        )

        # Log the event in the DB
        event = Event(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            event_type=classification,
            severity=risk_level,
            description=caregiver_alert.message,
            lat=wd.gps.lat,
            lng=wd.gps.lng,
            agent_action=f"Alert generated: {caregiver_alert.priority}",
        )
        db.add(event)

        # Create alert record and link to the patient's caregiver
        cg_link_result = await db.execute(
            select(CaregiverLink)
            .where(CaregiverLink.patient_id == request.user_id)
            .where(CaregiverLink.is_primary == True)
            .limit(1)
        )
        cg_link = cg_link_result.scalar_one_or_none()

        if cg_link:
            alert_record = Alert(
                id=str(uuid.uuid4()),
                patient_id=request.user_id,
                caregiver_id=cg_link.caregiver_id,
                priority=caregiver_alert.priority,
                message=caregiver_alert.message,
                context=caregiver_alert.context,
                reasoning=f"Classifier: {classification} ({confidence:.0%}). Risk: {risk_level}.",
                event_id=event.id,
            )
            db.add(alert_record)
            logger.info(f"Alert saved for caregiver {cg_link.caregiver_id}: {caregiver_alert.priority}")

    return StatusResponse(
        classification=classification,
        confidence=confidence,
        risk_level=risk_level,
        user_message=user_message,
        caregiver_alert=caregiver_alert,
    )


# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def _generate_user_message(
    classification: str,
    user_name: str,
    heart_rate: int,
    gps_lat: float,
    gps_lng: float,
) -> str:
    """
    When something's detected, we need to talk to the user.
    Uses the fast model since this gets read aloud immediately.
    """
    prompt = f"""You are SahayAI, a caring AI companion. Something was detected from {user_name}'s smartwatch.

Detection: {classification}
Heart rate: {heart_rate} bpm
Location: {gps_lat}, {gps_lng}

Generate a calm, short message (under 30 words) for {user_name}:
- If FALL: ask if they're okay, tell them help is on the way
- If WANDERING: gently let them know they've gone far from home, offer to help navigate back
- If DISTRESS: soothe them, ask what's wrong, mention their caregiver has been notified

Just the message, nothing else. No JSON, no quotes."""

    return await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model_preference="fast",
        temperature=0.4,
        max_tokens=80,
    )


async def _generate_caregiver_alert(
    classification: str,
    confidence: float,
    risk_level: str,
    user_name: str,
    heart_rate: int,
    gps_lat: float,
    gps_lng: float,
    home_lat: float,
    home_lng: float,
) -> CaregiverAlertPayload:
    """
    Generate a smart alert for the caregiver. Not just "fall detected" but
    WHY we think so, WHERE it happened, and WHAT they should do.
    This is what makes our alerts better than dumb smartwatch notifications.
    """
    from classifier.predict import _haversine_meters
    dist = _haversine_meters(gps_lat, gps_lng, home_lat, home_lng)

    # Priority mapping — how loud should this alert be?
    priority_map = {
        "critical": "emergency",
        "high": "urgent",
        "medium": "attention",
        "low": "routine",
        "none": "routine",
    }
    priority = priority_map.get(risk_level, "attention")

    prompt = f"""You are SahayAI's caregiver alert system. Generate a clear, actionable alert.

Patient: {user_name}
Detection: {classification} (confidence: {confidence:.0%})
Heart rate: {heart_rate} bpm
Distance from home: {dist:.0f} meters
GPS: {gps_lat}, {gps_lng}
Risk level: {risk_level}

Generate TWO things:
1. ALERT MESSAGE (under 40 words) — what happened, where, how urgent
2. CONTEXT (under 60 words) — why we think this, what the caregiver should do

Format:
MESSAGE: <the alert>
CONTEXT: <the context>

Be specific and actionable. Not "anomaly detected" but "Ramesh appears to have fallen in the kitchen, heart rate elevated to 110bpm."
"""

    raw = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model_preference="quality",  # 70b — alert quality matters, caregiver trusts this
        temperature=0.3,
        max_tokens=200,
    )

    # Parse the MESSAGE: and CONTEXT: lines from the response
    message = f"{classification.upper()} detected for {user_name}. HR: {heart_rate}bpm. {dist:.0f}m from home."
    context = f"Confidence: {confidence:.0%}. Risk: {risk_level}. Check on {user_name} immediately."

    try:
        lines = raw.strip().split("\n")
        for line in lines:
            if line.strip().upper().startswith("MESSAGE:"):
                message = line.split(":", 1)[1].strip()
            elif line.strip().upper().startswith("CONTEXT:"):
                context = line.split(":", 1)[1].strip()
    except Exception:
        # If parsing fails, the defaults above are good enough
        pass

    return CaregiverAlertPayload(
        priority=priority,
        message=message,
        context=context,
    )