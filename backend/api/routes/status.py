import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.models.schemas import StatusRequest, StatusResponse, CaregiverAlertPayload
from api.models.database import get_db
from api.models.tables import Event, Alert, CaregiverLink
from agents.pipeline import run_pipeline
from api.routes.websocket import broadcast_alert

router = APIRouter()
logger = logging.getLogger("sahayai.status")


@router.post("/check-status", response_model=StatusResponse)
async def check_status(request: StatusRequest, db: AsyncSession = Depends(get_db)):
    try:
        logger.info(f"Status check for user {request.user_id}")
        wd = request.wearable_data

        # Run the full pipeline with wearable trigger
        pipeline_state = await run_pipeline(
            initial_state={
                "user_id": request.user_id,
                "role": "patient",
                "trigger_type": "wearable",
                "heart_rate": wd.heart_rate,
                "accel_x": wd.accelerometer.x,
                "accel_y": wd.accelerometer.y,
                "accel_z": wd.accelerometer.z,
                "steps": wd.steps,
                "gps_lat": wd.gps.lat,
                "gps_lng": wd.gps.lng,
                "window_seconds": request.window_seconds,
            },
            db=db,
        )

        classification = pipeline_state.get("wearable_classification", "normal")
        confidence = pipeline_state.get("wearable_confidence", 0.9)
        risk_level = pipeline_state.get("risk_level", "none")

        user_message = pipeline_state.get("response_text") or None
        if risk_level == "none":
            user_message = None

        # Build caregiver alert
        caregiver_alert = None
        if pipeline_state.get("alert_caregiver") and pipeline_state.get("caregiver_alert_payload"):
            try:
                payload = pipeline_state["caregiver_alert_payload"]
                caregiver_alert = CaregiverAlertPayload(
                    priority=payload.get("priority", "attention"),
                    message=payload.get("message", f"{classification} detected"),
                    context=payload.get("context", "Check on them."),
                )

                # Save to DB
                event = Event(
                    id=str(uuid.uuid4()),
                    user_id=request.user_id,
                    event_type=classification,
                    severity=risk_level,
                    description=caregiver_alert.message,
                    lat=wd.gps.lat,
                    lng=wd.gps.lng,
                    agent_action=f"Pipeline: {' → '.join(pipeline_state.get('agents_executed', []))}",
                )
                db.add(event)

                cg_result = await db.execute(
                    select(CaregiverLink)
                    .where(CaregiverLink.patient_id == request.user_id)
                    .where(CaregiverLink.is_primary == True)
                    .limit(1)
                )
                cg_link = cg_result.scalar_one_or_none()

                if cg_link:
                    alert_record = Alert(
                        id=str(uuid.uuid4()),
                        patient_id=request.user_id,
                        caregiver_id=cg_link.caregiver_id,
                        priority=caregiver_alert.priority,
                        message=caregiver_alert.message,
                        context=caregiver_alert.context,
                        reasoning=pipeline_state.get("reasoning_text", ""),
                        event_id=event.id,
                    )
                    db.add(alert_record)

                    try:
                        await broadcast_alert(cg_link.caregiver_id, payload)
                    except Exception as e:
                        logger.warning(f"WS broadcast failed: {e}")

            except Exception as e:
                logger.error(f"Failed to save alert: {e}")

        return StatusResponse(
            classification=classification,
            confidence=confidence,
            risk_level=risk_level,
            user_message=user_message,
            caregiver_alert=caregiver_alert,
        )

    except Exception as e:
        # Wearable check failing is serious but we shouldn't crash.
        # Return normal with low confidence so the next check retries.
        logger.error(f"Status check failed: {e}", exc_info=True)
        return StatusResponse(
            classification="normal",
            confidence=0.3,
            risk_level="low",
            user_message=None,
            caregiver_alert=None,
        )