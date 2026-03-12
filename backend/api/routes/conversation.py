import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import ConversationRequest, ConversationResponse, EMRMemory
from api.models.database import get_db
from api.models.tables import User, Conversation, ConversationMessage, CCTScore
from agents.pipeline import run_pipeline

router = APIRouter()
logger = logging.getLogger("sahayai.conversation")


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest, db: AsyncSession = Depends(get_db)):
    """
    Freeform chat for both patients and caregivers.
    Now routes through the full agent pipeline instead of doing
    everything inline. The pipeline handles:
    Perception → Context → Reasoning → Assistance/Caregiver → Learning
    """
    logger.info(f"Conversation from {request.role} user={request.user_id}: {request.message[:80]}...")

    # Get or create conversation session
    conversation_id = request.conversation_id or str(uuid.uuid4())
    if not request.conversation_id:
        new_convo = Conversation(
            id=conversation_id,
            user_id=request.user_id,
            role=request.role,
        )
        db.add(new_convo)

    # Save user's message
    user_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sender="user",
        content=request.message,
    )
    db.add(user_msg)

    # ---------------------------------------------------------------
    # Run the full agent pipeline
    # This is where all the magic happens — perception, context,
    # reasoning, assistance, caregiver alerts, CCT, EMR, everything
    # ---------------------------------------------------------------
    pipeline_state = await run_pipeline(
        initial_state={
            "user_id": request.user_id,
            "role": request.role,
            "trigger_type": "voice",
            "user_message": request.message,
            "conversation_id": conversation_id,
        },
        db=db,
    )

    # Save AI's response
    response_text = pipeline_state.get("response_text", "I'm here if you need me.")
    ai_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sender="ai",
        content=response_text,
    )
    db.add(ai_msg)

    # Save CCT scores if they were generated
    cct_composite = pipeline_state.get("cct_composite")
    cct_scores = pipeline_state.get("cct_scores", {})
    if cct_composite and request.role == "patient":
        try:
            cct_entry = CCTScore(
                id=str(uuid.uuid4()),
                user_id=request.user_id,
                conversation_id=conversation_id,
                recall_accuracy=cct_scores.get("recall_accuracy", 0.0),
                response_latency=cct_scores.get("response_latency", 0.0),
                vocabulary_richness=cct_scores.get("vocabulary_richness", 0.0),
                temporal_orientation=cct_scores.get("temporal_orientation", 0.0),
                narrative_coherence=cct_scores.get("narrative_coherence", 0.0),
                semantic_consistency=cct_scores.get("semantic_consistency", 0.0),
                composite_score=cct_composite,
            )
            db.add(cct_entry)
        except Exception as e:
            logger.warning(f"Failed to save CCT score: {e}")

    # Update conversation metadata
    try:
        convo = await db.get(Conversation, conversation_id)
        if convo:
            convo.latest_cct_score = cct_composite
            convo.latest_aac_score = pipeline_state.get("aac_score")
            convo.emr_was_triggered = pipeline_state.get("trigger_emr", False)
            convo.last_message_at = datetime.utcnow()
    except Exception:
        pass

    # Push WebSocket alert if caregiver was flagged
    if pipeline_state.get("alert_caregiver") and pipeline_state.get("caregiver_alert_payload"):
        try:
            from api.routes.websocket import broadcast_alert
            from sqlalchemy import select
            from api.models.tables import CaregiverLink

            cg_result = await db.execute(
                select(CaregiverLink)
                .where(CaregiverLink.patient_id == request.user_id)
                .where(CaregiverLink.is_primary == True)
                .limit(1)
            )
            cg_link = cg_result.scalar_one_or_none()
            if cg_link:
                await broadcast_alert(
                    cg_link.caregiver_id,
                    pipeline_state["caregiver_alert_payload"],
                )
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed: {e}")

    # Build response
    emr_memory = None
    if pipeline_state.get("trigger_emr") and pipeline_state.get("emr_memory_used"):
        mem = pipeline_state["emr_memory_used"]
        emr_memory = EMRMemory(
            text=mem.get("text", "A warm memory."),
            emotion_tag=mem.get("metadata", {}).get("emotion", "comfort"),
        )

    return ConversationResponse(
        response_text=response_text,
        conversation_id=conversation_id,
        cct_score=cct_composite,
        aac_score=pipeline_state.get("aac_score"),
        emr_triggered=pipeline_state.get("trigger_emr", False),
        emr_memory=emr_memory,
    )