from typing import TypedDict, Optional

# =====================================================
# AssistState — the single object that flows through
# every agent in the LangGraph pipeline.
#
# Think of it like a patient's chart that gets passed
# from nurse to nurse during a shift. Each agent reads
# what it needs, writes its findings, passes it along.
#
# Pipeline: Perception → Context → Reasoning → Assistance/Caregiver → Learning
#
# Every field is Optional because not every pipeline run
# fills every field. A simple voice query won't have
# wearable data. A wearable check won't have a user message.
# Agents check what's present and skip what's not.
# =====================================================


class AssistState(TypedDict, total=False):

    # ---------------------------------------------------------------
    # INPUT — what triggered this pipeline run
    # Set by the API endpoint before the pipeline starts
    # ---------------------------------------------------------------

    # Who is this about and what kind of input triggered the pipeline
    user_id: str
    role: str                          # "patient" or "caregiver"
    trigger_type: str                  # "voice", "camera", "wearable", "reminder", "scheduled"

    # Voice input — user said something
    user_message: str                  # raw text from STT
    conversation_id: str               # links to the conversations table

    # Camera input — user pointed their phone at something
    image_base64: str                  # base64 encoded camera frame
    
    # Wearable input — smartwatch data window
    heart_rate: int
    accel_x: float
    accel_y: float
    accel_z: float
    steps: int
    gps_lat: float
    gps_lng: float
    window_seconds: int

    # ---------------------------------------------------------------
    # PERCEPTION AGENT OUTPUT
    # First agent in the pipeline — turns raw input into structured events
    # ---------------------------------------------------------------

    # What the perception agent figured out from the raw input
    scene_description: str             # from camera analysis
    obstacles: list[dict]              # detected obstacles from camera
    wearable_classification: str       # normal, fall, wandering, distress
    wearable_confidence: float         # how sure the classifier is
    detected_emotion: str              # calm, confused, distressed, agitated, happy
    perception_summary: str            # one-line summary of what happened

    # ---------------------------------------------------------------
    # CONTEXT AGENT OUTPUT
    # Pulls everything we know about this person from RAG + DB
    # ---------------------------------------------------------------

    user_name: str
    disability_type: str
    medical_conditions: str
    home_lat: float
    home_lng: float

    # Current scores that modulate how the system behaves
    aac_score: int                     # 0-100, Adaptive Autonomy Calibration
    current_cct_composite: float       # latest CCT composite score

    # Retrieved from RAG
    relevant_routines: list[dict]      # today's routines that matter right now
    recent_events: list[dict]          # last few events for context
    user_profile_context: str          # formatted profile string for the LLM
    communication_prefs: dict          # preferred tone, sentence length, etc.

    # EMR memories — pre-fetched in case reasoning decides to trigger EMR
    emr_candidates: list[dict]         # emotion-tagged memories from ChromaDB

    # Short-circuit flag — Context agent can decide no LLM call is needed
    # e.g., normal wearable reading with nothing going on = skip Reasoning
    needs_reasoning: bool

    # ---------------------------------------------------------------
    # REASONING AGENT OUTPUT
    # The brain — decides risk level, what to do, who to notify
    # ---------------------------------------------------------------

    request_type: str                  # question, help, emergency, chat, confusion, distress
    risk_level: str                    # none, low, medium, high, critical
    alert_caregiver: bool              # should we ping the caregiver?
    alert_priority: str                # routine, attention, urgent, emergency
    alert_message: str                 # what to tell the caregiver
    trigger_emr: bool                  # should we surface a personal memory?
    reasoning_text: str                # the agent's explanation of its decision
    suggested_response_direction: str  # rough idea of what to tell the user

    # ---------------------------------------------------------------
    # ASSISTANCE AGENT OUTPUT (user-facing)
    # What we actually say to the person — warm, short, TTS-ready
    # ---------------------------------------------------------------

    response_text: str                 # the final response the user hears
    emr_memory_used: dict | None       # which memory was surfaced, if any
    guidance_text: str                 # navigation/safety guidance if applicable

    # CCT scoring — happens silently during assistance
    cct_scores: dict                   # the 6 dimension scores from this interaction
    cct_composite: float               # weighted average

    # ---------------------------------------------------------------
    # CAREGIVER AGENT OUTPUT
    # Runs in parallel with Assistance when alert_caregiver is True
    # ---------------------------------------------------------------

    caregiver_alert_payload: dict      # full alert object for WebSocket push
    caregiver_summary: str             # if this was a summary request
    cbd_score: float                   # current caregiver burnout score
    cbd_intervention: str | None       # suggestion if burnout detected

    # ---------------------------------------------------------------
    # LEARNING AGENT OUTPUT
    # Updates RAG, adjusts baselines, logs outcomes
    # ---------------------------------------------------------------

    rag_updates: list[dict]            # what was written back to ChromaDB
    aac_adjustment: int                # how much AAC baseline shifted
    learning_notes: str                # what the learning agent observed

    # ---------------------------------------------------------------
    # PIPELINE METADATA
    # Tracking what happened during this run for debugging and logs
    # ---------------------------------------------------------------

    pipeline_started_at: str           # ISO timestamp
    pipeline_completed_at: str         # ISO timestamp
    agents_executed: list[str]         # which agents actually ran
    errors: list[str]                  # any non-fatal errors during the run
    llm_calls_made: int                # how many LLM API calls this run used
    total_latency_ms: int              # end-to-end time in milliseconds