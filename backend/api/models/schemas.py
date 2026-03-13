from pydantic import BaseModel
from typing import Optional


# =====================================================
# /analyze-scene
# =====================================================

class Location(BaseModel):
    lat: float
    lng: float

class SceneRequest(BaseModel):
    image: str  # base64 encoded image from Flutter camera
    location: Location
    user_id: str

class Obstacle(BaseModel):
    type: str
    distance: str
    direction: str

class SceneResponse(BaseModel):
    scene_description: str
    obstacles: list[Obstacle]
    guidance_text: str
    risk_level: str  # none, low, medium, high


# =====================================================
# /conversation
# =====================================================

class ConversationRequest(BaseModel):
    user_id: str
    role: str  # patient or caregiver
    message: str
    conversation_id: Optional[str] = None


class EMRMemory(BaseModel):
    text: str
    emotion_tag: str

class ConversationResponse(BaseModel):
    response_text: str
    conversation_id: str
    cct_score: Optional[float] = None
    aac_score: Optional[int] = None
    emr_triggered: bool = False
    emr_memory: Optional[EMRMemory] = None
    # TTS audio — if ElevenLabs is available, this contains base64 audio
    # Flutter plays this directly instead of using robotic local TTS
    audio_base64: Optional[str] = None
    audio_provider: Optional[str] = None

# =====================================================
# /check-status
# =====================================================

class Accelerometer(BaseModel):
    x: float
    y: float
    z: float

class GPS(BaseModel):
    lat: float
    lng: float

class WearableData(BaseModel):
    heart_rate: int
    accelerometer: Accelerometer
    steps: int
    gps: GPS

class StatusRequest(BaseModel):
    user_id: str
    wearable_data: WearableData
    window_seconds: int

class CaregiverAlertPayload(BaseModel):
    priority: str
    message: str
    context: str

class StatusResponse(BaseModel):
    classification: str  # normal, fall, wandering, distress
    confidence: float
    risk_level: str  # none, low, medium, high, critical
    user_message: Optional[str] = None
    caregiver_alert: Optional[CaregiverAlertPayload] = None


# =====================================================
# /caregiver/alerts
# =====================================================

class AlertItem(BaseModel):
    """Matches Android Alert data class (Alert.kt)"""
    id: str
    patient_id: str
    alert_type: str     # e.g. "fall", "medication", "wandering", "cognitive"
    priority: str       # routine, attention, urgent, emergency
    title: str
    description: str
    created_at: str     # ISO timestamp — Android @SerialName("created_at")
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None

class AlertsResponse(BaseModel):
    """Kept for internal use — Android reads the list directly."""
    alerts: list[AlertItem]

class AcknowledgeRequest(BaseModel):
    action: str  # acknowledge, dismiss, escalate
    note: Optional[str] = None

class AcknowledgeResponse(BaseModel):
    success: bool
    updated_alert: dict


# =====================================================
# /caregiver/summary
# =====================================================

class SummaryMetrics(BaseModel):
    medication_adherence: float
    steps: int
    alerts_count: int
    avg_aac_score: int
    cct_trend: str  # stable, improving, declining

class SummaryEvent(BaseModel):
    time: str
    type: str
    description: str
    severity: str

class CCTScorePoint(BaseModel):
    date: str
    score: float

class SummaryResponse(BaseModel):
    """Legacy — kept for internal cache. Android uses CaregiverSummaryResponse."""
    summary_text: str
    date: str
    metrics: SummaryMetrics
    events: list[SummaryEvent]
    cct_scores: list[CCTScorePoint]


class CaregiverSummaryResponse(BaseModel):
    """Flat schema matching Android CaregiverSummary data class."""
    patient_id: str
    date: str
    steps_today: int = 0
    reminders_completed: int = 0
    reminders_total: int = 0
    avg_cct_score: float = 0.0
    risk_level: str = "LOW"        # LOW / MEDIUM / HIGH / CRITICAL
    aac_score: float = 75.0
    conversations_today: int = 0
    mood_summary: str = ""
    # Extra fields surfaced on caregiver dashboard (harmless for Android, ignored via @SerialName)
    medication_adherence: float = 1.0
    alerts_count: int = 0
    cct_trend: str = "stable"      # stable, improving, declining


class CognitiveTrendPoint(BaseModel):
    """Matches Android CognitiveTrendPoint data class."""
    date: str
    cct_score: float
    aac_score: Optional[float] = None
    conversation_count: int = 0


# =====================================================
# /patient/reminders
# =====================================================

class ReminderItem(BaseModel):
    id: str
    type: str  # medication, routine, appointment
    scheduled_time: str
    message: str
    status: str  # pending, confirmed, missed

class RemindersResponse(BaseModel):
    reminders: list[ReminderItem]

class ConfirmReminderRequest(BaseModel):
    confirmation_method: str  # voice or tap

class ConfirmReminderResponse(BaseModel):
    success: bool
    next_reminder: Optional[dict] = None


# =====================================================
# WebSocket alert message
# =====================================================

class WSAlertMessage(BaseModel):
    alert_type: str
    priority: str  # routine, attention, urgent, emergency
    message: str
    patient_id: str
    timestamp: str
    event_id: str