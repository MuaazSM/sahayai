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

@router.get("/caregiver/alerts/{patient_id}", response_model=AlertsResponse)
async def get_alerts(
    patient_id: str,
    since: str = Query(default=None, description="ISO timestamp — only return alerts after this time"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the alert feed for a patient. The Flutter app polls this
    on the caregiver dashboard (and also gets real-time pushes via WebSocket,
    but this endpoint is the fallback + history scroll).
    """
    logger.info(f"Fetching alerts for patient {patient_id} (limit={limit})")

    query = (
        select(Alert)
        .where(Alert.patient_id == patient_id)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
    )

    # If `since` is provided, only return alerts newer than that timestamp
    # This lets the Flutter app do incremental fetches without re-downloading everything
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
            priority=a.priority,
            message=a.message,
            context=a.context,
            reasoning=a.reasoning,
            timestamp=a.timestamp.isoformat(),
            acknowledged=a.acknowledged,
        )
        for a in alerts
    ]

    logger.info(f"Returning {len(alert_items)} alerts")
    return AlertsResponse(alerts=alert_items)


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
    logger.info(f"Acknowledging alert {alert_id}: action={request.action}")

    alert = await db.get(Alert, alert_id)
    if not alert:
        return AcknowledgeResponse(success=False, updated_alert={"error": "Alert not found"})

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledge_action = request.action
    alert.acknowledge_note = request.note

    # If escalated, we'd normally notify secondary caregivers here
    # For the hackathon demo, just log it
    if request.action == "escalate":
        logger.warning(f"Alert {alert_id} ESCALATED by caregiver. Would notify secondary caregivers.")

    return AcknowledgeResponse(
        success=True,
        updated_alert={
            "id": alert.id,
            "acknowledged": True,
            "acknowledged_at": alert.acknowledged_at.isoformat(),
            "action": request.action,
            "note": request.note,
        },
    )


# =====================================================
# GET /caregiver/summary/{patient_id}
# =====================================================

@router.get("/caregiver/summary/{patient_id}", response_model=SummaryResponse)
async def get_summary(
    patient_id: str,
    date_str: str = Query(default=None, alias="date", description="YYYY-MM-DD, defaults to today"),
    db: AsyncSession = Depends(get_db),
):
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
                events_list = []
                try:
                    events_list = [
                        SummaryEvent(**e) for e in json.loads(cached.events_json or "[]")
                    ]
                except Exception:
                    pass

                return SummaryResponse(
                    summary_text=cached.summary_text,
                    date=cached.summary_date.isoformat(),
                    metrics=SummaryMetrics(
                        medication_adherence=cached.medication_adherence,
                        steps=cached.total_steps,
                        alerts_count=cached.alerts_count,
                        avg_aac_score=cached.avg_aac_score,
                        cct_trend=cached.cct_trend,
                    ),
                    events=events_list,
                    cct_scores=[],
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

        # Medication adherence
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

        cct_trend = await _compute_cct_trend(patient_id, summary_date, cct_scores, db)

        events_for_response = [
            SummaryEvent(
                time=e.timestamp.strftime("%H:%M"),
                type=e.event_type,
                description=e.description,
                severity=e.severity,
            )
            for e in events
        ]

        cct_for_response = [
            CCTScorePoint(
                date=c.scored_at.strftime("%Y-%m-%d"),
                score=c.composite_score,
            )
            for c in cct_scores
        ]

        # Generate summary via LLM
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

        summary_text = await chat_completion(
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
                summary_text=summary_text,
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

        return SummaryResponse(
            summary_text=summary_text,
            date=summary_date.isoformat(),
            metrics=SummaryMetrics(
                medication_adherence=medication_adherence,
                steps=total_steps,
                alerts_count=len(alerts),
                avg_aac_score=avg_aac,
                cct_trend=cct_trend,
            ),
            events=events_for_response,
            cct_scores=cct_for_response,
        )

    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        return SummaryResponse(
            summary_text="I had trouble generating today's summary. Please try again in a moment.",
            date=date.today().isoformat(),
            metrics=SummaryMetrics(
                medication_adherence=0.0,
                steps=0,
                alerts_count=0,
                avg_aac_score=70,
                cct_trend="stable",
            ),
            events=[],
            cct_scores=[],
        )


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