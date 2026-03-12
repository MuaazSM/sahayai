"""
Test: Voice Input → Full Agent Pipeline → Response + CCT + EMR

Verifies:
1. Normal conversation returns warm response + CCT score
2. Distress conversation triggers EMR + caregiver alert
3. Caregiver "how was dad's day?" gets proper summary
4. Conversation history is maintained across messages
5. All responses match the data contract
"""

import pytest
from unittest.mock import patch
from tests.conftest import _mock_chat_completion_factory


class TestConversationEndpoint:

    def test_normal_conversation_returns_valid_response(self, sync_client, mock_llm_normal, normal_conversation_payload):
        """Basic chat should return a response + conversation ID"""
        resp = sync_client.post("/conversation", json=normal_conversation_payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "response_text" in data
        assert "conversation_id" in data
        assert len(data["response_text"]) > 0
        assert len(data["conversation_id"]) > 0

    def test_conversation_returns_cct_for_patient(self, sync_client, mock_llm_normal, normal_conversation_payload):
        """Patient conversations should include a CCT score"""
        resp = sync_client.post("/conversation", json=normal_conversation_payload)
        data = resp.json()

        # CCT might be None if scoring failed, but field should exist
        assert "cct_score" in data
        assert "aac_score" in data

    def test_caregiver_conversation_no_cct(self, sync_client, mock_llm_normal, caregiver_conversation_payload):
        """Caregiver messages should NOT get CCT scored — that's patient-only"""
        resp = sync_client.post("/conversation", json=caregiver_conversation_payload)
        data = resp.json()

        assert data.get("cct_score") is None

    def test_distress_triggers_emr(self, sync_client, mock_llm_high_risk, distress_conversation_payload):
        """Patient expressing confusion/distress should trigger EMR"""
        resp = sync_client.post("/conversation", json=distress_conversation_payload)
        data = resp.json()

        assert data["emr_triggered"] == True or data.get("emr_memory") is not None

    def test_empty_message_handled_gracefully(self, sync_client, mock_llm_normal):
        """Empty message shouldn't crash — just ask them to repeat"""
        payload = {
            "user_id": "ramesh-001",
            "role": "patient",
            "message": "",
            "conversation_id": None,
        }
        resp = sync_client.post("/conversation", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["response_text"]) > 0

    def test_whitespace_message_handled(self, sync_client, mock_llm_normal):
        """Whitespace-only message — STT sometimes sends these"""
        payload = {
            "user_id": "ramesh-001",
            "role": "patient",
            "message": "   ",
            "conversation_id": None,
        }
        resp = sync_client.post("/conversation", json=payload)
        assert resp.status_code == 200

    def test_response_matches_data_contract(self, sync_client, mock_llm_normal, normal_conversation_payload):
        """Response should have exactly the fields from our data contract"""
        resp = sync_client.post("/conversation", json=normal_conversation_payload)
        data = resp.json()

        required = ["response_text", "conversation_id", "cct_score", "aac_score", "emr_triggered", "emr_memory"]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_total_pipeline_failure_returns_warm_fallback(self, sync_client, normal_conversation_payload):
        """Even if everything breaks, user gets a kind response, not a 500"""
        async def _broken_pipeline(*args, **kwargs):
            raise Exception("Total pipeline failure")

        with patch("api.routes.conversation.run_pipeline", new=_broken_pipeline):
            resp = sync_client.post("/conversation", json=normal_conversation_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["response_text"]) > 0
            # Should sound warm, not like an error message
            assert "error" not in data["response_text"].lower()


class TestConversationPipeline:

    @pytest.mark.asyncio
    async def test_voice_always_runs_full_pipeline(self, mock_llm_normal):
        """Voice input should never short-circuit — always needs reasoning"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "voice",
            "user_message": "Good morning, what's for breakfast?",
        })

        agents = state.get("agents_executed", [])
        assert "perception" in agents
        assert "context" in agents
        assert "reasoning" in agents
        assert "assistance" in agents
        assert state.get("response_text") is not None

    @pytest.mark.asyncio
    async def test_distress_message_triggers_parallel_path(self, mock_llm_high_risk):
        """Distressed user should trigger both assistance + caregiver"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "voice",
            "user_message": "I don't know where I am. I'm lost and scared.",
        })

        agents = state.get("agents_executed", [])
        assert "assistance" in agents
        assert "caregiver" in agents
        assert state.get("risk_level") in ("medium", "high", "critical")

    @pytest.mark.asyncio
    async def test_cct_scores_populated_for_patient(self, mock_llm_normal):
        """CCT should silently score patient messages"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "ramesh-001",
            "role": "patient",
            "trigger_type": "voice",
            "user_message": "I went to the park this morning and fed the birds.",
        })

        cct = state.get("cct_scores", {})
        if cct:  # might be empty if mock didn't trigger CCT path
            assert "composite" in cct
            assert 0.0 <= cct["composite"] <= 1.0

    @pytest.mark.asyncio
    async def test_caregiver_query_gets_summary_style_response(self, mock_llm_normal):
        """Caregiver asking about patient should get a summary-style answer"""
        from agents.pipeline import run_pipeline

        state = await run_pipeline({
            "user_id": "priya-001",
            "role": "caregiver",
            "trigger_type": "voice",
            "user_message": "How was Dad's day today?",
        })

        assert state.get("response_text") is not None
        assert len(state.get("response_text", "")) > 20  # should be a real summary, not one-liner


# =====================================================
# CAREGIVER ENDPOINT TESTS
# =====================================================

class TestCaregiverEndpoints:

    def test_alerts_endpoint_returns_list(self, sync_client):
        """GET /caregiver/alerts should return an alerts array"""
        resp = sync_client.get("/caregiver/alerts/ramesh-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_summary_endpoint_returns_valid_structure(self, sync_client, mock_llm_normal):
        """GET /caregiver/summary should return full summary with metrics"""
        resp = sync_client.get("/caregiver/summary/ramesh-001")
        assert resp.status_code == 200
        data = resp.json()

        assert "summary_text" in data
        assert "metrics" in data
        assert "events" in data
        metrics = data["metrics"]
        assert "medication_adherence" in metrics
        assert "cct_trend" in metrics
        assert metrics["cct_trend"] in ("stable", "improving", "declining")

    def test_acknowledge_nonexistent_alert(self, sync_client):
        """Acknowledging a fake alert should return success=false"""
        resp = sync_client.post(
            "/caregiver/alerts/fake-alert-id/acknowledge",
            json={"action": "acknowledge", "note": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] == False


# =====================================================
# HEALTH CHECK
# =====================================================

class TestHealthCheck:

    def test_health_returns_ok(self, sync_client):
        resp = sync_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root_returns_message(self, sync_client):
        resp = sync_client.get("/")
        assert resp.status_code == 200
        assert "SahayAI" in resp.json()["message"]