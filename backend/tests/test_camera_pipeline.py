"""
Test: Camera Frame → Perception Agent → Vision LLM → Structured Scene Response

Verifies the full /analyze-scene flow:
1. Flutter sends a base64 image + GPS
2. Perception Agent sends it to vision model
3. Response comes back with scene description, obstacles, guidance, risk level
4. Response matches our data contract exactly
"""

import pytest
from unittest.mock import patch


# =====================================================
# ENDPOINT TESTS — hit /analyze-scene through the API
# =====================================================

class TestAnalyzeSceneEndpoint:

    def test_scene_returns_valid_structure(self, sync_client, mock_llm_normal, sample_camera_payload):
        """The response should have all required fields from the data contract"""
        resp = sync_client.post("/analyze-scene", json=sample_camera_payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "scene_description" in data
        assert "obstacles" in data
        assert "guidance_text" in data
        assert "risk_level" in data
        assert isinstance(data["obstacles"], list)

    def test_scene_risk_level_valid_values(self, sync_client, mock_llm_normal, sample_camera_payload):
        """Risk level should only be one of the allowed values"""
        resp = sync_client.post("/analyze-scene", json=sample_camera_payload)
        data = resp.json()
        assert data["risk_level"] in ("none", "low", "medium", "high")

    def test_scene_obstacles_have_required_fields(self, sync_client, mock_llm_normal, sample_camera_payload):
        """Each obstacle should have type, distance, and direction"""
        resp = sync_client.post("/analyze-scene", json=sample_camera_payload)
        data = resp.json()

        for obstacle in data["obstacles"]:
            assert "type" in obstacle
            assert "distance" in obstacle
            assert "direction" in obstacle

    def test_scene_with_empty_image_returns_graceful_fallback(self, sync_client, mock_llm_normal):
        """If Flutter sends an empty image (camera failed), we should still get a valid response"""
        payload = {
            "image": "",
            "location": {"lat": 19.1136, "lng": 72.8697},
            "user_id": "ramesh-001",
        }
        resp = sync_client.post("/analyze-scene", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # Should get a helpful message, not a crash
        assert len(data["scene_description"]) > 0

    def test_scene_with_short_image_returns_graceful_fallback(self, sync_client, mock_llm_normal):
        """If the base64 string is too short to be real, handle gracefully"""
        payload = {
            "image": "abc123",
            "location": {"lat": 19.1136, "lng": 72.8697},
            "user_id": "ramesh-001",
        }
        resp = sync_client.post("/analyze-scene", json=payload)
        assert resp.status_code == 200

    def test_scene_llm_total_failure_still_returns_response(self, sync_client, sample_camera_payload):
        """Even if all LLM providers are down, user gets a safe fallback"""
        async def _broken_vision(*args, **kwargs):
            raise Exception("All providers down")

        with patch("utils.llm.vision_completion", new=_broken_vision):
            resp = sync_client.post("/analyze-scene", json=sample_camera_payload)
            assert resp.status_code == 200
            data = resp.json()
            # Should still have a scene_description, even if it's a fallback
            assert len(data["scene_description"]) > 0
            assert data["risk_level"] in ("none", "low", "medium", "high")

    def test_scene_malformed_llm_json_handled(self, sync_client, sample_camera_payload):
        """If the vision model returns garbage instead of JSON, don't crash"""
        async def _garbage_vision(*args, **kwargs):
            return "Sorry, I can't process images right now. Here's some random text instead."

        with patch("utils.llm.vision_completion", new=_garbage_vision):
            resp = sync_client.post("/analyze-scene", json=sample_camera_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["scene_description"]) > 0


# =====================================================
# PIPELINE TESTS — test the agents directly
# =====================================================

class TestCameraPerceptionAgent:

    @pytest.mark.asyncio
    async def test_perception_processes_camera_input(self, mock_llm_normal):
        """Perception agent should extract scene data from camera input"""
        import base64
        from agents.perception import perception_agent

        fake_image = base64.b64encode(b"x" * 200).decode()
        state = {
            "user_id": "ramesh-001",
            "trigger_type": "camera",
            "image_base64": fake_image,
            "gps_lat": 19.1136,
            "gps_lng": 72.8697,
            "agents_executed": [],
            "llm_calls_made": 0,
        }

        result = await perception_agent(state)

        assert "perception" in result["agents_executed"]
        assert result.get("scene_description") is not None
        assert isinstance(result.get("obstacles", []), list)
        assert result.get("llm_calls_made", 0) >= 1
        assert "Camera" in result.get("perception_summary", "")

    @pytest.mark.asyncio
    async def test_perception_detects_emotion_from_voice(self, mock_llm_normal):
        """When user sends a voice message, perception should detect emotion"""
        from agents.perception import perception_agent

        state = {
            "user_id": "ramesh-001",
            "trigger_type": "voice",
            "user_message": "I'm feeling great today!",
            "agents_executed": [],
            "llm_calls_made": 0,
        }

        result = await perception_agent(state)

        assert result.get("detected_emotion") in ("calm", "happy", "confused", "distressed", "agitated")
        assert "User said" in result.get("perception_summary", "")

    @pytest.mark.asyncio
    async def test_perception_handles_combined_input(self, mock_llm_normal):
        """Real scenario: user speaks while pointing camera"""
        import base64
        from agents.perception import perception_agent

        fake_image = base64.b64encode(b"x" * 200).decode()
        state = {
            "user_id": "ramesh-001",
            "trigger_type": "camera",
            "user_message": "What am I looking at?",
            "image_base64": fake_image,
            "gps_lat": 19.1136,
            "gps_lng": 72.8697,
            "agents_executed": [],
            "llm_calls_made": 0,
        }

        result = await perception_agent(state)

        # Should have processed BOTH voice and camera
        summary = result.get("perception_summary", "")
        assert "User said" in summary
        assert "Camera" in summary
        assert result.get("detected_emotion") is not None
        assert result.get("scene_description") is not None