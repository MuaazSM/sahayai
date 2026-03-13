"""
Test: Wearable Data → Classifier → Pipeline → Caregiver Alert

Verifies:
1. Normal readings short-circuit (no LLM calls, fast response)
2. Falls trigger critical alerts + parallel caregiver notification
3. Wandering triggers high-risk response + geofencing context
4. Distress triggers appropriate user message + caregiver alert
5. All responses match the data contract
"""

import pytest
from unittest.mock import patch


# =====================================================
# CLASSIFIER UNIT TESTS — rule-based fallback
# =====================================================

class TestWearableClassifier:

    def test_normal_reading(self):
        """Normal vitals at home should classify as normal"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=72, accel_x=0.1, accel_y=0.2, accel_z=9.8,
            steps=5, gps_lat=19.1136, gps_lng=72.8697,
            home_lat=19.1136, home_lng=72.8697,
        )
        assert result["classification"] == "normal"
        assert result["confidence"] >= 0.7

    def test_fall_detection(self):
        """High acceleration + elevated HR = fall"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=110, accel_x=15.0, accel_y=20.0, accel_z=25.0,
            steps=0, gps_lat=19.1136, gps_lng=72.8697,
            home_lat=19.1136, home_lng=72.8697,
        )
        assert result["classification"] == "fall"
        assert result["confidence"] >= 0.7

    def test_extreme_fall_without_hr_spike(self):
        """Massive accel spike alone should still detect as fall"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=75, accel_x=20.0, accel_y=25.0, accel_z=30.0,
            steps=0, gps_lat=19.1136, gps_lng=72.8697,
        )
        assert result["classification"] == "fall"

    def test_wandering_detection(self):
        """Far from home + walking = wandering"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=85, accel_x=1.2, accel_y=0.8, accel_z=9.9,
            steps=45, gps_lat=19.1250, gps_lng=72.8800,
            home_lat=19.1136, home_lng=72.8697,
        )
        assert result["classification"] == "wandering"

    def test_very_far_from_home_even_stationary(self):
        """1km+ from home even without moving = wandering"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=70, accel_x=0.1, accel_y=0.1, accel_z=9.8,
            steps=0, gps_lat=19.1250, gps_lng=72.9000,  # ~3km away
            home_lat=19.1136, home_lng=72.8697,
        )
        assert result["classification"] == "wandering"

    def test_distress_high_hr_low_movement(self):
        """Sky-high heart rate + no movement = distress"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=145, accel_x=0.05, accel_y=0.1, accel_z=9.8,
            steps=0, gps_lat=19.1136, gps_lng=72.8697,
        )
        assert result["classification"] == "distress"

    def test_distress_very_low_hr(self):
        """Dangerously low heart rate = distress"""
        from classifier.predict import classify_wearable

        result = classify_wearable(
            heart_rate=40, accel_x=0.1, accel_y=0.1, accel_z=9.8,
            steps=0, gps_lat=19.1136, gps_lng=72.8697,
        )
        assert result["classification"] == "distress"

    def test_haversine_distance(self):
        """Sanity check the distance calculation"""
        from classifier.predict import _haversine_meters

        # Same point = 0 distance
        assert _haversine_meters(19.1136, 72.8697, 19.1136, 72.8697) < 1

        # ~1.5km away
        dist = _haversine_meters(19.1136, 72.8697, 19.1250, 72.8800)
        assert 1000 < dist < 2000


# =====================================================
# ENDPOINT TESTS — /check-wearable (full pipeline)
# =====================================================

class TestCheckStatusEndpoint:

    def test_normal_returns_no_alert(self, sync_client, mock_llm_normal, normal_wearable_data):
        """Normal readings should return risk=none with no caregiver alert"""
        resp = sync_client.post("/check-wearable", json=normal_wearable_data)

        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "normal"
        assert data["risk_level"] == "none"
        assert data["caregiver_alert"] is None
        assert data["user_message"] is None

    def test_fall_returns_critical_alert(self, sync_client, mock_llm_high_risk, fall_wearable_data):
        """Fall should return critical risk + caregiver alert"""
        resp = sync_client.post("/check-wearable", json=fall_wearable_data)

        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "fall"
        assert data["risk_level"] in ("high", "critical")
        assert data["caregiver_alert"] is not None
        assert data["caregiver_alert"]["priority"] in ("urgent", "emergency")

    def test_wandering_returns_high_risk(self, sync_client, mock_llm_high_risk, wandering_wearable_data):
        """Wandering should return high risk + alert"""
        resp = sync_client.post("/check-wearable", json=wandering_wearable_data)

        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "wandering"
        assert data["risk_level"] in ("medium", "high")

    def test_distress_returns_user_message(self, sync_client, mock_llm_high_risk, distress_wearable_data):
        """Distress should generate a calming user message"""
        resp = sync_client.post("/check-wearable", json=distress_wearable_data)

        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "distress"
        assert data["user_message"] is not None
        assert len(data["user_message"]) > 0

    def test_response_matches_data_contract(self, sync_client, mock_llm_normal, normal_wearable_data):
        """Response should have exactly the fields from our data contract"""
        resp = sync_client.post("/check-wearable", json=normal_wearable_data)
        data = resp.json()

        required_fields = ["classification", "confidence", "risk_level", "user_message", "caregiver_alert"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        assert isinstance(data["confidence"], float)
        assert 0.0 <= data["confidence"] <= 1.0

    def test_total_failure_returns_safe_default(self, sync_client, normal_wearable_data):
        """Even if the entire pipeline explodes, return a safe response"""
        async def _broken_pipeline(*args, **kwargs):
            raise Exception("Everything is on fire")

        with patch("api.routes.status.run_pipeline", new=_broken_pipeline):
            resp = sync_client.post("/check-wearable", json=normal_wearable_data)
            assert resp.status_code == 200
            data = resp.json()
            assert data["classification"] == "normal"


# =====================================================
# FULL PIPELINE TESTS — wearable through all agents
# =====================================================

class TestWearablePipeline:

    @pytest.mark.asyncio
    async def test_normal_wearable_short_circuits(self, mock_llm_normal):
        """Normal wearable data should skip reasoning/assistance/caregiver"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "wearable",
            "heart_rate": 72,
            "accel_x": 0.1, "accel_y": 0.2, "accel_z": 9.8,
            "steps": 5,
            "gps_lat": 19.1136, "gps_lng": 72.8697,
            "window_seconds": 30,
        })

        agents = state.get("agents_executed", [])
        assert "perception" in agents
        assert "context" in agents
        # Reasoning should be skipped — nothing interesting happening
        assert "reasoning" not in agents
        assert state.get("risk_level") == "none"
        assert state.get("alert_caregiver") == False

    @pytest.mark.asyncio
    async def test_fall_triggers_parallel_path(self, mock_llm_high_risk):
        """Fall detection should run both Assistance and Caregiver agents"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "wearable",
            "heart_rate": 110,
            "accel_x": 15.0, "accel_y": 20.0, "accel_z": 25.0,
            "steps": 0,
            "gps_lat": 19.1136, "gps_lng": 72.8697,
            "window_seconds": 30,
        })

        agents = state.get("agents_executed", [])
        assert "perception" in agents
        assert "context" in agents
        assert "reasoning" in agents
        # Both should have run (parallel path)
        assert "assistance" in agents
        assert "caregiver" in agents
        # Should have generated a caregiver alert
        assert state.get("risk_level") in ("high", "critical")

    @pytest.mark.asyncio
    async def test_wandering_includes_distance_context(self, mock_llm_high_risk):
        """Wandering detection should include GPS distance info"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "wearable",
            "heart_rate": 85,
            "accel_x": 1.2, "accel_y": 0.8, "accel_z": 9.9,
            "steps": 45,
            "gps_lat": 19.1250, "gps_lng": 72.8800,
            "window_seconds": 30,
        })

        assert state.get("wearable_classification") == "wandering"
        assert "wandering" in state.get("perception_summary", "").lower()

    @pytest.mark.asyncio
    async def test_pipeline_latency_tracked(self, mock_llm_normal):
        """Pipeline should track its own execution time"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "wearable",
            "heart_rate": 72,
            "accel_x": 0.1, "accel_y": 0.2, "accel_z": 9.8,
            "steps": 5,
            "gps_lat": 19.1136, "gps_lng": 72.8697,
            "window_seconds": 30,
        })

        assert state.get("pipeline_started_at") is not None
        assert state.get("pipeline_completed_at") is not None

    @pytest.mark.asyncio
    async def test_pipeline_survives_agent_failure(self):
        """If one agent throws, the pipeline should continue with fallbacks"""
        from agents.pipeline import run_pipeline

        async def _broken_perception(state):
            raise Exception("Perception crashed")

        with patch("agents.pipeline.perception_agent", new=_broken_perception), \
             patch("utils.llm.chat_completion", new=_mock_chat_completion_factory("normal")):

            state = await run_pipeline({
                "user_id": "ramesh-001",
                "role": "patient",
                "trigger_type": "voice",
                "user_message": "hello",
            })

            # Pipeline should still complete despite perception failing
            assert "perception" not in state.get("agents_executed", [])
            assert len(state.get("errors", [])) > 0
            # Should still have a response for the user
            assert state.get("response_text") is not None


# import the factory here so the last test can use it
from tests.conftest import _mock_chat_completion_factory