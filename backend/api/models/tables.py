import uuid
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models.database import Base


# ---------------------------------------------------------------------------
# Helper to generate UUID primary keys as strings
# We use string UUIDs everywhere because Flutter/Dart handles them easily
# and it keeps things simple across the whole stack
# ---------------------------------------------------------------------------
def new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# USERS — both patients and caregivers live in the same table.
# The role field tells us which one they are. This keeps auth simple
# and lets us handle edge cases (someone who's both) without a second table.
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # "patient" or "caregiver"

    # Disability info — only relevant for patients, NULL for caregivers
    disability_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # visual, mobility, cognitive, hearing
    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)  # free text, comma-separated

    # Location — home address for geofencing (wandering detection)
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # AAC baseline — the Learning Agent adjusts this over time
    # Starts at 70 for new patients (moderate confidence)
    aac_baseline: Mapped[int] = mapped_column(Integer, default=70)

    # CBD — caregiver burnout score. Only tracked for caregivers.
    # 0 = fresh and fine, 100 = completely burnt out
    cbd_score: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    routines: Mapped[list["Routine"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# CAREGIVER LINKS — maps which caregiver watches which patient.
# A caregiver can watch multiple patients (nurse at a care facility)
# and a patient can have multiple caregivers (daughter + night nurse).
# The is_primary flag controls who gets emergency alerts first.
# ---------------------------------------------------------------------------
class CaregiverLink(Base):
    __tablename__ = "caregiver_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    caregiver_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    relationship_label: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "daughter", "nurse", "spouse"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# ROUTINES — learned daily patterns for a patient.
# The Learning Agent updates these as it observes the patient's behavior.
# Used by Context Agent to know "it's 8 AM, Ramesh usually takes meds now"
# ---------------------------------------------------------------------------
class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    routine_type: Mapped[str] = mapped_column(String(50))  # medication, walk, meal, sleep, etc.
    scheduled_time: Mapped[str] = mapped_column(String(10))  # "08:00" — HH:MM format
    description: Mapped[str] = mapped_column(Text)  # "Take blood pressure medication with water"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    days_of_week: Mapped[str] = mapped_column(String(50), default="mon,tue,wed,thu,fri,sat,sun")  # which days this applies

    # The agent tracks how often the patient actually follows this routine
    # to adapt reminders — if adherence is low, remind earlier and more firmly
    adherence_rate: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="routines")


# ---------------------------------------------------------------------------
# EVENTS — everything that happens gets logged here. Falls, wandering
# episodes, medication confirmations, conversations, camera uses, alerts.
# This is the main audit trail and also feeds the Learning Agent.
# The Caregiver Agent queries this to generate daily summaries.
# ---------------------------------------------------------------------------
class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    event_type: Mapped[str] = mapped_column(String(50))
    # Types: "fall", "wandering", "distress", "medication_taken", "medication_missed",
    #        "camera_use", "conversation", "reminder_confirmed", "geofence_breach",
    #        "emr_triggered", "vitals_anomaly"

    severity: Mapped[str] = mapped_column(String(20), default="info")  # info, low, medium, high, critical
    description: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # extra context as JSON string

    # Where it happened — useful for wandering events and the caregiver map view
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # What the agent decided to do about it — logged for transparency
    agent_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# ALERTS — generated by the Reasoning/Caregiver Agent when something needs
# a caregiver's attention. Pushed via WebSocket in real time, also stored
# here so the caregiver can scroll back through history.
# Priority levels determine how aggressively we notify:
#   routine   → silent, shows in feed
#   attention → badge notification
#   urgent    → sound + vibration
#   emergency → repeated alerts until acknowledged
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    caregiver_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    priority: Mapped[str] = mapped_column(String(20))  # routine, attention, urgent, emergency
    message: Mapped[str] = mapped_column(Text)  # human-readable alert text
    context: Mapped[str] = mapped_column(Text)  # WHY this alert was generated
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # the agent's reasoning chain

    # Links back to the event that triggered this alert
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.id"), nullable=True)

    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledge_action: Mapped[str | None] = mapped_column(String(20), nullable=True)  # acknowledge, dismiss, escalate
    acknowledge_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# DAILY SUMMARIES — the Caregiver Agent generates one of these at end of day
# (or on-demand when caregiver asks "how was dad's day?"). Stores both the
# natural language summary and structured metrics so the frontend can render
# charts and cards without re-parsing the text.
# ---------------------------------------------------------------------------
class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    summary_date: Mapped[date] = mapped_column(Date)
    summary_text: Mapped[str] = mapped_column(Text)  # the AI-generated natural language summary

    # Structured metrics — pulled from events table and CCT/AAC scores
    medication_adherence: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_aac_score: Mapped[int] = mapped_column(Integer, default=70)
    cct_trend: Mapped[str] = mapped_column(String(20), default="stable")  # stable, improving, declining

    # All events for this day as a JSON array — so the frontend can show a timeline
    events_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# CONVERSATIONS — groups messages into sessions. When a user starts talking,
# we create a conversation. If they come back within 30 min, we reuse it.
# The CCT and AAC scores on the conversation are the latest values at the
# time of the last message — gives us a per-session snapshot.
# ---------------------------------------------------------------------------
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))  # patient or caregiver

    # Latest scores at end of conversation — quick lookup without scanning messages
    latest_cct_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_aac_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emr_was_triggered: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# CONVERSATION MESSAGES — individual turns in a conversation.
# We store both user and AI messages so we can replay context into the LLM
# and also so CCT can analyze the full conversation history for scoring.
# ---------------------------------------------------------------------------
class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    sender: Mapped[str] = mapped_column(String(20))  # "user" or "ai"
    content: Mapped[str] = mapped_column(Text)

    # CCT scores this message (only for user messages from patients)
    cct_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# REMINDERS — scheduled prompts for the patient. Created from routines
# each morning by a background task, or manually by caregiver.
# Status flow: pending → confirmed (patient did it) or missed (no response)
# ---------------------------------------------------------------------------
class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    reminder_type: Mapped[str] = mapped_column(String(30))  # medication, routine, appointment
    scheduled_time: Mapped[datetime] = mapped_column(DateTime)
    message: Mapped[str] = mapped_column(Text)  # "Time to take your blood pressure medication"
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, confirmed, missed
    confirmation_method: Mapped[str | None] = mapped_column(String(10), nullable=True)  # voice or tap

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reminders")


# ---------------------------------------------------------------------------
# CCT SCORES — time-series of cognitive scores. One row per scoring event.
# The CCT module writes here after every patient conversation.
# Frontend pulls this for the cognitive trend chart on the caregiver dashboard.
# ---------------------------------------------------------------------------
class CCTScore(Base):
    __tablename__ = "cct_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=True)

    # The 6 cognitive dimensions — each scored 0.0 to 1.0
    recall_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    response_latency: Mapped[float] = mapped_column(Float, default=0.0)
    vocabulary_richness: Mapped[float] = mapped_column(Float, default=0.0)
    temporal_orientation: Mapped[float] = mapped_column(Float, default=0.0)
    narrative_coherence: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_consistency: Mapped[float] = mapped_column(Float, default=0.0)

    # Composite score — weighted average of all 6 dimensions
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)

    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# AAC SCORES — snapshot of the Adaptive Autonomy Calibration score over time.
# Recalculated every 15 minutes by the AAC module. The Reasoning Agent reads
# the latest one to decide how much to intervene. Stored as time-series so
# we can show "confidence throughout the day" on the caregiver dashboard.
# ---------------------------------------------------------------------------
class AACScore(Base):
    __tablename__ = "aac_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    score: Mapped[int] = mapped_column(Integer)  # 0-100

    # What contributed to this score — helps debug and explain to caregivers
    cct_component: Mapped[float] = mapped_column(Float, default=0.0)
    vitals_component: Mapped[float] = mapped_column(Float, default=0.0)
    routine_component: Mapped[float] = mapped_column(Float, default=0.0)
    time_of_day_component: Mapped[float] = mapped_column(Float, default=0.0)

    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)