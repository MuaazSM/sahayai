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

class SceneResponse(BaseModel):
    """Matches Android SceneResponse data class."""
    description: str
    objects_detected: list[str] = []
    safety_concerns: list[str] = []
    confidence: float = 1.0


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
    aac_score: Optional[float] = None  # float to match Android ConversationResponse.aacScore: Float
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
    wearable_data: Optional[WearableData] = None  # optional — Android SOS sends user_id only
    window_seconds: int = 30
    location_lat: Optional[float] = None  # Android StatusRequest optional fields
    location_lng: Optional[float] = None


class WearableStatusRequest(BaseModel):
    """Separate request for the /check-wearable endpoint (background service)."""
    user_id: str
    wearable_data: WearableData
    window_seconds: int = 30


class CaregiverAlertPayload(BaseModel):
    priority: str
    message: str
    context: str


class WearableStatusResponse(BaseModel):
    """Response for /check-wearable — used by background wearable service."""
    classification: str
    confidence: float
    risk_level: str
    user_message: Optional[str] = None
    caregiver_alert: Optional[CaregiverAlertPayload] = None

class StatusResponse(BaseModel):
    # Backend/pipeline fields (kept for wearable tests)
    classification: str = "normal"  # normal, fall, wandering, distress
    confidence: float = 0.9
    risk_level: str = "none"        # none, low, medium, high, critical
    user_message: Optional[str] = None
    caregiver_alert: Optional[CaregiverAlertPayload] = None
    # Android EmergencyViewModel fields
    status: str = "ok"
    message: str = ""
    alert_sent: bool = False
    caregiver_notified: bool = False


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
    acknowledged_by: str = ""           # Android sends this
    note: Optional[str] = None
    action: str = "acknowledge"         # acknowledge, dismiss, escalate (kept for internal use)

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
    """Matches Android Reminder data class."""
    id: str
    user_id: str
    title: str
    description: str = ""
    reminder_type: str = "OTHER"
    scheduled_time: str
    is_confirmed: bool = False
    created_at: str = ""

class RemindersResponse(BaseModel):
    reminders: list[ReminderItem]

class ConfirmReminderRequest(BaseModel):
    confirmation_method: str = "tap"  # voice or tap; Android sends no body so default to tap

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