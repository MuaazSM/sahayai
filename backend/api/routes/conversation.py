import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.models.schemas import ConversationRequest, ConversationResponse, EMRMemory
from api.models.database import get_db
from api.models.tables import (
    User, Conversation, ConversationMessage, Event, CCTScore, AACScore
)
from utils.llm import chat_completion

router = APIRouter()
logger = logging.getLogger("sahayai.conversation")

# Load prompts once at startup so we're not reading files on every request
with open("prompts/reasoning_agent.txt", "r") as f:
    REASONING_PROMPT = f.read()

with open("prompts/assistance_agent.txt", "r") as f:
    ASSISTANCE_PROMPT = f.read()


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest, db: AsyncSession = Depends(get_db)):
    """
    The main chat endpoint. Handles both patient and caregiver messages.
    For patients: runs through Reasoning → Assistance pipeline, scores CCT silently.
    For caregivers: routes to caregiver-style response (summaries, questions about patient).
    """
    logger.info(f"Conversation from {request.role} user={request.user_id}: {request.message[:80]}...")

    # ---------------------------------------------------------------
    # 1. Get or create a conversation session
    #    If they sent a conversation_id, continue that session.
    #    Otherwise start a new one.
    # ---------------------------------------------------------------
    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        new_convo = Conversation(
            id=conversation_id,
            user_id=request.user_id,
            role=request.role,
        )
        db.add(new_convo)
        logger.info(f"New conversation created: {conversation_id}")

    # ---------------------------------------------------------------
    # 2. Save the user's message to the DB
    #    We store every message so CCT can analyze the full history
    #    and so we can replay context into the LLM
    # ---------------------------------------------------------------
    user_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sender="user",
        content=request.message,
    )
    db.add(user_msg)

    # ---------------------------------------------------------------
    # 3. Load context — user profile, recent messages, latest AAC score
    #    This is what makes the AI feel "aware" of who it's talking to
    # ---------------------------------------------------------------
    user = await db.get(User, request.user_id)
    user_name = user.name if user else "there"
    disability = user.disability_type if user else "unknown"
    aac_baseline = user.aac_baseline if user else 70

    # Grab the latest AAC score if one exists, otherwise use baseline
    latest_aac_result = await db.execute(
        select(AACScore)
        .where(AACScore.user_id == request.user_id)
        .order_by(AACScore.calculated_at.desc())
        .limit(1)
    )
    latest_aac = latest_aac_result.scalar_one_or_none()
    current_aac = latest_aac.score if latest_aac else aac_baseline

    # Pull recent messages from this conversation for context
    # We send the last 10 messages so the LLM has short-term memory
    recent_msgs_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.timestamp.desc())
        .limit(10)
    )
    recent_msgs = recent_msgs_result.scalars().all()
    recent_msgs.reverse()  # oldest first for the LLM

    # ---------------------------------------------------------------
    # 4. REASONING AGENT — decides risk level, whether to alert
    #    caregiver, whether to trigger EMR, and drafts the approach
    #    Uses the "quality" model (llama-3.3-70b) for good judgment
    # ---------------------------------------------------------------
    context_block = f"""
User Profile:
- Name: {user_name}
- Disability: {disability}
- Current AAC Score: {current_aac}/100
- Time now: {datetime.utcnow().strftime("%I:%M %p")}

Recent conversation:
{_format_messages_for_llm(recent_msgs)}

New message from user: "{request.message}"
"""

    reasoning_messages = [
        {"role": "system", "content": REASONING_PROMPT},
        {"role": "user", "content": context_block},
    ]

    reasoning_raw = await chat_completion(
        messages=reasoning_messages,
        model_preference="quality",  # llama-3.3-70b — good judgment matters here
        temperature=0.2,
        max_tokens=512,
    )

    # Parse the reasoning agent's JSON response
    reasoning = _parse_reasoning(reasoning_raw)

    # ---------------------------------------------------------------
    # 5. ASSISTANCE AGENT — generates the actual user-facing response
    #    Uses the "fast" model (llama-3.1-8b) for low latency since
    #    this is what the user hears through TTS
    # ---------------------------------------------------------------
    assistance_context = f"""
You are talking to {user_name}. Their AAC score is {current_aac}/100.
Situation assessment: {reasoning.get('request_type', 'chat')}, risk: {reasoning.get('risk_level', 'none')}.

{"EMR MEMORY TRIGGERED — weave this memory in naturally: " + reasoning.get("emr_memory_text", "") if reasoning.get("trigger_emr") else ""}

Reasoning agent's suggested response direction: {reasoning.get('response_text', '')}

Recent conversation:
{_format_messages_for_llm(recent_msgs)}

User just said: "{request.message}"

Respond to the user now. Remember: warm, short, spoken aloud via TTS.
"""

    assistance_messages = [
        {"role": "system", "content": ASSISTANCE_PROMPT},
        {"role": "user", "content": assistance_context},
    ]

    response_text = await chat_completion(
        messages=assistance_messages,
        model_preference="fast",  # llama-3.1-8b — speed matters for voice
        temperature=0.5,
        max_tokens=150,  # keep it short for TTS
    )

    # ---------------------------------------------------------------
    # 6. CCT SCORING — silently score cognitive dimensions from the
    #    user's message. Only for patient messages, not caregiver.
    #    Uses "structured" model (qwen3-32b) for reliable JSON output.
    # ---------------------------------------------------------------
    cct_score = None
    if request.role == "patient":
        cct_score = await _score_cct(
            user_message=request.message,
            conversation_history=_format_messages_for_llm(recent_msgs),
            user_id=request.user_id,
            conversation_id=conversation_id,
            db=db,
        )

    # ---------------------------------------------------------------
    # 7. Save the AI's response to the DB
    # ---------------------------------------------------------------
    ai_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sender="ai",
        content=response_text,
    )
    db.add(ai_msg)

    # Update conversation's latest scores
    try:
        convo = await db.get(Conversation, conversation_id)
        if convo:
            convo.latest_cct_score = cct_score
            convo.latest_aac_score = current_aac
            convo.emr_was_triggered = reasoning.get("trigger_emr", False)
            convo.last_message_at = datetime.utcnow()
    except Exception:
        pass  # don't let metadata updates break the response

    # ---------------------------------------------------------------
    # 8. If reasoning said to alert caregiver, log the event + alert
    #    (the actual WebSocket push happens in the caregiver agent,
    #    for now we just store it in the events table)
    # ---------------------------------------------------------------
    if reasoning.get("alert_caregiver"):
        event = Event(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            event_type=reasoning.get("request_type", "conversation"),
            severity=reasoning.get("risk_level", "low"),
            description=f"Conversation triggered alert: {reasoning.get('alert_message', '')}",
            agent_action=f"Alert sent to caregiver. Priority: {reasoning.get('alert_priority', 'attention')}",
        )
        db.add(event)

    # ---------------------------------------------------------------
    # 9. Build and return the response matching our data contract
    # ---------------------------------------------------------------
    emr_memory = None
    if reasoning.get("trigger_emr"):
        emr_memory = EMRMemory(
            text=reasoning.get("emr_memory_text", "A warm memory from your life."),
            emotion_tag=reasoning.get("request_type", "comfort"),
        )

    return ConversationResponse(
        response_text=response_text,
        conversation_id=conversation_id,
        cct_score=cct_score,
        aac_score=current_aac,
        emr_triggered=reasoning.get("trigger_emr", False),
        emr_memory=emr_memory,
    )


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def _format_messages_for_llm(messages: list[ConversationMessage]) -> str:
    """Turn DB message rows into a simple text block the LLM can read"""
    if not messages:
        return "(no prior messages)"
    lines = []
    for msg in messages:
        speaker = "User" if msg.sender == "user" else "SahayAI"
        lines.append(f"{speaker}: {msg.content}")
    return "\n".join(lines)


def _parse_reasoning(raw: str) -> dict:
    """
    Parse the reasoning agent's JSON. If it's garbage, return safe defaults
    so the pipeline doesn't crash — we'd rather give a generic friendly
    response than blow up on the user.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Reasoning agent returned non-JSON: {raw[:200]}")
        return {
            "request_type": "chat",
            "risk_level": "none",
            "alert_caregiver": False,
            "alert_priority": "routine",
            "alert_message": None,
            "trigger_emr": False,
            "response_text": "I'm here to help.",
            "reasoning": "Fallback — couldn't parse reasoning output",
        }


async def _score_cct(
    user_message: str,
    conversation_history: str,
    user_id: str,
    conversation_id: str,
    db: AsyncSession,
) -> float | None:
    """
    CCT — Conversational Cognitive Tracking
    Silently scores 6 cognitive dimensions from the user's message.
    Runs in the background conceptually — the user never sees this.
    Returns the composite score (0.0 to 1.0).
    """
    cct_prompt = """Score this patient's cognitive state from their message on 6 dimensions (each 0.0 to 1.0):
- recall_accuracy: Can they remember recent things correctly?
- response_latency: Is their response appropriately timed/paced? (inferred from text coherence)
- vocabulary_richness: Are they using varied, appropriate words?
- temporal_orientation: Do they know what time/day it is?
- narrative_coherence: Does their message make logical sense?
- semantic_consistency: Is it consistent with what they said before?

Conversation so far:
{history}

Latest message: "{message}"

Respond with ONLY this JSON:
{{"recall_accuracy": 0.0, "response_latency": 0.0, "vocabulary_richness": 0.0, "temporal_orientation": 0.0, "narrative_coherence": 0.0, "semantic_consistency": 0.0, "composite": 0.0}}

The composite should be the average of all 6 scores.
""".format(history=conversation_history, message=user_message)

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": cct_prompt}],
            model_preference="structured",  # qwen3-32b — good at JSON
            temperature=0.1,
            max_tokens=256,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        scores = json.loads(cleaned)

        # Save to DB so the caregiver dashboard can show trends
        cct_entry = CCTScore(
            id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=conversation_id,
            recall_accuracy=scores.get("recall_accuracy", 0.0),
            response_latency=scores.get("response_latency", 0.0),
            vocabulary_richness=scores.get("vocabulary_richness", 0.0),
            temporal_orientation=scores.get("temporal_orientation", 0.0),
            narrative_coherence=scores.get("narrative_coherence", 0.0),
            semantic_consistency=scores.get("semantic_consistency", 0.0),
            composite_score=scores.get("composite", 0.0),
        )
        db.add(cct_entry)

        logger.info(f"CCT scored: composite={scores.get('composite', 0.0):.2f}")
        return scores.get("composite", 0.0)

    except Exception as e:
        # CCT failing should never break the conversation
        logger.warning(f"CCT scoring failed: {e}")
        return None