"""
Patient reminder endpoints:
  GET  /patient/reminders/{user_id}          — get pending reminders
  POST /patient/reminders/{reminder_id}/confirm — confirm a reminder (voice/tap)
"""

import uuid
import logging
from datetime import datetime

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.models.database import get_db
from api.models.tables import Reminder, Event
from api.models.schemas import (
    ReminderItem,
    RemindersResponse,
    ConfirmReminderRequest,
    ConfirmReminderResponse,
)

router = APIRouter()
logger = logging.getLogger("sahayai.reminders")


@router.get("/patient/reminders/{user_id}", response_model=list[ReminderItem])
async def get_reminders(user_id: str, db: AsyncSession = Depends(get_db)):
    """Return pending and recent reminders for the patient."""
    try:
        result = await db.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .where(Reminder.status == "pending")
            .order_by(Reminder.scheduled_time.asc())
            .limit(20)
        )
        reminders = result.scalars().all()

        return [
            ReminderItem(
                id=r.id,
                user_id=r.user_id,
                title=r.message,
                description="",
                reminder_type=r.reminder_type.upper(),
                scheduled_time=r.scheduled_time.isoformat(),
                is_confirmed=(r.status == "confirmed"),
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in reminders
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch reminders for {user_id}: {e}")
        return []


@router.post("/patient/reminders/{reminder_id}/confirm", response_model=ConfirmReminderResponse)
async def confirm_reminder(
    reminder_id: str,
    request: Optional[ConfirmReminderRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark a reminder as confirmed and log the event for the Learning Agent."""
    confirmation_method = request.confirmation_method if request else "tap"
    try:
        reminder = await db.get(Reminder, reminder_id)
        if not reminder:
            return ConfirmReminderResponse(success=False, next_reminder=None)

        # Update reminder status
        reminder.status = "confirmed"
        reminder.confirmation_method = confirmation_method
        reminder.confirmed_at = datetime.utcnow()

        # Log to events table so Learning Agent can track adherence
        event = Event(
            id=str(uuid.uuid4()),
            user_id=reminder.user_id,
            event_type="reminder_confirmed",
            severity="info",
            description=f"Reminder confirmed via {confirmation_method}: {reminder.message}",
        )
        db.add(event)

        await db.commit()

        # Look for the next pending reminder
        next_result = await db.execute(
            select(Reminder)
            .where(Reminder.user_id == reminder.user_id)
            .where(Reminder.status == "pending")
            .order_by(Reminder.scheduled_time.asc())
            .limit(1)
        )
        next_reminder = next_result.scalar_one_or_none()

        next_dict = None
        if next_reminder:
            next_dict = {
                "id": next_reminder.id,
                "user_id": next_reminder.user_id,
                "title": next_reminder.message,
                "description": "",
                "reminder_type": next_reminder.reminder_type.upper(),
                "scheduled_time": next_reminder.scheduled_time.isoformat(),
                "is_confirmed": (next_reminder.status == "confirmed"),
                "created_at": next_reminder.created_at.isoformat() if next_reminder.created_at else "",
            }

        return ConfirmReminderResponse(success=True, next_reminder=next_dict)

    except Exception as e:
        logger.error(f"Failed to confirm reminder {reminder_id}: {e}", exc_info=True)
        return ConfirmReminderResponse(success=False, next_reminder=None)
