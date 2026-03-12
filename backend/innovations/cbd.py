import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from api.models.tables import Alert, User, Event

logger = logging.getLogger("sahayai.cbd")

# =====================================================
# CBD — Caregiver Burnout Detection
#
# Caregiver breakdown is the #1 predictor of patient
# institutionalization. Nobody builds for the person up
# at 3 AM worrying. We do.
#
# We passively track 5 behavioral signals that indicate
# the caregiver is wearing down:
#
# 1. ALERT RESPONSE TIME (30%)
#    How fast do they acknowledge alerts? Getting slower
#    over the week = they're overwhelmed or checked out.
#
# 2. ENGAGEMENT FREQUENCY (20%)
#    How often are they checking in? Sudden drop = they're
#    avoiding the app. Sudden spike = anxiety/hypervigilance.
#    Both are burnout indicators.
#
# 3. LATE NIGHT USAGE (20%)
#    Using the app between midnight and 5 AM means they're
#    not sleeping. Sleep deprivation is burnout fuel.
#
# 4. ALERT ACKNOWLEDGMENT RATE (15%)
#    What % of alerts do they actually acknowledge vs ignore?
#    Dropping ack rate = alert fatigue = burnout.
#
# 5. ESCALATION FREQUENCY (15%)
#    How often do they escalate alerts to others? More
#    escalations = they're reaching their limit.
#
# Score: 0 (fresh and fine) to 100 (completely burnt out)
#
# GRADUATED INTERVENTIONS:
#   0-30:  Nothing. They're doing great.
#   30-50: Gentle encouragement. "Remember to take care of yourself."
#   50-70: Suggest respite. "Consider asking family to help today."
#   70-85: Increase system autonomy. SahayAI handles more silently.
#   85+:   Alert secondary caregivers. "Priya may need support."
# =====================================================

WEIGHTS = {
    "response_time": 0.30,
    "engagement": 0.20,
    "late_night": 0.20,
    "ack_rate": 0.15,
    "escalation": 0.15,
}


async def compute_cbd_score(caregiver_id: str, db: AsyncSession) -> dict:
    """
    Full CBD computation using rolling 7-day behavioral data.
    Returns score + component breakdown + intervention suggestion.
    """
    logger.info(f"Computing CBD for caregiver {caregiver_id}")

    # ---------------------------------------------------------------
    # 1. ALERT RESPONSE TIME COMPONENT
    # ---------------------------------------------------------------
    response_time_score = await _compute_response_time_component(caregiver_id, db)

    # ---------------------------------------------------------------
    # 2. ENGAGEMENT FREQUENCY COMPONENT
    # ---------------------------------------------------------------
    engagement_score = await _compute_engagement_component(caregiver_id, db)

    # ---------------------------------------------------------------
    # 3. LATE NIGHT USAGE COMPONENT
    # ---------------------------------------------------------------
    late_night_score = await _compute_late_night_component(caregiver_id, db)

    # ---------------------------------------------------------------
    # 4. ALERT ACKNOWLEDGMENT RATE COMPONENT
    # ---------------------------------------------------------------
    ack_rate_score = await _compute_ack_rate_component(caregiver_id, db)

    # ---------------------------------------------------------------
    # 5. ESCALATION FREQUENCY COMPONENT
    # ---------------------------------------------------------------
    escalation_score = await _compute_escalation_component(caregiver_id, db)

    # ---------------------------------------------------------------
    # WEIGHTED COMPOSITE
    # ---------------------------------------------------------------
    raw_score = (
        response_time_score * WEIGHTS["response_time"] +
        engagement_score * WEIGHTS["engagement"] +
        late_night_score * WEIGHTS["late_night"] +
        ack_rate_score * WEIGHTS["ack_rate"] +
        escalation_score * WEIGHTS["escalation"]
    )

    # Blend with stored CBD score so it doesn't jump around.
    # 60% new calculation, 40% previous score for smoothing.
    user = await db.get(User, caregiver_id)
    previous_score = user.cbd_score if user else 0.0
    final_score = raw_score * 0.6 + previous_score * 0.4
    final_score = max(0.0, min(100.0, final_score))

    # Update the user record with the new CBD score
    if user:
        user.cbd_score = final_score

    # Determine intervention
    intervention = _get_intervention(final_score)

    logger.info(
        f"CBD computed: {final_score:.0f}/100 "
        f"(resp_time={response_time_score:.0f}, engagement={engagement_score:.0f}, "
        f"late_night={late_night_score:.0f}, ack_rate={ack_rate_score:.0f}, "
        f"escalation={escalation_score:.0f})"
    )

    return {
        "score": round(final_score, 1),
        "components": {
            "response_time": round(response_time_score, 1),
            "engagement": round(engagement_score, 1),
            "late_night": round(late_night_score, 1),
            "ack_rate": round(ack_rate_score, 1),
            "escalation": round(escalation_score, 1),
        },
        "intervention_level": _get_intervention_level(final_score),
        "intervention_message": intervention,
        "previous_score": round(previous_score, 1),
    }


# =====================================================
# COMPONENT CALCULATIONS (all use rolling 7-day windows)
# =====================================================

async def _compute_response_time_component(caregiver_id: str, db: AsyncSession) -> float:
    """
    How quickly does the caregiver respond to alerts?
    
    Healthy: <5 min average response time = score 0 (no burnout signal)
    Concerning: 5-30 min = score 30-60
    Bad: 30+ min or not responding = score 70-100
    
    We also check if response times are TRENDING slower this week
    vs last week — a worsening trend is more concerning than
    consistently slow responses (which might just be their schedule).
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Get all acknowledged alerts for this caregiver in the last 7 days
    result = await db.execute(
        select(Alert)
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledged == True,
            Alert.acknowledged_at.isnot(None),
        ))
        .order_by(Alert.timestamp.desc())
    )
    acked_alerts = result.scalars().all()

    if not acked_alerts:
        # No acknowledged alerts — either no alerts happened (good)
        # or they're ignoring everything (bad). Check total alerts.
        total_result = await db.execute(
            select(func.count(Alert.id))
            .where(and_(
                Alert.caregiver_id == caregiver_id,
                Alert.timestamp >= seven_days_ago,
            ))
        )
        total_alerts = total_result.scalar() or 0

        if total_alerts == 0:
            return 0.0  # no alerts at all — nothing to respond to
        else:
            return 80.0  # alerts exist but none acknowledged — bad sign

    # Calculate average response time in minutes
    response_times = []
    for alert in acked_alerts:
        delta = (alert.acknowledged_at - alert.timestamp).total_seconds() / 60.0
        # Cap at 24 hours — anything beyond that is basically "didn't respond"
        response_times.append(min(delta, 1440))

    avg_response_min = sum(response_times) / len(response_times)

    # Also check trend: compare first half vs second half of the week
    if len(response_times) >= 4:
        midpoint = len(response_times) // 2
        # acked_alerts is ordered desc, so first half = recent, second half = older
        recent_avg = sum(response_times[:midpoint]) / midpoint
        older_avg = sum(response_times[midpoint:]) / (len(response_times) - midpoint)

        # If recent response times are >50% slower, add a trend penalty
        if older_avg > 0 and recent_avg > older_avg * 1.5:
            trend_penalty = 15.0
            logger.info(f"CBD: response time worsening trend detected (+15)")
        else:
            trend_penalty = 0.0
    else:
        trend_penalty = 0.0

    # Map average response time to a 0-100 score
    if avg_response_min < 5:
        base_score = 0.0       # responding within 5 min — great
    elif avg_response_min < 15:
        base_score = 20.0      # 5-15 min — normal
    elif avg_response_min < 30:
        base_score = 40.0      # 15-30 min — getting slow
    elif avg_response_min < 60:
        base_score = 60.0      # 30-60 min — concerning
    elif avg_response_min < 180:
        base_score = 80.0      # 1-3 hours — they're struggling
    else:
        base_score = 95.0      # 3+ hours — checked out

    return min(100.0, base_score + trend_penalty)


async def _compute_engagement_component(caregiver_id: str, db: AsyncSession) -> float:
    """
    How often is the caregiver checking in?
    
    We look at two things:
    1. Daily login/interaction frequency (via events or conversations)
    2. Whether frequency is DROPPING (avoidance) or SPIKING (anxiety)
    
    Both extremes are bad — healthy engagement is consistent.
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)

    # Count interactions per day this week
    this_week_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledged == True,
        ))
    )
    this_week_interactions = this_week_result.scalar() or 0

    # Count interactions per day last week for comparison
    last_week_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= fourteen_days_ago,
            Alert.timestamp < seven_days_ago,
            Alert.acknowledged == True,
        ))
    )
    last_week_interactions = last_week_result.scalar() or 0

    # No data at all — can't assess, return neutral
    if this_week_interactions == 0 and last_week_interactions == 0:
        return 20.0

    # Calculate daily averages
    this_week_daily = this_week_interactions / 7.0
    last_week_daily = last_week_interactions / 7.0

    # Check for sudden drop (avoidance) or spike (anxiety)
    if last_week_daily > 0:
        change_ratio = this_week_daily / last_week_daily

        if change_ratio < 0.3:
            # Engagement dropped by 70%+ — they're avoiding the app
            return 75.0
        elif change_ratio < 0.5:
            # Significant drop
            return 55.0
        elif change_ratio > 3.0:
            # 3x spike — hypervigilance, anxiety
            return 60.0
        elif change_ratio > 2.0:
            # Moderate spike
            return 40.0
        else:
            # Stable engagement — healthy
            return 10.0
    else:
        # No baseline to compare — just check if they're engaging at all
        if this_week_daily > 0:
            return 15.0
        else:
            return 50.0  # not engaging at all


async def _compute_late_night_component(caregiver_id: str, db: AsyncSession) -> float:
    """
    Are they using the app between midnight and 5 AM?
    That means they're not sleeping, which is a direct burnout driver.
    
    We count late-night interactions over the past 7 days.
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Get all alerts for this caregiver in the past week
    result = await db.execute(
        select(Alert)
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledged == True,
            Alert.acknowledged_at.isnot(None),
        ))
    )
    alerts = result.scalars().all()

    if not alerts:
        return 0.0

    # Count how many were acknowledged between midnight and 5 AM
    late_night_count = 0
    for alert in alerts:
        ack_hour = alert.acknowledged_at.hour
        if 0 <= ack_hour < 5:
            late_night_count += 1

    # Also count late-night alert CREATIONS (even unacknowledged)
    # because that means the patient is having issues at night
    # which stresses the caregiver even if they don't respond
    night_alert_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            func.extract("hour", Alert.timestamp) < 5,
        ))
    )
    night_alerts_total = night_alert_result.scalar() or 0

    # Score based on how many late-night interactions happened
    total_late = late_night_count + night_alerts_total
    if total_late == 0:
        return 0.0
    elif total_late <= 2:
        return 30.0    # occasional — maybe one bad night
    elif total_late <= 5:
        return 55.0    # multiple nights disrupted
    elif total_late <= 10:
        return 75.0    # most nights disrupted
    else:
        return 95.0    # chronic sleep deprivation


async def _compute_ack_rate_component(caregiver_id: str, db: AsyncSession) -> float:
    """
    What percentage of alerts do they actually acknowledge?
    Dropping acknowledgment rate = alert fatigue = burnout.
    
    High ack rate (>80%) = engaged = low burnout signal
    Low ack rate (<40%) = checked out = high burnout signal
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
        ))
    )
    total = total_result.scalar() or 0

    if total == 0:
        return 0.0  # no alerts to acknowledge

    acked_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledged == True,
        ))
    )
    acked = acked_result.scalar() or 0

    ack_rate = acked / total

    # Map ack rate to burnout score (inverted — high ack = low burnout)
    if ack_rate >= 0.9:
        return 0.0       # acknowledging almost everything — engaged
    elif ack_rate >= 0.7:
        return 20.0
    elif ack_rate >= 0.5:
        return 45.0
    elif ack_rate >= 0.3:
        return 65.0
    else:
        return 90.0      # ignoring most alerts — major burnout signal


async def _compute_escalation_component(caregiver_id: str, db: AsyncSession) -> float:
    """
    How often are they escalating alerts to secondary caregivers?
    Occasional escalation is healthy (asking for help when needed).
    Frequent escalation = overwhelmed, at their limit.
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total_acked_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledged == True,
        ))
    )
    total_acked = total_acked_result.scalar() or 0

    if total_acked == 0:
        return 0.0

    escalated_result = await db.execute(
        select(func.count(Alert.id))
        .where(and_(
            Alert.caregiver_id == caregiver_id,
            Alert.timestamp >= seven_days_ago,
            Alert.acknowledge_action == "escalate",
        ))
    )
    escalated = escalated_result.scalar() or 0

    escalation_rate = escalated / total_acked

    if escalation_rate == 0:
        return 0.0        # never escalates — handling it themselves
    elif escalation_rate < 0.1:
        return 15.0       # rare escalation — healthy boundary-setting
    elif escalation_rate < 0.3:
        return 40.0       # escalating ~1 in 3 — starting to lean on others
    elif escalation_rate < 0.5:
        return 65.0       # escalating half — overwhelmed
    else:
        return 90.0       # escalating most — at their limit


# =====================================================
# INTERVENTIONS
# =====================================================

def _get_intervention_level(score: float) -> str:
    if score < 30:
        return "none"
    elif score < 50:
        return "gentle"
    elif score < 70:
        return "suggest_respite"
    elif score < 85:
        return "increase_autonomy"
    else:
        return "alert_secondary"


def _get_intervention(score: float) -> str | None:
    if score < 30:
        return None

    if score >= 85:
        return (
            "We've noticed you might be carrying a heavy load lately. "
            "We've increased SahayAI's monitoring so you can step back a bit. "
            "Would you like us to notify another family member to help?"
        )
    elif score >= 70:
        return (
            "You've been incredibly attentive this week. SahayAI is handling "
            "more routine checks automatically so you can breathe. Please "
            "consider asking someone to cover for a few hours today."
        )
    elif score >= 50:
        return (
            "You're doing an amazing job caring for your loved one. "
            "Remember — taking a break isn't selfish, it's necessary. "
            "Even a 20-minute walk or a call with a friend can help recharge."
        )
    elif score >= 30:
        return (
            "Just a gentle reminder — you matter too. "
            "Taking care of yourself helps you take better care of them."
        )

    return None