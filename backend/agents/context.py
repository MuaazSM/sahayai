import logging
from datetime import datetime

from agents.state import AssistState
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger("sahayai.agent.context")


async def context_agent(state: AssistState, db: AsyncSession = None) -> AssistState:
    """
    Second agent in the pipeline. Pulls everything we know about this
    person from RAG (ChromaDB) and the database (PostgreSQL).

    Also decides if we even need to bother the Reasoning Agent.
    If wearable data is normal, no voice input, no scheduled event —
    why waste an LLM call? Short-circuit and save latency + money.
    """
    logger.info(f"Context Agent running | user={state.get('user_id', 'unknown')}")

    updates: dict = {
        "agents_executed": state.get("agents_executed", []) + ["context"],
    }

    user_id = state.get("user_id", "")

    # ---------------------------------------------------------------
    # 1. Pull user profile from DB — basic info we always need
    # ---------------------------------------------------------------
    if db:
        try:
            from api.models.tables import User, AACScore
            user = await db.get(User, user_id)
            if user:
                updates["user_name"] = user.name
                updates["disability_type"] = user.disability_type or "unknown"
                updates["medical_conditions"] = user.medical_conditions or ""
                updates["home_lat"] = user.home_lat or 19.1136
                updates["home_lng"] = user.home_lng or 72.8697

                # Compute fresh AAC score — pulls from CCT, vitals, routines,
                # and time-of-day. This is what modulates how aggressive
                # the Reasoning Agent is with interventions.
                try:
                    from innovations.aac import compute_aac_score
                    aac_result = await compute_aac_score(user_id, db)
                    updates["aac_score"] = aac_result["score"]
                    logger.info(
                        f"AAC computed: {aac_result['score']}/100 "
                        f"(cct={aac_result['cct_component']:.0f}, "
                        f"vitals={aac_result['vitals_component']:.0f}, "
                        f"routine={aac_result['routine_component']:.0f}, "
                        f"time={aac_result['time_of_day_component']:.0f})"
                    )
                except Exception as e:
                    logger.warning(f"AAC computation failed: {e}, using baseline")
                    updates["aac_score"] = user.aac_baseline
        except Exception as e:
            logger.warning(f"DB lookup failed: {e}")
            updates["user_name"] = state.get("user_name", "there")
            updates["aac_score"] = state.get("aac_score", 70)
    else:
        updates["user_name"] = state.get("user_name", "there")
        updates["aac_score"] = state.get("aac_score", 70)

    # ---------------------------------------------------------------
    # 2. Pull from ChromaDB RAG — profile, routines, events, EMR
    #    Wrapped in try/except because ChromaDB might not be seeded yet
    # ---------------------------------------------------------------
    try:
        from rag.retriever import (
            retrieve_profile, retrieve_routines, retrieve_recent_events,
            retrieve_communication_prefs, retrieve_emr_memories,
        )

        # What time of day is it? Helps us find relevant routines
        hour = datetime.utcnow().hour
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"

        # Profile context — who is this person
        profile_docs = retrieve_profile(user_id)
        profile_text = "\n".join([d["text"] for d in profile_docs]) if profile_docs else ""

        # Routines — what should be happening around now
        routine_docs = retrieve_routines(user_id, time_of_day)
        updates["relevant_routines"] = routine_docs

        # Recent events — what happened recently that might be relevant
        # Use the perception summary as the search query so we find
        # similar past situations (e.g., past wandering episodes)
        event_query = state.get("perception_summary", "recent events")
        event_docs = retrieve_recent_events(user_id, query=event_query, n=5)
        updates["recent_events"] = event_docs

        # Communication prefs — how to talk to this person
        comm_docs = retrieve_communication_prefs(user_id)
        if comm_docs:
            updates["communication_prefs"] = comm_docs[0].get("metadata", {})

        # EMR memory candidates — pre-fetch in case Reasoning triggers EMR
        # We do this here instead of in the Assistance Agent because RAG
        # retrieval is fast (~10ms) and it saves a round trip later
        detected_emotion = state.get("detected_emotion", "calm")
        if detected_emotion in ("confused", "distressed", "agitated"):
            emr_docs = retrieve_emr_memories(user_id, emotion=detected_emotion, n=3)
            updates["emr_candidates"] = emr_docs
            logger.info(f"Pre-fetched {len(emr_docs)} EMR candidates for emotion: {detected_emotion}")

        # Build the formatted profile context string for the LLM
        routines_text = "\n".join([
            f"- {d['text']}" for d in routine_docs
        ]) if routine_docs else "No routines found"

        events_text = "\n".join([
            f"- {d['text']}" for d in event_docs
        ]) if event_docs else "No recent events"

        updates["user_profile_context"] = f"""
Patient: {updates.get('user_name', 'Unknown')}
Disability: {updates.get('disability_type', 'unknown')}
Conditions: {updates.get('medical_conditions', 'unknown')}
AAC Score: {updates.get('aac_score', 70)}/100
Time: {datetime.utcnow().strftime('%I:%M %p')} ({time_of_day})

Profile: {profile_text if profile_text else 'No profile in RAG yet'}

Relevant routines for {time_of_day}:
{routines_text}

Recent events:
{events_text}
"""

    except Exception as e:
        # ChromaDB not ready or not seeded — that's fine for now,
        # we'll just give the LLM less context
        logger.warning(f"RAG retrieval failed: {e}. Continuing with DB-only context.")
        updates["relevant_routines"] = []
        updates["recent_events"] = []
        updates["emr_candidates"] = []
        updates["user_profile_context"] = f"""
Patient: {updates.get('user_name', 'Unknown')}
AAC Score: {updates.get('aac_score', 70)}/100
Time: {datetime.utcnow().strftime('%I:%M %p')}
(RAG not available — limited context)
"""

    # ---------------------------------------------------------------
    # 3. SHORT-CIRCUIT DECISION
    #    If nothing interesting is happening, skip the Reasoning Agent.
    #    This saves an LLM call (~1-2 seconds) on boring wearable pings.
    #
    #    We NEED reasoning when:
    #    - User said something (always process voice input)
    #    - Camera was used (always describe what they see)
    #    - Wearable classified as anything other than normal
    #    - Emotion detected as not calm
    #    - It's a reminder trigger (need to generate the reminder text)
    # ---------------------------------------------------------------
    trigger = state.get("trigger_type", "voice")
    wearable_class = state.get("wearable_classification", "normal")
    emotion = state.get("detected_emotion", "calm")
    has_voice = bool(state.get("user_message"))
    has_camera = bool(state.get("image_base64"))

    needs_reasoning = (
        has_voice or
        has_camera or
        wearable_class != "normal" or
        emotion not in ("calm", "happy") or
        trigger == "reminder"
    )

    updates["needs_reasoning"] = needs_reasoning

    if not needs_reasoning:
        logger.info("Short-circuiting — nothing interesting happening, skipping Reasoning Agent")
    else:
        logger.info(f"Reasoning needed: voice={has_voice}, camera={has_camera}, "
                     f"wearable={wearable_class}, emotion={emotion}, trigger={trigger}")

    logger.info(f"Context Agent done | AAC={updates.get('aac_score', '?')} | "
                f"routines={len(updates.get('relevant_routines', []))} | "
                f"events={len(updates.get('recent_events', []))}")

    return {**state, **updates}