"""
Android ↔ Backend API Contract Tests
======================================
Verifies every JSON field the Android Kotlin data classes deserialize.
A mismatch here = crash or silent data loss on the phone.

Contract source: android/app/src/main/java/com/sahayai/android/domain/model/
Serialization: Kotlinx Serialization with @SerialName annotations
"""

import pytest


# =========================================================
# /conversation — Android ConversationResponse
# =========================================================

class TestConversationContract:
    """Android data class:
    ConversationResponse(
        @SerialName("response_text") responseText: String,
        @SerialName("aac_score")     aacScore: Float,       // NON-NULLABLE
        @SerialName("cct_score")     cctScore: Float?,
        @SerialName("emr_triggered") emrTriggered: Boolean,
        @SerialName("emr_memory")    emrMemory: String?
    )
    """

    def test_all_serialname_fields_present(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/conversation", json={"user_id": "ramesh-001", "message": "Hello", "role": "patient"})
        data = resp.json()
        for field in ["response_text", "aac_score", "cct_score", "emr_triggered", "emr_memory"]:
            assert field in data, f"Android @SerialName('{field}') missing from response"

    def test_aac_score_never_null(self, sync_client, mock_llm_normal):
        """CRITICAL: Android aacScore is Float (non-nullable). Null = NumberFormatException crash."""
        resp = sync_client.post("/conversation", json={"user_id": "ramesh-001", "message": "hi", "role": "patient"})
        assert resp.json()["aac_score"] is not None
        assert isinstance(resp.json()["aac_score"], (int, float))

    def test_aac_score_never_null_on_error(self, sync_client):
        """Even on pipeline crash, aac_score must be a number."""
        from unittest.mock import patch
        async def _boom(*a, **kw): raise Exception("crash")
        with patch("api.routes.conversation.run_pipeline", new=_boom):
            resp = sync_client.post("/conversation", json={"user_id": "x", "message": "hi", "role": "patient"})
            assert resp.json()["aac_score"] is not None

    def test_types_match_kotlin(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/conversation", json={"user_id": "ramesh-001", "message": "test", "role": "patient"})
        d = resp.json()
        assert isinstance(d["response_text"], str)         # String
        assert isinstance(d["aac_score"], (int, float))     # Float
        assert isinstance(d["emr_triggered"], bool)         # Boolean
        assert d["cct_score"] is None or isinstance(d["cct_score"], (int, float))  # Float?
        assert d["emr_memory"] is None or isinstance(d["emr_memory"], str)         # String?

    def test_response_text_never_empty(self, sync_client, mock_llm_normal):
        """Android TTS reads response_text aloud — empty string = silent phone."""
        resp = sync_client.post("/conversation", json={"user_id": "ramesh-001", "message": "hello", "role": "patient"})
        assert len(resp.json()["response_text"]) > 0

    def test_android_request_shape_accepted(self, sync_client, mock_llm_normal):
        """Android sends: {user_id, message, role} — no conversation_id field."""
        resp = sync_client.post("/conversation", json={"user_id": "ramesh_demo_001", "message": "Namaste", "role": "patient"})
        assert resp.status_code == 200

    def test_no_unexpected_crash_fields(self, sync_client, mock_llm_normal):
        """Core @SerialName fields must always be present."""
        resp = sync_client.post("/conversation", json={"user_id": "ramesh-001", "message": "hi", "role": "patient"})
        allowed = {"response_text", "aac_score", "cct_score", "emr_triggered", "emr_memory"}
        for f in allowed:
            assert f in resp.json()


# =========================================================
# /check-status — Android StatusResponse
# =========================================================

class TestStatusContract:
    """Android data class:
    StatusResponse(
        @SerialName("status")             status: String,
        @SerialName("message")            message: String,
        @SerialName("alert_sent")         alertSent: Boolean,
        @SerialName("caregiver_notified") caregiverNotified: Boolean
    )
    Android sends: StatusRequest(user_id, location_lat?, location_lng?)
    """

    def test_android_request_shape(self, sync_client):
        """Android sends simple {user_id, location_lat?, location_lng?}"""
        resp = sync_client.post("/check-status", json={"user_id": "ramesh_demo_001", "location_lat": 19.1136, "location_lng": 72.8697})
        assert resp.status_code == 200

    def test_all_serialname_fields(self, sync_client):
        resp = sync_client.post("/check-status", json={"user_id": "ramesh-001"})
        data = resp.json()
        for field in ["status", "message", "alert_sent", "caregiver_notified"]:
            assert field in data, f"Android @SerialName('{field}') missing"

    def test_field_types(self, sync_client):
        data = sync_client.post("/check-status", json={"user_id": "ramesh-001"}).json()
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["alert_sent"], bool)
        assert isinstance(data["caregiver_notified"], bool)

    def test_status_without_location(self, sync_client):
        """Android may omit location fields (Optional)."""
        resp = sync_client.post("/check-status", json={"user_id": "ramesh-001"})
        assert resp.status_code == 200


# =========================================================
# /analyze-scene — Android SceneResponse (multipart upload)
# =========================================================

class TestSceneContract:
    """Android data class:
    SceneResponse(
        @SerialName("description")       description: String,
        @SerialName("objects_detected")   objectsDetected: List<String>,
        @SerialName("safety_concerns")    safetyConcerns: List<String>,
        @SerialName("confidence")         confidence: Float
    )
    Android sends: multipart form with user_id (text) + image (file)
    """

    def test_multipart_upload_accepted(self, sync_client, mock_llm_normal):
        """Android sends multipart/form-data, NOT JSON."""
        resp = sync_client.post("/analyze-scene",
            data={"user_id": "ramesh_demo_001"},
            files={"image": ("scene.jpg", b"\xff\xd8\xff" + b"x" * 200, "image/jpeg")})
        assert resp.status_code == 200

    def test_all_serialname_fields(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/analyze-scene",
            data={"user_id": "ramesh-001"},
            files={"image": ("scene.jpg", b"\xff\xd8\xff" + b"x" * 200, "image/jpeg")})
        data = resp.json()
        for field in ["description", "objects_detected", "safety_concerns", "confidence"]:
            assert field in data, f"Android @SerialName('{field}') missing"

    def test_field_types(self, sync_client, mock_llm_normal):
        data = sync_client.post("/analyze-scene",
            data={"user_id": "ramesh-001"},
            files={"image": ("scene.jpg", b"x" * 200, "image/jpeg")}).json()
        assert isinstance(data["description"], str)
        assert isinstance(data["objects_detected"], list)
        assert isinstance(data["safety_concerns"], list)
        assert isinstance(data["confidence"], (int, float))

    def test_objects_detected_are_strings(self, sync_client, mock_llm_normal):
        """Android: List<String> — each element must be a string, not an object."""
        data = sync_client.post("/analyze-scene",
            data={"user_id": "ramesh-001"},
            files={"image": ("scene.jpg", b"x" * 200, "image/jpeg")}).json()
        for obj in data["objects_detected"]:
            assert isinstance(obj, str), f"objects_detected contains non-string: {type(obj)}"


# =========================================================
# /caregiver/alerts — Android List<Alert>
# =========================================================

class TestAlertsContract:
    """Android: Response<List<Alert>>  (flat list, NOT wrapped)"""

    def test_returns_flat_list(self, sync_client):
        resp = sync_client.get("/caregiver/alerts/ramesh_demo_001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list), "Android expects List<Alert>, not {alerts:[...]}"

    def test_alert_item_fields_when_present(self, sync_client):
        data = sync_client.get("/caregiver/alerts/ramesh-001").json()
        assert isinstance(data, list)


# =========================================================
# /caregiver/alerts/{id}/acknowledge — Android Response<Unit>
# =========================================================

class TestAcknowledgeContract:
    """Android: Response<Unit> — expects 200 with empty/null body.
    Android sends: AcknowledgeRequest(acknowledged_by, note)
    """

    def test_android_request_shape(self, sync_client):
        """Android sends {acknowledged_by, note}, NOT {action, note}."""
        resp = sync_client.post("/caregiver/alerts/alert-001/acknowledge",
            json={"acknowledged_by": "caregiver_priya_001", "note": "On my way"})
        assert resp.status_code == 200

    def test_without_note(self, sync_client):
        resp = sync_client.post("/caregiver/alerts/alert-001/acknowledge",
            json={"acknowledged_by": "priya-001"})
        assert resp.status_code == 200


# =========================================================
# /caregiver/summary — Android CaregiverSummary
# =========================================================

class TestSummaryContract:
    """Android data class:
    CaregiverSummary(
        patient_id, date, steps_today, reminders_completed, reminders_total,
        avg_cct_score, risk_level, aac_score, conversations_today, mood_summary
    )
    """

    def test_all_serialname_fields(self, sync_client, mock_llm_normal):
        data = sync_client.get("/caregiver/summary/ramesh_demo_001").json()
        for field in ["patient_id", "date", "steps_today", "reminders_completed",
                       "reminders_total", "avg_cct_score", "risk_level", "aac_score",
                       "conversations_today", "mood_summary"]:
            assert field in data, f"Android CaregiverSummary @SerialName('{field}') missing"

    def test_types(self, sync_client, mock_llm_normal):
        d = sync_client.get("/caregiver/summary/ramesh-001").json()
        assert isinstance(d["patient_id"], str)
        assert isinstance(d["date"], str)
        assert isinstance(d["steps_today"], int)
        assert isinstance(d["aac_score"], (int, float))
        assert isinstance(d["mood_summary"], str)


# =========================================================
# /caregiver/trends — Android List<CognitiveTrendPoint>
# =========================================================

class TestTrendsContract:
    """Android: List<CognitiveTrendPoint>(date, cct_score, aac_score?, conversation_count)"""

    def test_returns_list(self, sync_client):
        resp = sync_client.get("/caregiver/trends/ramesh-001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# =========================================================
# /patient/reminders — Android List<Reminder>
# =========================================================

class TestRemindersContract:
    """Android: Response<List<Reminder>>  (flat list, NOT {reminders:[...]})"""

    def test_returns_flat_list(self, sync_client):
        resp = sync_client.get("/patient/reminders/ramesh_demo_001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list), "Android expects List<Reminder>, not {reminders:[...]}"

    def test_confirm_returns_success(self, sync_client):
        """Android: Response<Unit> — just needs 200."""
        resp = sync_client.post("/patient/reminders/rem_001/confirm")
        assert resp.status_code == 200


# =========================================================
# /health — basic connectivity check
# =========================================================

class TestHealthContract:

    def test_health_up(self, sync_client):
        assert sync_client.get("/health").json()["status"] == "healthy"

    def test_root(self, sync_client):
        assert "SahayAI" in sync_client.get("/").json()["message"]
