# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**SahayAI** is an agentic AI assistive intelligence platform for people with disabilities and their caregivers. It combines a FastAPI Python backend with a Flutter mobile app (not in this repo), ChromaDB RAG, and PostgreSQL.

**Current state:** All implementation files are empty skeletons. The full architectural design is documented in `docs/SahayAI_Blueprint_v2.docx`.

## Tech Stack

- **Backend:** FastAPI + LangGraph (agent orchestration)
- **LLMs:** Codex Sonnet (reasoning/caregiver), Codex Haiku (user-facing, <1s latency), GPT-4o Vision (scene analysis)
- **Databases:** PostgreSQL (relational) + ChromaDB (vector/RAG)
- **Embeddings:** OpenAI `text-embedding-3-small`
- **Classifier:** scikit-learn/PyTorch for wearable sensor event detection
- **Speech:** Whisper STT + platform TTS

## Commands

```bash
# Setup
cd backend && pip install -r requirements.txt

# Run backend
uvicorn backend.main:app --reload --port 8000

# Docker (once configured)
docker-compose up

# Run single test
pytest backend/tests/test_<module>.py::test_<name> -v

# Run all tests
pytest backend/ -v --cov=backend --cov-report=term-missing
```

## Architecture

### Six-Agent Pipeline (LangGraph)

```
PERCEPTION → CONTEXT → REASONING → ASSISTANCE (+ CCT + EMR) / CAREGIVER (+ CBD) → LEARNING
```

- **Perception** (`agents/perception.py`): Unifies camera, wearable, GPS, voice inputs; detects emotions
- **Context** (`agents/context.py`): RAG enrichment from ChromaDB (profile, routines, AAC score, CCT history)
- **Reasoning** (`agents/reasoning.py`): Core decisions; intervention intensity modulated by AAC score
- **Assistance** (`agents/assistance.py`): User-facing Codex Haiku responses + silent CCT scoring + EMR trigger
- **Caregiver** (`agents/caregiver.py`): Alerts/summaries for caregivers + CBD burnout detection
- **Learning** (`agents/learning.py`): Updates RAG, AAC params, EMR weights, CBD thresholds from feedback
- **Pipeline** (`agents/pipeline.py`): LangGraph orchestration + state routing
- **State** (`agents/state.py`): Shared agent state definition

### Four Core Innovations

1. **CCT** (`innovations/cct.py`) — Conversational Cognitive Tracking: scores 6 dimensions (recall, latency, vocabulary, temporal orientation, narrative coherence, semantic consistency) on every conversation turn to produce a continuous cognitive curve
2. **AAC** (`innovations/aac.py`) — Adaptive Autonomy Calibration: computes a 0-100 Cognitive Confidence Score every 15 minutes; high score → system backs off, low score → increased assistance
3. **EMR** (`innovations/emr.py`) — Emotional Memory Reinforcement: when distress detected, retrieves semantically-matched personal memories (photos, songs, stories) from ChromaDB as calming intervention
4. **CBD** (`innovations/cbd.py`) — Caregiver Burnout Detection: tracks alert response times, tone shifts, login frequency over 7-day rolling windows to detect burnout before breakdown

### API Routes

| Route | File | Purpose |
|-------|------|---------|
| `POST /conversation` | `routes/conversation.py` | Primary user interaction endpoint |
| `GET/POST /caregiver` | `routes/caregiver.py` | Caregiver dashboard queries |
| `POST /scene` | `routes/scene.py` | Camera frame → GPT-4o Vision analysis |
| `POST /reminders` | `routes/reminders.py` | Medication/routine reminders |
| `GET /status` | `routes/status.py` | Health check |
| `WS /ws` | `routes/websocket.py` | Real-time caregiver alerts |

### RAG Structure (ChromaDB)

Collections: user profiles, daily routines, past events, EMR memories (photos/songs/stories)

### Wearable Classifier

4-class event detection: `Normal / Fall / Wandering / Distress` — trained on synthetic wearable sensor data via `demo/generate_wearable_data.py` + `demo/train_classifier.py`

## Demo Scenario

`demo/scenario_ramesh_day.py` — end-to-end walkthrough for the "Ramesh" demo persona (profile in `demo/sample_data/`). Run this to validate the full pipeline.

## Key Design Decisions

- Codex **Haiku** for all user-facing responses (latency); Codex **Sonnet** for reasoning/CCT scoring/caregiver summaries
- CCT scoring runs **silently** inside AssistanceAgent — never visible to the user
- AAC score is recalculated every 15 minutes and controls Reasoning Agent thresholds
- EMR retrieval uses **semantic similarity + emotional state + user preferences** (not just keywords)
- CBD operates on **passive behavioral signals** — no additional burden on caregivers
