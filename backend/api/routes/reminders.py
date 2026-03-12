"""
Patient reminder endpoints:
  GET  /patient/reminders/{user_id}          — get pending reminders
  POST /patient/reminders/{reminder_id}/confirm — confirm a reminder (voice/tap)
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/patient/reminders/{user_id}")
async def get_reminders(user_id: str):
    # TODO: Muaaz — query PostgreSQL reminders table
    return {"reminders": []}


@router.post("/patient/reminders/{reminder_id}/confirm")
async def confirm_reminder(reminder_id: str, request: dict):
    # TODO: Muaaz — mark reminder as confirmed, trigger Learning Agent
    return {"success": True, "next_reminder": None}