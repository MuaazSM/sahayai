import json
import uuid
import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from api.models.schemas import (
    AlertItem, AlertsResponse,
    AcknowledgeRequest, AcknowledgeResponse,
    SummaryResponse, SummaryMetrics, SummaryEvent, CCTScorePoint,
    CaregiverSummaryResponse, CognitiveTrendPoint,
)
from api.models.database import get_db
from api.models.tables import (
    User, Alert, Event, CaregiverLink, DailySummary,
    CCTScore, AACScore, Reminder,
)
from utils.llm import chat_completion

router = APIRouter()
logger = logging.getLogger("sahayai.caregiver")

# Load the caregiver agent prompt once
with open("prompts/caregiver_agent.txt", "r") as f:
    CAREGIVER_PROMPT = f.read()


# =====================================================
# GET /caregiver/alerts/{patient_id}
# =====================================================

@router.get("/caregiver/alerts/{patient_id}", response_model=list[AlertItem])
async def get_alerts(
    patient_id: str,
    since: str = Query(default=None, description="ISO timestamp — only return alerts after this time"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the alert feed for a patient as a flat list.
    Android expects Response<List<Alert>> — no wrapper object.
    """
    logger.info(f"Fetching alerts for patient {patient_id} (limit={limit})")

    query = (
        select(Alert)
        .where(Alert.patient_id == patient_id)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
    )

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            query = query.where(Alert.timestamp > since_dt)
        except ValueError:
            logger.warning(f"Invalid since timestamp: {since}, ignoring filter")

    result = await db.execute(query)
    alerts = result.scalars().all()

    alert_items = [
        AlertItem(
            id=a.id,
            patient_id=a.patient_id,
            alert_type=_derive_alert_type(a),
            priority=a.priority,
            title=_extract_title(a.message),
            description=a.message or "",
            created_at=a.timestamp.isoformat(),
            is_acknowledged=a.acknowledged,
            acknowledged_by=a.caregiver_id if a.acknowledged else None,
            acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        )
        for a in alerts
    ]

    logger.info(f"Returning {len(alert_items)} alerts")
    return alert_items


# =====================================================
# POST /caregiver/alerts/{alert_id}/acknowledge
# =====================================================

@router.post("/caregiver/alerts/{alert_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Caregiver taps an alert to acknowledge/dismiss/escalate it.
    We track this because:
    - CBD uses response times to detect burnout
    - Escalated alerts get forwarded to secondary caregivers
    - Acknowledged alerts stop the repeated notification loop
    """
    action = request.action
    acknowledged_by = request.acknowledged_by or "caregiver"
    logger.info(f"Acknowledging alert {alert_id}: action={action}, by={acknowledged_by}")

    alert = await db.get(Alert, alert_id)
    if not alert:
        return AcknowledgeResponse(success=False, updated_alert={"error": "Alert not found"})

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledge_action = action
    alert.acknowledge_note = request.note
    if not alert.caregiver_id and acknowledged_by:
        alert.caregiver_id = acknowledged_by

    # If escalated, we'd normally notify secondary caregivers here
    # For the hackathon demo, just log it
    if action == "escalate":
        logger.warning(f"Alert {alert_id} ESCALATED by {acknowledged_by}. Would notify secondary caregivers.")

    return AcknowledgeResponse(
        success=True,
        updated_alert={
            "id": alert.id,
            "acknowledged": True,
            "acknowledged_at": alert.acknowledged_at.isoformat(),
            "action": action,
            "acknowledged_by": acknowledged_by,
            "note": request.note,
        },
    )


# =====================================================
# GET /caregiver/summary/{patient_id}
# =====================================================

@router.get("/caregiver/summary/{patient_id}", response_model=CaregiverSummaryResponse)
async def get_summary(
    patient_id: str,
    date_str: str = Query(default=None, alias="date", description="YYYY-MM-DD, defaults to today"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns daily summary. Response shape matches Android CaregiverSummary data class —
    flat fields, no nested metrics object.
    """
    try:
        if date_str:
            try:
                summary_date = date.fromisoformat(date_str)
            except ValueError:
                summary_date = date.today()
        else:
            summary_date = date.today()

        day_start = datetime.combine(summary_date, datetime.min.time())
        day_end = datetime.combine(summary_date, datetime.max.time())

        logger.info(f"Generating summary for patient {patient_id} on {summary_date}")

        # --- Check cache first so we don't regenerate on every refresh ---
        try:
            cached_result = await db.execute(
                select(DailySummary)
                .where(and_(
                    DailySummary.patient_id == patient_id,
                    DailySummary.summary_date == summary_date,
                ))
                .order_by(DailySummary.generated_at.desc())
                .limit(1)
            )
            cached = cached_result.scalar_one_or_none()
            if cached:
                logger.info("Returning cached summary")
                avg_cct = await _compute_avg_cct(patient_id, day_start, day_end, db)
                return CaregiverSummaryResponse(
                    patient_id=patient_id,
                    date=cached.summary_date.isoformat(),
                    steps_today=cached.total_steps,
                    reminders_completed=int(cached.medication_adherence * 10),  # approximation until real column added
                    reminders_total=10,
                    avg_cct_score=avg_cct,
                    risk_level=_aac_to_risk(cached.avg_aac_score),
                    aac_score=float(cached.avg_aac_score),
                    conversations_today=0,
                    mood_summary=cached.summary_text,
                    medication_adherence=cached.medication_adherence,
                    alerts_count=cached.alerts_count,
                    cct_trend=cached.cct_trend,
                )
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")

        # --- No cache, generate fresh ---
        user = await db.get(User, patient_id)
        user_name = user.name if user else "the patient"
        conditions = user.medical_conditions if user else "unknown"

        events_result = await db.execute(
            select(Event)
            .where(and_(
                Event.user_id == patient_id,
                Event.timestamp >= day_start,
                Event.timestamp <= day_end,
            ))
            .order_by(Event.timestamp.asc())
        )
        events = events_result.scalars().all()

        cct_result = await db.execute(
            select(CCTScore)
            .where(and_(
                CCTScore.user_id == patient_id,
                CCTScore.scored_at >= day_start,
                CCTScore.scored_at <= day_end,
            ))
            .order_by(CCTScore.scored_at.asc())
        )
        cct_scores = cct_result.scalars().all()

        aac_result = await db.execute(
            select(AACScore)
            .where(and_(
                AACScore.user_id == patient_id,
                AACScore.calculated_at >= day_start,
                AACScore.calculated_at <= day_end,
            ))
            .order_by(AACScore.calculated_at.asc())
        )
        aac_scores = aac_result.scalars().all()

        alerts_result = await db.execute(
            select(Alert)
            .where(and_(
                Alert.patient_id == patient_id,
                Alert.timestamp >= day_start,
                Alert.timestamp <= day_end,
            ))
            .order_by(Alert.timestamp.asc())
        )
        alerts = alerts_result.scalars().all()

        # Medication adherence + reminder counts
        med_total_result = await db.execute(
            select(func.count(Reminder.id))
            .where(and_(
                Reminder.user_id == patient_id,
                Reminder.reminder_type == "medication",
                Reminder.scheduled_time >= day_start,
                Reminder.scheduled_time <= day_end,
            ))
        )
        med_total = med_total_result.scalar() or 0

        med_confirmed_result = await db.execute(
            select(func.count(Reminder.id))
            .where(and_(
                Reminder.user_id == patient_id,
                Reminder.reminder_type == "medication",
                Reminder.scheduled_time >= day_start,
                Reminder.scheduled_time <= day_end,
                Reminder.status == "confirmed",
            ))
        )
        med_confirmed = med_confirmed_result.scalar() or 0
        medication_adherence = (med_confirmed / med_total) if med_total > 0 else 1.0

        total_steps = sum(_extract_steps_from_event(e) for e in events)

        avg_aac = int(
            sum(a.score for a in aac_scores) / len(aac_scores)
        ) if aac_scores else (user.aac_baseline if user else 70)

        avg_cct = (
            sum(s.composite_score for s in cct_scores) / len(cct_scores)
        ) if cct_scores else 0.0

        # Count conversations today (events with type "conversation")
        conversations_today = sum(1 for e in events if e.event_type == "conversation")

        cct_trend = await _compute_cct_trend(patient_id, summary_date, cct_scores, db)

        # Generate mood summary via LLM
        events_for_llm = _format_events_for_llm(events)
        summary_context = f"""
Patient: {user_name}
Conditions: {conditions}
Date: {summary_date}
AAC Score (avg today): {avg_aac}/100
CCT Trend: {cct_trend}
Medication Adherence: {medication_adherence:.0%} ({med_confirmed}/{med_total} taken)
Alerts today: {len(alerts)}

Today's events (chronological):
{events_for_llm if events_for_llm else "No events recorded today — quiet day."}

CCT Scores today:
{_format_cct_for_llm(cct_scores) if cct_scores else "No cognitive scores recorded today."}

Alerts today:
{_format_alerts_for_llm(alerts) if alerts else "No alerts today."}

Generate the daily summary now."""

        summary_messages = [
            {"role": "system", "content": CAREGIVER_PROMPT},
            {"role": "user", "content": summary_context},
        ]

        mood_summary = await chat_completion(
            messages=summary_messages,
            model_preference="quality",
            temperature=0.5,
            max_tokens=400,
        )

        # Cache it
        try:
            cached_entry = DailySummary(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                summary_date=summary_date,
                summary_text=mood_summary,
                medication_adherence=medication_adherence,
                total_steps=total_steps,
                alerts_count=len(alerts),
                avg_aac_score=avg_aac,
                cct_trend=cct_trend,
                events_json=json.dumps([
                    {"time": e.timestamp.strftime("%H:%M"), "type": e.event_type,
                     "description": e.description, "severity": e.severity}
                    for e in events
                ]),
            )
            db.add(cached_entry)
        except Exception as e:
            logger.warning(f"Failed to cache summary: {e}")

        return CaregiverSummaryResponse(
            patient_id=patient_id,
            date=summary_date.isoformat(),
            steps_today=total_steps,
            reminders_completed=med_confirmed,
            reminders_total=med_total,
            avg_cct_score=round(avg_cct, 3),
            risk_level=_aac_to_risk(avg_aac),
            aac_score=float(avg_aac),
            conversations_today=conversations_today,
            mood_summary=mood_summary,
            medication_adherence=medication_adherence,
            alerts_count=len(alerts),
            cct_trend=cct_trend,
        )

    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        return CaregiverSummaryResponse(
            patient_id=patient_id,
            date=date.today().isoformat(),
            mood_summary="I had trouble generating today's summary. Please try again in a moment.",
            risk_level="LOW",
            aac_score=70.0,
            cct_trend="stable",
        )


# =====================================================
# GET /caregiver/trends/{patient_id}
# =====================================================

@router.get("/caregiver/trends/{patient_id}", response_model=list[CognitiveTrendPoint])
async def get_cognitive_trends(
    patient_id: str,
    days: int = Query(default=14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns 14-day CCT + AAC trend data for the caregiver cognitive chart.
    Android CognitiveTrendScreen calls GET /caregiver/trends/{patient_id}.
    """
    from innovations.cct import get_cct_trend
    trend = await get_cct_trend(patient_id, days=days, db=db)
    return [
        CognitiveTrendPoint(
            date=point["date"],
            cct_score=point["cct_score"],
            aac_score=point.get("aac_score"),
            conversation_count=point.get("conversation_count", 0),
        )
        for point in trend
    ]


# =====================================================
# GET /caregiver/burnout/{caregiver_id}
# =====================================================

@router.get("/caregiver/burnout/{caregiver_id}")
async def get_burnout_score(caregiver_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns the full CBD burnout analysis for a caregiver.
    Monty uses this for the "take care of yourself" card on the dashboard.
    """
    try:
        from innovations.cbd import compute_cbd_score
        result = await compute_cbd_score(caregiver_id, db)
        return result
    except Exception as e:
        logger.error(f"CBD computation failed: {e}")
        return {"score": 0, "error": str(e)}


# =====================================================
# GET /caregiver/aac/{patient_id}
# =====================================================


@router.get("/caregiver/aac/{patient_id}")
async def get_aac_score(patient_id: str, db: AsyncSession = Depends(get_db)):
    """
    Compute and return the current AAC score with full component breakdown.
    Monty's Flutter app calls this for the AAC badge on the caregiver dashboard.
    """
    try:
        from innovations.aac import compute_aac_score
        result = await compute_aac_score(patient_id, db)
        return result
    except Exception as e:
        logger.error(f"AAC computation failed: {e}")
        return {"score": 70, "error": str(e)}


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def _derive_alert_type(alert: Alert) -> str:
    """
    Derive a categorical alert_type from the alert message/context.
    Android Alert.alert_type is used for icon selection in the feed.
    """
    text = f"{alert.message or ''} {alert.context or ''}".lower()
    if "fall" in text:
        return "fall"
    if "wander" in text or "location" in text:
        return "wandering"
    if "medication" in text or "medicine" in text or "pill" in text:
        return "medication"
    if "distress" in text or "confused" in text or "agitat" in text:
        return "cognitive"
    if "emergency" in alert.priority:
        return "emergency"
    return "general"


def _extract_title(message: str) -> str:
    """Short title (≤60 chars) derived from the first sentence of the alert message."""
    if not message:
        return "Alert"
    first_sentence = message.split(".")[0].strip()
    if len(first_sentence) <= 60:
        return first_sentence
    return first_sentence[:57] + "..."


def _aac_to_risk(aac_score: int) -> str:
    """Convert AAC score (0-100) to Android risk_level string."""
    if aac_score >= 70:
        return "LOW"
    if aac_score >= 50:
        return "MEDIUM"
    if aac_score >= 30:
        return "HIGH"
    return "CRITICAL"


async def _compute_avg_cct(
    patient_id: str,
    day_start: datetime,
    day_end: datetime,
    db: AsyncSession,
) -> float:
    """Compute average CCT composite for a day window."""
    result = await db.execute(
        select(CCTScore)
        .where(and_(
            CCTScore.user_id == patient_id,
            CCTScore.scored_at >= day_start,
            CCTScore.scored_at <= day_end,
        ))
    )
    scores = result.scalars().all()
    if not scores:
        return 0.0
    return round(sum(s.composite_score for s in scores) / len(scores), 3)


def _extract_steps_from_event(event: Event) -> int:
    """
    Some events have step counts in their metadata_json.
    This is a best-effort extraction — returns 0 if nothing found.
    """
    if not event.metadata_json:
        return 0
    try:
        meta = json.loads(event.metadata_json)
        return int(meta.get("steps", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def _format_events_for_llm(events: list[Event]) -> str:
    """Turn event rows into a readable timeline for the LLM"""
    if not events:
        return ""
    lines = []
    for e in events:
        time_str = e.timestamp.strftime("%I:%M %p")
        lines.append(f"- {time_str} | {e.event_type.upper()} ({e.severity}) — {e.description}")
    return "\n".join(lines)


def _format_cct_for_llm(scores: list[CCTScore]) -> str:
    lines = []
    for s in scores:
        time_str = s.scored_at.strftime("%I:%M %p")
        lines.append(f"- {time_str} | Composite: {s.composite_score:.2f} (recall={s.recall_accuracy:.2f}, coherence={s.narrative_coherence:.2f})")
    return "\n".join(lines)


def _format_alerts_for_llm(alerts: list[Alert]) -> str:
    lines = []
    for a in alerts:
        time_str = a.timestamp.strftime("%I:%M %p")
        ack_status = "acknowledged" if a.acknowledged else "unacknowledged"
        lines.append(f"- {time_str} | {a.priority.upper()} — {a.message} [{ack_status}]")
    return "\n".join(lines)


async def _compute_cct_trend(
    patient_id: str,
    today: date,
    today_scores: list[CCTScore],
    db: AsyncSession,
) -> str:
    """
    Compare today's avg CCT composite to yesterday's.
    Returns: "stable", "improving", or "declining"
    """
    if not today_scores:
        return "stable"

    today_avg = sum(s.composite_score for s in today_scores) / len(today_scores)

    # Get yesterday's scores
    yesterday = today - timedelta(days=1)
    yday_start = datetime.combine(yesterday, datetime.min.time())
    yday_end = datetime.combine(yesterday, datetime.max.time())

    yday_result = await db.execute(
        select(CCTScore)
        .where(and_(
            CCTScore.user_id == patient_id,
            CCTScore.scored_at >= yday_start,
            CCTScore.scored_at <= yday_end,
        ))
    )
    yday_scores = yday_result.scalars().all()

    if not yday_scores:
        return "stable"

    yday_avg = sum(s.composite_score for s in yday_scores) / len(yday_scores)

    # A change of more than 0.05 (5%) is meaningful, otherwise noise
    diff = today_avg - yday_avg
    if diff > 0.05:
        return "improving"
    elif diff < -0.05:
        return "declining"
    else:
        return "stable"