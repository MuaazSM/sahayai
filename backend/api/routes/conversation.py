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
    try:
        logger.info(f"Conversation from {request.role} user={request.user_id}: {request.message[:80]}...")

        # Validate input
        if not request.message or not request.message.strip():
            return ConversationResponse(
                response_text="I didn't catch that. Could you say that again?",
                conversation_id=request.conversation_id or str(uuid.uuid4()),
                cct_score=None,
                aac_score=None,
                emr_triggered=False,
                emr_memory=None,
            )

        # Get or create conversation session
        conversation_id = request.conversation_id or str(uuid.uuid4())
        try:
            if not request.conversation_id:
                new_convo = Conversation(
                    id=conversation_id,
                    user_id=request.user_id,
                    role=request.role,
                )
                db.add(new_convo)

            user_msg = ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                sender="user",
                content=request.message,
            )
            db.add(user_msg)
        except Exception as e:
            # DB write failed but we can still process the conversation
            logger.warning(f"DB write failed for conversation: {e}")

        # Run the full agent pipeline
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

        response_text = pipeline_state.get("response_text", "I'm here if you need me.")

        # Save AI response to DB
        try:
            ai_msg = ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                sender="ai",
                content=response_text,
            )
            db.add(ai_msg)
        except Exception as e:
            logger.warning(f"Failed to save AI message: {e}")

        # Save CCT scores
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

        # Push WebSocket alert if needed
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
            try:
                mem = pipeline_state["emr_memory_used"]
                emr_memory = EMRMemory(
                    text=mem.get("text", "A warm memory."),
                    emotion_tag=mem.get("metadata", {}).get("emotion", "comfort"),
                )
            except Exception:
                pass

        # Generate human-like voice audio for the response
        # This runs async so it doesn't block — if ElevenLabs is slow
        # or unavailable, Flutter falls back to local TTS
        audio_base64 = None
        audio_provider = None
        try:
            from utils.tts import text_to_speech
            tts_result = await text_to_speech(text=response_text)
            audio_base64 = tts_result.get("audio_base64")
            audio_provider = tts_result.get("provider")
        except Exception as e:
            logger.warning(f"TTS failed: {e}")

        return ConversationResponse(
            response_text=response_text,
            conversation_id=conversation_id,
            cct_score=cct_composite,
            aac_score=pipeline_state.get("aac_score"),
            emr_triggered=pipeline_state.get("trigger_emr", False),
            emr_memory=emr_memory,
            audio_base64=audio_base64,
            audio_provider=audio_provider,
        )

    except Exception as e:
        # Total pipeline failure — still give the user a warm response
        # Never leave them staring at an error screen
        logger.error(f"Conversation endpoint failed: {e}", exc_info=True)
        return ConversationResponse(
            response_text="I'm having a little trouble right now, but I'm still here with you. Could you try saying that again?",
            conversation_id=request.conversation_id or str(uuid.uuid4()),
            cct_score=None,
            aac_score=None,
            emr_triggered=False,
            emr_memory=None,
        )