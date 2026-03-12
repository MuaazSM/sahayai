import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from api.models.tables import CCTScore, AACScore, Event, Reminder, User

logger = logging.getLogger("sahayai.aac")

# =====================================================
# AAC — Adaptive Autonomy Calibration
#
# The whole point: over-assisting dementia patients accelerates
# cognitive decline. Under-assisting puts them at risk.
# AAC finds the sweet spot by computing a real-time Confidence
# Score (0-100) that modulates how much the system intervenes.
#
# High score (80+) → system backs off, respects independence
# Medium (50-79)   → gentle check-ins, moderate monitoring
# Low (below 50)   → proactive help, caregiver awareness up
#
# COMPONENTS (weighted):
#   1. CCT cognitive scores     — 40% (most important signal)
#   2. Vitals stability         — 20% (heart rate anomalies = concern)
#   3. Routine adherence        — 25% (skipping meds = red flag)
#   4. Time-of-day patterns     — 15% (sundowning is real — late
#      afternoon/evening cognition drops in dementia patients)
#
# Recalculated every 15 minutes or on-demand after significant events.
# =====================================================

# How much each component contributes to the final score
WEIGHTS = {
    "cct": 0.40,
    "vitals": 0.20,
    "routine": 0.25,
    "time_of_day": 0.15,
}


async def compute_aac_score(user_id: str, db: AsyncSession) -> dict:
    """
    Compute the current AAC Confidence Score for a patient.
    Returns a dict with the overall score + each component breakdown
    so the caregiver dashboard can show what's contributing.
    """
    logger.info(f"Computing AAC for user {user_id}")

    # Get the user's baseline — this is their "normal" that the
    # Learning Agent adjusts over time
    user = await db.get(User, user_id)
    baseline = user.aac_baseline if user else 70

    # ---------------------------------------------------------------
    # 1. CCT COMPONENT (40%)
    #    Average of recent CCT composite scores (last 6 hours).
    #    A healthy elderly person scores 0.65-0.85.
    #    Below 0.5 = significant concern.
    # ---------------------------------------------------------------
    cct_component = await _compute_cct_component(user_id, db)

    # ---------------------------------------------------------------
    # 2. VITALS COMPONENT (20%)
    #    Based on recent heart rate events. Stable HR in normal
    #    range = good. Spikes, drops, high variability = concern.
    # ---------------------------------------------------------------
    vitals_component = await _compute_vitals_component(user_id, db)

    # ---------------------------------------------------------------
    # 3. ROUTINE ADHERENCE COMPONENT (25%)
    #    Did they take their meds? Follow their routine?
    #    Skipping routines is one of the earliest signs of a bad day.
    # ---------------------------------------------------------------
    routine_component = await _compute_routine_component(user_id, db)

    # ---------------------------------------------------------------
    # 4. TIME-OF-DAY COMPONENT (15%)
    #    Sundowning — cognitive function drops in late afternoon/evening
    #    for many dementia patients. We bake this into the score so
    #    the system automatically becomes more attentive after 4 PM.
    # ---------------------------------------------------------------
    time_component = _compute_time_component()

    # ---------------------------------------------------------------
    # WEIGHTED COMPOSITE
    # Each component is 0-100, weighted sum gives us the final score
    # ---------------------------------------------------------------
    raw_score = (
        cct_component * WEIGHTS["cct"] +
        vitals_component * WEIGHTS["vitals"] +
        routine_component * WEIGHTS["routine"] +
        time_component * WEIGHTS["time_of_day"]
    )

    # Blend with baseline so the score doesn't swing wildly on a single
    # bad reading. 70% current calculation, 30% historical baseline.
    # This smooths out noise while still being responsive to real changes.
    final_score = int(raw_score * 0.7 + baseline * 0.3)
    final_score = max(0, min(100, final_score))

    # ---------------------------------------------------------------
    # Save to DB as time-series so we can show trends on dashboard
    # ---------------------------------------------------------------
    aac_entry = AACScore(
        id=str(uuid.uuid4()),
        user_id=user_id,
        score=final_score,
        cct_component=cct_component,
        vitals_component=vitals_component,
        routine_component=routine_component,
        time_of_day_component=time_component,
    )
    db.add(aac_entry)

    logger.info(
        f"AAC computed: {final_score}/100 "
        f"(cct={cct_component:.0f}, vitals={vitals_component:.0f}, "
        f"routine={routine_component:.0f}, time={time_component:.0f})"
    )

    return {
        "score": final_score,
        "cct_component": cct_component,
        "vitals_component": vitals_component,
        "routine_component": routine_component,
        "time_of_day_component": time_component,
        "baseline": baseline,
    }


# =====================================================
# COMPONENT CALCULATIONS
# =====================================================

async def _compute_cct_component(user_id: str, db: AsyncSession) -> float:
    """
    Pull CCT scores from the last 6 hours and convert to a 0-100 scale.
    
    CCT composite is 0.0-1.0 where:
      0.8+ = sharp, scoring 80+
      0.6-0.8 = normal elderly, scoring 60-80
      0.4-0.6 = mild concern, scoring 40-60
      below 0.4 = significant impairment, scoring 0-40
    """
    six_hours_ago = datetime.utcnow() - timedelta(hours=6)

    result = await db.execute(
        select(CCTScore)
        .where(and_(
            CCTScore.user_id == user_id,
            CCTScore.scored_at >= six_hours_ago,
        ))
        .order_by(CCTScore.scored_at.desc())
        .limit(10)
    )
    scores = result.scalars().all()

    if not scores:
        # No recent CCT data — fall back to a neutral score.
        # Don't assume bad OR good without evidence.
        return 65.0

    # Simple average of composite scores, mapped to 0-100
    avg_composite = sum(s.composite_score for s in scores) / len(scores)

    # Also check for TREND within the window — a dropping score
    # is more concerning than a stable low score
    if len(scores) >= 3:
        recent_avg = sum(s.composite_score for s in scores[:2]) / 2
        older_avg = sum(s.composite_score for s in scores[-2:]) / 2
        trend_penalty = 0.0

        # If scores are dropping, apply a penalty
        if recent_avg < older_avg - 0.1:
            trend_penalty = 10.0
            logger.info(f"CCT trend penalty: recent={recent_avg:.2f} vs older={older_avg:.2f}")

        return max(0, min(100, avg_composite * 100 - trend_penalty))

    return max(0, min(100, avg_composite * 100))


async def _compute_vitals_component(user_id: str, db: AsyncSession) -> float:
    """
    Check recent vitals-related events for anomalies.

    Normal HR for elderly at rest: 60-100 bpm
    Concerning: sustained >100 or <50
    
    We look at recent events with HR data. No events = assume stable.
    """
    two_hours_ago = datetime.utcnow() - timedelta(hours=2)

    result = await db.execute(
        select(Event)
        .where(and_(
            Event.user_id == user_id,
            Event.timestamp >= two_hours_ago,
            Event.event_type.in_(["distress", "fall", "vitals_anomaly"]),
        ))
    )
    concerning_events = result.scalars().all()

    if not concerning_events:
        # No concerning vitals events recently — that's good
        return 85.0

    # Each concerning event drops the score
    # Falls are worse than general distress
    penalty = 0
    for event in concerning_events:
        if event.event_type == "fall":
            penalty += 30  # falls are a big deal
        elif event.event_type == "distress":
            penalty += 15
        elif event.event_type == "vitals_anomaly":
            penalty += 10

    return max(0, min(100, 85 - penalty))


async def _compute_routine_component(user_id: str, db: AsyncSession) -> float:
    """
    How well is the patient following their routines today?
    
    We check medication reminders specifically because:
    - Missing meds is the #1 caregiver concern
    - It's a reliable early indicator of a bad cognitive day
    - It's objectively measurable (confirmed vs missed)
    """
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())

    # Count today's medication reminders
    total_result = await db.execute(
        select(func.count(Reminder.id))
        .where(and_(
            Reminder.user_id == user_id,
            Reminder.reminder_type == "medication",
            Reminder.scheduled_time >= today_start,
            Reminder.scheduled_time <= datetime.utcnow(),
        ))
    )
    total = total_result.scalar() or 0

    if total == 0:
        # No medication reminders have been due yet today
        # Could be early morning — assume they'll follow routine
        return 75.0

    confirmed_result = await db.execute(
        select(func.count(Reminder.id))
        .where(and_(
            Reminder.user_id == user_id,
            Reminder.reminder_type == "medication",
            Reminder.scheduled_time >= today_start,
            Reminder.scheduled_time <= datetime.utcnow(),
            Reminder.status == "confirmed",
        ))
    )
    confirmed = confirmed_result.scalar() or 0

    missed_result = await db.execute(
        select(func.count(Reminder.id))
        .where(and_(
            Reminder.user_id == user_id,
            Reminder.reminder_type == "medication",
            Reminder.scheduled_time >= today_start,
            Reminder.scheduled_time <= datetime.utcnow(),
            Reminder.status == "missed",
        ))
    )
    missed = missed_result.scalar() or 0

    # Confirmed meds boost the score, missed ones drop it hard
    # Pending ones (not yet confirmed or missed) are neutral
    adherence = confirmed / total if total > 0 else 0.75
    miss_penalty = missed * 15  # each missed med is a -15 hit

    return max(0, min(100, adherence * 85 - miss_penalty))


def _compute_time_component() -> float:
    """
    Sundowning pattern — cognitive function tends to dip in late
    afternoon and evening for dementia patients. This is well-documented
    in clinical literature and we factor it in so the system
    automatically becomes more vigilant during high-risk hours.

    Score curve:
      6 AM - 11 AM:  85 (morning — best cognitive period)
      11 AM - 2 PM:  80 (midday — slight post-lunch dip)
      2 PM - 5 PM:   65 (afternoon — sundowning begins)
      5 PM - 8 PM:   50 (evening — peak sundowning risk)
      8 PM - 10 PM:  55 (late evening — settling down)
      10 PM - 6 AM:  45 (night — disorientation risk high)
    """
    hour = datetime.utcnow().hour

    time_scores = {
        range(6, 11): 85,    # morning — sharp
        range(11, 14): 80,   # midday — okay
        range(14, 17): 65,   # afternoon — sundowning starts
        range(17, 20): 50,   # evening — peak risk
        range(20, 22): 55,   # late evening
    }

    for time_range, score in time_scores.items():
        if hour in time_range:
            return float(score)

    # Night hours (10 PM - 6 AM) — highest disorientation risk
    return 45.0


async def get_latest_aac(user_id: str, db: AsyncSession) -> int:
    """
    Quick lookup — grab the most recent AAC score without recomputing.
    Used by the Context Agent when it just needs the current value.
    Falls back to user baseline if no score exists yet.
    """
    result = await db.execute(
        select(AACScore)
        .where(AACScore.user_id == user_id)
        .order_by(AACScore.calculated_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if latest:
        return latest.score

    user = await db.get(User, user_id)
    return user.aac_baseline if user else 70