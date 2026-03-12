"""
Shared fixtures for all SahayAI tests.
Sets up a test DB, mock LLM clients, and reusable test data
so individual tests don't have to repeat boilerplate.
"""

import os
import sys
import uuid
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Make sure imports work from the backend directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


# =====================================================
# EVENT LOOP — needed because we're mixing async DB + async tests
# =====================================================

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =====================================================
# MOCK LLM — we don't want to burn Groq rate limits in tests.
# Every test gets a fake LLM that returns predictable responses
# based on what kind of call it is.
# =====================================================

MOCK_REASONING_RESPONSE = '''{
    "request_type": "chat",
    "risk_level": "none",
    "alert_caregiver": false,
    "alert_priority": "routine",
    "alert_message": null,
    "trigger_emr": false,
    "response_text": "Good morning! Everything looks great today.",
    "reasoning": "Normal conversation, no risk detected."
}'''

MOCK_REASONING_HIGH_RISK = '''{
    "request_type": "distress",
    "risk_level": "high",
    "alert_caregiver": true,
    "alert_priority": "urgent",
    "alert_message": "Patient appears confused and distressed.",
    "trigger_emr": true,
    "response_text": "It's okay, I'm here with you.",
    "reasoning": "User expressed confusion about location. High risk."
}'''

MOCK_SCENE_RESPONSE = '''{
    "scene_description": "You are on a sidewalk next to a park. There is a bench to your left and a road ahead.",
    "obstacles": [
        {"type": "road", "distance": "10 meters", "direction": "ahead"},
        {"type": "bench", "distance": "2 meters", "direction": "left"}
    ],
    "guidance_text": "The path ahead is mostly clear. There is a road about 10 meters ahead — be cautious.",
    "risk_level": "low"
}'''

MOCK_CCT_RESPONSE = '''{
    "recall_accuracy": 0.75,
    "response_latency": 0.80,
    "vocabulary_richness": 0.70,
    "temporal_orientation": 0.65,
    "narrative_coherence": 0.78,
    "semantic_consistency": 0.72,
    "composite": 0.73
}'''

MOCK_SUMMARY_RESPONSE = (
    "Ramesh had a calm day overall. He took his morning medication on time "
    "and had a pleasant conversation about the weather. His cognitive scores "
    "remained stable. No alerts were triggered. Tomorrow, consider reminding "
    "him about his evening walk — he missed it today."
)

MOCK_ASSISTANCE_RESPONSE = "Good morning, Ramesh! How are you feeling today? Your morning medication is coming up soon."

MOCK_CAREGIVER_ALERT = "ALERT: Ramesh appears confused about his location.\nACTION: Check on him or call to help orient him."


def _mock_chat_completion_factory(scenario: str = "normal"):
    """
    Returns a mock chat_completion function that gives different
    responses based on the model_preference parameter, simulating
    how different agents in the pipeline get different models.
    """
    async def mock_chat(messages, model_preference="fast", temperature=0.3, max_tokens=1024):
        # Figure out what agent is calling based on the messages content
        system_msg = messages[0].get("content", "") if messages else ""
        user_msg = messages[-1].get("content", "") if messages else ""

        # CCT scoring call
        if "recall_accuracy" in user_msg or "cognitive" in user_msg.lower():
            return MOCK_CCT_RESPONSE

        # Reasoning agent call
        if "Reasoning Agent" in system_msg or model_preference == "quality":
            if scenario == "high_risk":
                return MOCK_REASONING_HIGH_RISK
            # Check if user message has distress keywords
            if any(word in user_msg.lower() for word in ["lost", "don't know", "scared", "confused"]):
                return MOCK_REASONING_HIGH_RISK
            return MOCK_REASONING_RESPONSE

        # Caregiver agent calls
        if "Caregiver" in system_msg or "caregiver" in system_msg.lower():
            if "summary" in user_msg.lower() or "daily" in user_msg.lower():
                return MOCK_SUMMARY_RESPONSE
            return MOCK_CAREGIVER_ALERT

        # Emotion detection — single word response
        if "Classify the emotion" in user_msg:
            if scenario == "high_risk":
                return "distressed"
            return "calm"

        # Default — assistance agent response
        return MOCK_ASSISTANCE_RESPONSE

    return mock_chat


async def _mock_vision_completion(base64_image, prompt, temperature=0.3, max_tokens=1024):
    """Mock vision model — always returns a valid scene analysis"""
    return MOCK_SCENE_RESPONSE


@pytest.fixture
def mock_llm_normal():
    """Patches LLM calls to return normal/safe responses"""
    with patch("utils.llm.chat_completion", new=_mock_chat_completion_factory("normal")), \
         patch("utils.llm.vision_completion", new=_mock_vision_completion):
        yield


@pytest.fixture
def mock_llm_high_risk():
    """Patches LLM calls to return high-risk/distress responses"""
    with patch("utils.llm.chat_completion", new=_mock_chat_completion_factory("high_risk")), \
         patch("utils.llm.vision_completion", new=_mock_vision_completion):
        yield


# =====================================================
# MOCK CLASSIFIER — so tests don't need model.joblib
# =====================================================

@pytest.fixture(autouse=True)
def mock_classifier():
    """Always mock the classifier so tests work without a trained model"""
    with patch("classifier.predict._model_loaded", False):
        yield


# =====================================================
# MOCK CHROMADB — tests shouldn't need a real vector store
# =====================================================

@pytest.fixture(autouse=True)
def mock_chromadb():
    """Mock ChromaDB so tests don't need seeded collections"""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    mock_collection.count.return_value = 0

    with patch("rag.chromadb_setup.get_collection", return_value=mock_collection), \
         patch("rag.chromadb_setup.init_chromadb"):
        yield


# =====================================================
# APP + CLIENT — test against the real FastAPI app
# =====================================================

@pytest_asyncio.fixture
async def async_client():
    """
    Async HTTP client that talks to the real FastAPI app.
    Uses the actual routes, middleware, and error handling
    but with mocked LLM and DB underneath.
    """
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_client():
    """Sync test client for simple endpoint checks"""
    from main import app
    return TestClient(app)


# =====================================================
# TEST DATA — reusable payloads for common test scenarios
# =====================================================

@pytest.fixture
def ramesh_user_id():
    return "ramesh-001"


@pytest.fixture
def priya_caregiver_id():
    return "priya-001"


@pytest.fixture
def normal_wearable_data():
    """Ramesh sitting at home, everything fine"""
    return {
        "user_id": "ramesh-001",
        "wearable_data": {
            "heart_rate": 72,
            "accelerometer": {"x": 0.1, "y": 0.2, "z": 9.8},
            "steps": 5,
            "gps": {"lat": 19.1136, "lng": 72.8697},
        },
        "window_seconds": 30,
    }


@pytest.fixture
def fall_wearable_data():
    """Ramesh fell — huge accel spike + elevated heart rate"""
    return {
        "user_id": "ramesh-001",
        "wearable_data": {
            "heart_rate": 110,
            "accelerometer": {"x": 15.0, "y": 20.0, "z": 25.0},
            "steps": 0,
            "gps": {"lat": 19.1136, "lng": 72.8697},
        },
        "window_seconds": 30,
    }


@pytest.fixture
def wandering_wearable_data():
    """Ramesh is 1.3km from home, walking continuously"""
    return {
        "user_id": "ramesh-001",
        "wearable_data": {
            "heart_rate": 85,
            "accelerometer": {"x": 1.2, "y": 0.8, "z": 9.9},
            "steps": 45,
            "gps": {"lat": 19.1250, "lng": 72.8800},
        },
        "window_seconds": 30,
    }


@pytest.fixture
def distress_wearable_data():
    """Ramesh's heart rate is through the roof, not moving"""
    return {
        "user_id": "ramesh-001",
        "wearable_data": {
            "heart_rate": 145,
            "accelerometer": {"x": 0.05, "y": 0.1, "z": 9.8},
            "steps": 0,
            "gps": {"lat": 19.1136, "lng": 72.8697},
        },
        "window_seconds": 30,
    }


@pytest.fixture
def sample_camera_payload():
    """Fake base64 image — just needs to be long enough to pass validation"""
    import base64
    fake_image = base64.b64encode(b"x" * 200).decode()
    return {
        "image": fake_image,
        "location": {"lat": 19.1136, "lng": 72.8697},
        "user_id": "ramesh-001",
    }


@pytest.fixture
def normal_conversation_payload():
    return {
        "user_id": "ramesh-001",
        "role": "patient",
        "message": "Good morning, what do I have to do today?",
        "conversation_id": None,
    }


@pytest.fixture
def distress_conversation_payload():
    return {
        "user_id": "ramesh-001",
        "role": "patient",
        "message": "I don't know where I am. Everything looks strange. I'm scared.",
        "conversation_id": None,
    }


@pytest.fixture
def caregiver_conversation_payload():
    return {
        "user_id": "priya-001",
        "role": "caregiver",
        "message": "How was Dad's day today?",
        "conversation_id": None,
    }