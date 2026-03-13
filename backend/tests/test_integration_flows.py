"""
End-to-End Integration Flows
==============================
Simulates real user journeys through the Android app.
Each scenario chains multiple API calls the way the app does.
"""

import pytest, asyncio, base64
from unittest.mock import patch
from tests.conftest import _mock_llm_factory


# =========================================================
# SCENARIO 1: Ramesh's calm morning
# =========================================================

class TestCalmMorningFlow:

    def test_01_sos_check(self, sync_client):
        """7:00 AM — App sends SOS/status check on launch"""
        resp = sync_client.post("/check-status", json={"user_id": "ramesh_demo_001"})
        data = resp.json()
        assert data["status"] == "SAFE"
        assert isinstance(data["caregiver_notified"], bool)

    def test_02_morning_conversation(self, sync_client, mock_llm_normal):
        """8:00 AM — Ramesh says good morning"""
        resp = sync_client.post("/conversation", json={
            "user_id": "ramesh_demo_001", "message": "Good morning! What should I do today?", "role": "patient"
        })
        data = resp.json()
        assert len(data["response_text"]) > 0
        assert data["aac_score"] > 0  # non-null, non-zero
        assert data["emr_triggered"] is False

    def test_03_check_reminders(self, sync_client):
        """8:05 AM — App auto-loads reminders"""
        resp = sync_client.get("/patient/reminders/ramesh_demo_001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_04_caregiver_views_summary(self, sync_client, mock_llm_normal):
        """6 PM — Priya checks Ramesh's day"""
        resp = sync_client.get("/caregiver/summary/ramesh_demo_001")
        data = resp.json()
        assert data["patient_id"] == "ramesh_demo_001"
        assert len(data["mood_summary"]) > 0
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "MODERATE")

    def test_05_caregiver_views_trends(self, sync_client):
        """6:05 PM — Priya taps cognitive trends chart"""
        resp = sync_client.get("/caregiver/trends/ramesh_demo_001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_06_caregiver_views_alerts(self, sync_client):
        """6:10 PM — Priya checks alert feed"""
        resp = sync_client.get("/caregiver/alerts/ramesh_demo_001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# =========================================================
# SCENARIO 2: Fall emergency
# =========================================================

class TestFallEmergencyFlow:

    def test_wearable_detects_fall(self, sync_client, mock_llm_high_risk):
        """Wearable pipeline detects fall (extended endpoint)"""
        resp = sync_client.post("/check-wearable", json={
            "user_id": "ramesh_demo_001",
            "wearable_data": {
                "heart_rate": 115, "accelerometer": {"x": 18.0, "y": 22.0, "z": 28.0},
                "steps": 0, "gps": {"lat": 19.1136, "lng": 72.8697}
            },
            "window_seconds": 30,
        })
        data = resp.json()
        assert data["classification"] == "fall"
        assert data["risk_level"] in ("high", "critical")
        assert data.get("caregiver_alert") is not None

    def test_fall_alert_payload_shape(self, sync_client, mock_llm_high_risk):
        """Alert payload must have priority/message/context for push notification"""
        resp = sync_client.post("/check-wearable", json={
            "user_id": "ramesh_demo_001",
            "wearable_data": {"heart_rate": 115, "accelerometer": {"x": 18.0, "y": 22.0, "z": 28.0}, "steps": 0, "gps": {"lat": 19.1136, "lng": 72.8697}},
            "window_seconds": 30,
        })
        alert = resp.json().get("caregiver_alert")
        if alert:
            assert "priority" in alert
            assert "message" in alert
            assert "context" in alert

    def test_caregiver_acknowledges_alert(self, sync_client):
        """Priya taps acknowledge on her phone"""
        resp = sync_client.post("/caregiver/alerts/alert-001/acknowledge", json={
            "acknowledged_by": "caregiver_priya_001", "note": "On my way home"
        })
        assert resp.status_code == 200


# =========================================================
# SCENARIO 3: Distress conversation with EMR
# =========================================================

class TestDistressEMRFlow:

    @pytest.mark.asyncio
    async def test_distress_triggers_emr_and_parallel(self, mock_llm_high_risk):
        """Ramesh is confused → EMR triggers + caregiver alerted in parallel"""
        from agents.pipeline import run_pipeline
        state = await run_pipeline({
            "user_id": "ramesh_demo_001", "role": "patient",
            "trigger_type": "voice",
            "user_message": "I don't know where I am. Everything looks strange.",
        })
        agents = state.get("agents_executed", [])
        assert "assistance" in agents
        assert "caregiver" in agents
        assert state.get("risk_level") in ("medium", "high", "critical")
        assert state.get("trigger_emr") is True


# =========================================================
# SCENARIO 4: Camera assist
# =========================================================

class TestCameraAssistFlow:

    def test_camera_multipart_then_conversation(self, sync_client, mock_llm_normal):
        """User scans scene, then asks about it"""
        scene_resp = sync_client.post("/analyze-scene",
            data={"user_id": "ramesh_demo_001"},
            files={"image": ("scene.jpg", b"\xff\xd8\xff" + b"x" * 200, "image/jpeg")})
        assert scene_resp.status_code == 200
        desc = scene_resp.json()["description"]
        assert len(desc) > 0

        conv_resp = sync_client.post("/conversation", json={
            "user_id": "ramesh_demo_001", "message": "What am I looking at?", "role": "patient"
        })
        assert conv_resp.status_code == 200
        assert len(conv_resp.json()["response_text"]) > 0


# =========================================================
# SCENARIO 5: Normal wearable short-circuit
# =========================================================

class TestWearableShortCircuit:

    @pytest.mark.asyncio
    async def test_normal_wearable_skips_llm(self, mock_llm_normal):
        """Normal vitals → perception + context only, zero LLM calls after"""
        from agents.pipeline import run_pipeline
        state = await run_pipeline({
            "user_id": "ramesh_demo_001", "role": "patient", "trigger_type": "wearable",
            "heart_rate": 72, "accel_x": 0.1, "accel_y": 0.2, "accel_z": 9.8,
            "steps": 5, "gps_lat": 19.1136, "gps_lng": 72.8697, "window_seconds": 30,
        })
        assert state["risk_level"] == "none"
        assert state["alert_caregiver"] is False
        assert "reasoning" not in state.get("agents_executed", [])


# =========================================================
# SCENARIO 6: Every endpoint smoke test
# =========================================================

class TestAllEndpointsSmoke:

    def test_every_android_endpoint(self, sync_client, mock_llm_normal):
        """Hit every endpoint the Android app calls — nothing should 500."""
        endpoints = [
            ("GET", "/health", None, None),
            ("GET", "/", None, None),
            ("POST", "/conversation", {"user_id": "r", "message": "hi", "role": "patient"}, None),
            ("POST", "/check-status", {"user_id": "r"}, None),
            ("POST", "/analyze-scene", None, {"data": {"user_id": "r"}, "files": {"image": ("f.jpg", b"x"*50, "image/jpeg")}}),
            ("GET", "/caregiver/alerts/r", None, None),
            ("GET", "/caregiver/summary/r", None, None),
            ("GET", "/caregiver/trends/r", None, None),
            ("GET", "/patient/reminders/r", None, None),
        ]
        for method, path, json_body, kwargs in endpoints:
            if method == "GET":
                resp = sync_client.get(path)
            elif kwargs:
                resp = sync_client.post(path, **kwargs)
            else:
                resp = sync_client.post(path, json=json_body)
            assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}"


# =========================================================
# SCENARIO 7: Resilience under failure
# =========================================================

class TestResilience:

    def test_conversation_pipeline_crash_returns_warm_response(self, sync_client):
        async def _boom(*a, **kw): raise Exception("total failure")
        with patch("api.routes.conversation.run_pipeline", new=_boom):
            resp = sync_client.post("/conversation", json={"user_id": "r", "message": "hi", "role": "patient"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["response_text"]) > 0
            assert data["aac_score"] is not None  # never null

    def test_scene_vision_crash_returns_description(self, sync_client):
        async def _boom(*a, **kw): raise Exception("vision down")
        with patch("utils.llm.vision_completion", new=_boom):
            resp = sync_client.post("/analyze-scene",
                data={"user_id": "r"}, files={"image": ("f.jpg", b"x"*200, "image/jpeg")})
            assert resp.status_code == 200
            assert len(resp.json()["description"]) > 0

    @pytest.mark.asyncio
    async def test_pipeline_survives_perception_crash(self):
        async def _broken(state): raise Exception("crash")
        m = _mock_llm_factory("normal")
        with patch("agents.pipeline.perception_agent", new=_broken), \
             patch("utils.llm.chat_completion", new=m), \
             patch("agents.perception.chat_completion", new=m), \
             patch("agents.reasoning.chat_completion", new=m), \
             patch("agents.assistance.chat_completion", new=m), \
             patch("agents.caregiver.chat_completion", new=m):
            from agents.pipeline import run_pipeline
            state = await run_pipeline({"user_id": "r", "role": "patient", "trigger_type": "voice", "user_message": "hi"})
            assert len(state.get("errors", [])) > 0
            assert state.get("response_text") is not None


# =========================================================
# SCENARIO 8: Concurrent requests
# =========================================================

class TestConcurrent:

    @pytest.mark.asyncio
    async def test_parallel_status_and_conversation(self, async_client, mock_llm_normal):
        """Android background service sends status while user is talking."""
        status_task = async_client.post("/check-status", json={"user_id": "r"})
        conv_task = async_client.post("/conversation", json={"user_id": "r", "message": "hi", "role": "patient"})
        s_resp, c_resp = await asyncio.gather(status_task, conv_task)
        assert s_resp.status_code == 200
        assert c_resp.status_code == 200


# =========================================================
# SCENARIO 9: Edge cases from real Android usage
# =========================================================

class TestEdgeCases:

    def test_empty_message(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/conversation", json={"user_id": "r", "message": "", "role": "patient"})
        assert resp.status_code == 200
        assert len(resp.json()["response_text"]) > 0

    def test_unicode_hindi(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/conversation", json={"user_id": "r", "message": "मुझे अच्छा लग रहा है", "role": "patient"})
        assert resp.status_code == 200

    def test_very_long_message(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/conversation", json={"user_id": "r", "message": "hello " * 500, "role": "patient"})
        assert resp.status_code == 200

    def test_missing_required_field_422(self, sync_client):
        """Pydantic rejects incomplete requests."""
        resp = sync_client.post("/conversation", json={"user_id": "r"})
        assert resp.status_code == 422

    def test_tiny_scene_image(self, sync_client, mock_llm_normal):
        resp = sync_client.post("/analyze-scene",
            data={"user_id": "r"}, files={"image": ("f.jpg", b"x", "image/jpeg")})
        assert resp.status_code == 200
        assert len(resp.json()["description"]) > 0


# =========================================================
# SCENARIO 10: WebSocket alert format
# =========================================================

class TestWebSocketContract:
    """Android: WsAlertMessage(type: String, alert: Alert?, message: String)
    The backend must send JSON matching this shape over WebSocket.
    """

    def test_websocket_connect_disconnect(self, sync_client):
        """Basic WS lifecycle test."""
        with sync_client.websocket_connect("/ws/alerts/priya-001") as ws:
            # Connection established successfully
            pass  # disconnect happens on exit

    def test_websocket_receives_alert_format(self, sync_client):
        """Push an alert and verify it matches WsAlertMessage shape."""
        import asyncio
        from api.routes.websocket import broadcast_alert, active_connections

        with sync_client.websocket_connect("/ws/alerts/priya-001") as ws:
            # Simulate an alert broadcast
            alert_payload = {
                "id": "alert-001", "patient_id": "ramesh-001",
                "alert_type": "FALL_DETECTED", "priority": "CRITICAL",
                "title": "Fall Detected", "description": "Ramesh fell",
                "message": "Fall detected in kitchen",
            }
            # Use the event loop to broadcast
            loop = asyncio.new_event_loop()
            loop.run_until_complete(broadcast_alert("priya-001", alert_payload))
            loop.close()

            msg = ws.receive_json()
            # Must match WsAlertMessage shape
            assert "type" in msg, "WsAlertMessage.type missing"
            assert "message" in msg, "WsAlertMessage.message missing"
            assert msg["type"] == "alert"
