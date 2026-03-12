"""
POST /conversation — Free-form chat endpoint. Handles both patient and
caregiver messages. Routes through the full LangGraph agent pipeline:
Perception → Context → Reasoning → Assistance/Caregiver → Learning.
CCT scoring happens silently on every patient message.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/conversation")
async def conversation(request: dict):
    # TODO: Muaaz — wire up full agent pipeline
    return {
        "response_text": "Good morning, Ramesh! It's a beautiful day. Your morning medication is due in 30 minutes.",
        "conversation_id": "demo-convo-001",
        "cct_score": 0.78,
        "aac_score": 82,
        "emr_triggered": False,
        "emr_memory": None,
    }