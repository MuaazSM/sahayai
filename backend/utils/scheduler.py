import asyncio
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger("sahayai.scheduler")

# Track the background task so we can cancel it on shutdown
_scheduler_task: asyncio.Task | None = None


def start_scheduler():
    """Called from main.py lifespan — kicks off the background loop"""
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Background scheduler started")


def stop_scheduler():
    """Called on shutdown — cancel the loop cleanly"""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        logger.info("Background scheduler stopped")


async def _scheduler_loop():
    """
    Runs forever in the background. Checks every 5 minutes if
    there's anything to do. Right now it handles:
    
    1. End-of-day summary generation (9:30 PM)
    2. AAC score recalculation (every 15 minutes)
    3. Missed medication detection (check reminders past their time)
    
    Why 5-minute intervals? Frequent enough to catch things promptly,
    infrequent enough to not hammer the database. The scheduler
    itself uses zero LLM calls — it just triggers other functions.
    """
    logger.info("Scheduler loop running — checking every 5 minutes")

    # Track what we've already done today so we don't repeat
    last_summary_date = None
    last_aac_recalc = datetime.min

    while True:
        try:
            now = datetime.utcnow()
            # IST is UTC+5:30 — hackathon is in Mumbai
            ist_hour = (now.hour + 5) % 24
            ist_minute = (now.minute + 30) % 60

            # -------------------------------------------------------
            # 1. AUTO-GENERATE DAILY SUMMARIES at 9:30 PM IST
            #    For every patient who had any activity today.
            #    Caregiver sees the summary when they open the app.
            # -------------------------------------------------------
            if ist_hour == 21 and ist_minute < 5 and last_summary_date != now.date():
                logger.info("Triggering end-of-day summary generation")
                await _generate_daily_summaries()
                last_summary_date = now.date()

            # -------------------------------------------------------
            # 2. RECALCULATE AAC SCORES every 15 minutes
            #    The AAC score needs to stay fresh because the
            #    time-of-day component changes (sundowning curve)
            #    and new CCT/vitals data might have come in.
            # -------------------------------------------------------
            if (now - last_aac_recalc).total_seconds() >= 900:  # 900s = 15 min
                await _recalculate_aac_scores()
                last_aac_recalc = now

            # -------------------------------------------------------
            # 3. CHECK FOR MISSED MEDICATIONS
            #    If a reminder was due >30 min ago and still pending,
            #    mark it as missed and log an event.
            # -------------------------------------------------------
            await _check_missed_reminders()

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled — shutting down")
            break
        except Exception as e:
            # Scheduler crashing should never take down the server.
            # Log it, sleep, try again next cycle.
            logger.error(f"Scheduler error: {e}", exc_info=True)

        await asyncio.sleep(300)  # 5 minutes


async def _generate_daily_summaries():
    """
    Find all patients who had events today and generate a cached
    summary for each one. This way when Priya opens the app at
    10 PM, the summary is already there — instant load, no waiting
    for an LLM call.
    """
    from api.models.database import async_session
    from api.models.tables import User, Event, DailySummary
    from sqlalchemy import select, and_, func

    try:
        async with async_session() as db:
            today = date.today()
            day_start = datetime.combine(today, datetime.min.time())
            day_end = datetime.combine(today, datetime.max.time())

            # Find patients who had events today
            patient_ids_result = await db.execute(
                select(Event.user_id)
                .where(and_(
                    Event.timestamp >= day_start,
                    Event.timestamp <= day_end,
                ))
                .distinct()
            )
            patient_ids = [row[0] for row in patient_ids_result.fetchall()]

            if not patient_ids:
                logger.info("No patient activity today — skipping summary generation")
                return

            for patient_id in patient_ids:
                # Check if summary already exists (from on-demand generation)
                existing_result = await db.execute(
                    select(func.count(DailySummary.id))
                    .where(and_(
                        DailySummary.patient_id == patient_id,
                        DailySummary.summary_date == today,
                    ))
                )
                if existing_result.scalar() > 0:
                    logger.info(f"Summary for {patient_id} already cached — skipping")
                    continue

                # Generate it by calling the same logic the endpoint uses
                try:
                    from api.routes.caregiver import get_summary
                    # We can't call the FastAPI endpoint directly from here,
                    # so we import the generation logic instead
                    await _generate_single_summary(patient_id, today, db)
                    logger.info(f"Auto-generated summary for {patient_id}")
                except Exception as e:
                    logger.error(f"Failed to generate summary for {patient_id}: {e}")

            await db.commit()

    except Exception as e:
        logger.error(f"Daily summary generation failed: {e}", exc_info=True)


async def _generate_single_summary(patient_id: str, summary_date: date, db):
    """
    Generate and cache a single patient's daily summary.
    Pulls events, scores, alerts, computes metrics, calls LLM.
    """
    import json
    import uuid
    from sqlalchemy import select, and_, func
    from api.models.tables import (
        User, Event, Alert, CCTScore, AACScore, Reminder, DailySummary
    )
    from utils.llm import chat_completion

    day_start = datetime.combine(summary_date, datetime.min.time())
    day_end = datetime.combine(summary_date, datetime.max.time())

    user = await db.get(User, patient_id)
    user_name = user.name if user else "the patient"
    conditions = user.medical_conditions if user else "unknown"

    # Pull events
    events_result = await db.execute(
        select(Event)
        .where(and_(Event.user_id == patient_id, Event.timestamp >= day_start, Event.timestamp <= day_end))
        .order_by(Event.timestamp.asc())
    )
    events = events_result.scalars().all()

    # Pull CCT
    cct_result = await db.execute(
        select(CCTScore)
        .where(and_(CCTScore.user_id == patient_id, CCTScore.scored_at >= day_start, CCTScore.scored_at <= day_end))
    )
    cct_scores = cct_result.scalars().all()

    # Pull AAC
    aac_result = await db.execute(
        select(AACScore)
        .where(and_(AACScore.user_id == patient_id, AACScore.calculated_at >= day_start, AACScore.calculated_at <= day_end))
    )
    aac_scores = aac_result.scalars().all()

    # Pull alerts
    alerts_result = await db.execute(
        select(Alert)
        .where(and_(Alert.patient_id == patient_id, Alert.timestamp >= day_start, Alert.timestamp <= day_end))
    )
    alerts = alerts_result.scalars().all()

    # Medication adherence
    med_total_result = await db.execute(
        select(func.count(Reminder.id))
        .where(and_(
            Reminder.user_id == patient_id, Reminder.reminder_type == "medication",
            Reminder.scheduled_time >= day_start, Reminder.scheduled_time <= day_end,
        ))
    )
    med_total = med_total_result.scalar() or 0

    med_confirmed_result = await db.execute(
        select(func.count(Reminder.id))
        .where(and_(
            Reminder.user_id == patient_id, Reminder.reminder_type == "medication",
            Reminder.scheduled_time >= day_start, Reminder.scheduled_time <= day_end,
            Reminder.status == "confirmed",
        ))
    )
    med_confirmed = med_confirmed_result.scalar() or 0
    adherence = (med_confirmed / med_total) if med_total > 0 else 1.0

    avg_aac = int(sum(a.score for a in aac_scores) / len(aac_scores)) if aac_scores else (user.aac_baseline if user else 70)

    # Format for LLM
    events_text = "\n".join([
        f"- {e.timestamp.strftime('%I:%M %p')} | {e.event_type.upper()} ({e.severity}) — {e.description}"
        for e in events
    ]) if events else "Quiet day — no events recorded."

    alerts_text = "\n".join([
        f"- {a.timestamp.strftime('%I:%M %p')} | {a.priority.upper()} — {a.message}"
        for a in alerts
    ]) if alerts else "No alerts."

    caregiver_prompt = """You are SahayAI's Caregiver Agent. Generate a daily summary like a thoughtful nurse doing a handoff — warm but factual. Under 200 words. Use the patient's name."""

    summary_context = f"""
Patient: {user_name}
Conditions: {conditions}
Date: {summary_date}
AAC Score (avg): {avg_aac}/100
Medication: {adherence:.0%} ({med_confirmed}/{med_total})
Alerts: {len(alerts)}

Events:
{events_text}

Alerts:
{alerts_text}

Generate the daily summary now."""

    summary_text = await chat_completion(
        messages=[
            {"role": "system", "content": caregiver_prompt},
            {"role": "user", "content": summary_context},
        ],
        model_preference="quality",
        temperature=0.5,
        max_tokens=400,
    )

    # Cache it
    cached = DailySummary(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        summary_date=summary_date,
        summary_text=summary_text,
        medication_adherence=adherence,
        total_steps=0,
        alerts_count=len(alerts),
        avg_aac_score=avg_aac,
        cct_trend="stable",
        events_json=json.dumps([
            {"time": e.timestamp.strftime("%H:%M"), "type": e.event_type,
             "description": e.description, "severity": e.severity}
            for e in events
        ]),
    )
    db.add(cached)


async def _recalculate_aac_scores():
    """
    Recompute AAC for all active patients every 15 minutes.
    The time-of-day component changes throughout the day (sundowning)
    so even without new events the score should update.
    """
    from api.models.database import async_session
    from api.models.tables import User
    from innovations.aac import compute_aac_score
    from sqlalchemy import select

    try:
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.role == "patient")
            )
            patients = result.scalars().all()

            for patient in patients:
                try:
                    await compute_aac_score(patient.id, db)
                except Exception as e:
                    logger.warning(f"AAC recalc failed for {patient.id}: {e}")

            await db.commit()
            logger.info(f"AAC recalculated for {len(patients)} patients")

    except Exception as e:
        logger.error(f"AAC recalculation failed: {e}")


async def _check_missed_reminders():
    """
    Any medication reminder that's been pending for >30 minutes
    is marked as missed. This triggers an event log and affects
    the AAC routine adherence component.
    """
    import uuid as uuid_lib
    from api.models.database import async_session
    from api.models.tables import Reminder, Event
    from sqlalchemy import select, and_

    try:
        async with async_session() as db:
            cutoff = datetime.utcnow() - timedelta(minutes=30)

            result = await db.execute(
                select(Reminder)
                .where(and_(
                    Reminder.status == "pending",
                    Reminder.scheduled_time <= cutoff,
                ))
            )
            overdue = result.scalars().all()

            for reminder in overdue:
                reminder.status = "missed"

                # Log it as an event so it shows up in the daily summary
                event = Event(
                    id=str(uuid_lib.uuid4()),
                    user_id=reminder.user_id,
                    event_type="medication_missed",
                    severity="medium",
                    description=f"Missed: {reminder.message}",
                    agent_action="Marked as missed after 30 min with no confirmation",
                )
                db.add(event)
                logger.info(f"Reminder {reminder.id} marked as missed for user {reminder.user_id}")

            if overdue:
                await db.commit()
                logger.info(f"Marked {len(overdue)} reminders as missed")

    except Exception as e:
        logger.error(f"Missed reminder check failed: {e}")