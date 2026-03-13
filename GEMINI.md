# SahayAI - Agentic AI Assistive Platform

SahayAI is an advanced agentic AI platform designed to support people with disabilities and their caregivers. Built by **Team Pied Piper** for the NMIMS Hackathon 2026, it leverages a sophisticated multi-agent pipeline and innovative cognitive tracking to provide personalized, adaptive assistance.

## Project Overview

- **Mission:** Empowering individuals with disabilities through adaptive, emotionally-aware AI companionship and providing caregivers with proactive burnout detection and status monitoring.
- **Core Architecture:** A six-agent pipeline orchestrated by **LangGraph**, integrating real-time perception, RAG-enriched context, and adaptive reasoning.
- **Platform:** 
  - **Backend:** FastAPI (Python) serving as the intelligent core.
  - **Mobile:** Android App (Kotlin/Jetpack Compose) for the user and caregiver interface.
- **Databases:** PostgreSQL (Relational) and ChromaDB (Vector/RAG).

## Tech Stack

### Backend (Python)
- **Framework:** FastAPI
- **Agent Orchestration:** LangGraph (LangChain ecosystem)
- **LLMs:** Groq (primary for speed), OpenAI (Vision/Embeddings)
- **Vector Store:** ChromaDB (for RAG and Emotional Memory Reinforcement)
- **Database:** PostgreSQL (SQLAlchemy/AsyncPG)
- **Machine Learning:** scikit-learn/PyTorch (Wearable sensor classification)
- **Async:** Uvicorn, asyncio

### Android (Kotlin)
- **UI Framework:** Jetpack Compose
- **Dependency Injection:** Hilt
- **Local Database:** Room
- **Networking:** Retrofit + OkHttp + Kotlinx Serialization
- **Hardware Integration:** CameraX, Play Services Location
- **Charts:** Vico Charts

## Six-Agent Pipeline (LangGraph)

The system operates on a stateful pipeline defined in `backend/agents/pipeline.py`:

1.  **Perception** (`perception.py`): Processes camera frames, wearable sensor data, and voice inputs.
2.  **Context** (`context.py`): Performs RAG retrieval from ChromaDB (user profile, routines, past events).
3.  **Reasoning** (`reasoning.py`): Core decision-making engine that adjusts intervention intensity based on the AAC score.
4.  **Assistance** (`assistance.py`): Generates user-facing responses and performs silent CCT scoring.
5.  **Caregiver** (`caregiver.py`): Manages alerts and summaries for the caregiver interface.
6.  **Learning** (`learning.py`): Updates long-term memory and adapts system parameters based on feedback.

## Four Core Innovations

1.  **CCT (Conversational Cognitive Tracking):** Silently scores 6 cognitive dimensions (recall, latency, vocabulary, etc.) on every interaction to monitor cognitive health.
2.  **AAC (Adaptive Autonomy Calibration):** Recalculates a "Cognitive Confidence Score" every 15 minutes to balance system assistance with user autonomy.
3.  **EMR (Emotional Memory Reinforcement):** Retrieves personal memories (photos, stories) as calming interventions when user distress is detected.
4.  **CBD (Caregiver Burnout Detection):** Passively monitors caregiver behavioral signals to identify potential burnout before it occurs.

## Building and Running

### Backend

```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload --port 8000

# Run tests
pytest
```

### Android App

- **Build Tool:** Gradle (Kotlin DSL)
- **Minimum SDK:** 26 (Android 8.0+)
- **Target SDK:** 35 (Android 15)
- **Running:** Use Android Studio or run `./gradlew installDebug` with a device connected.
- **Mock Data:** The debug build defaults to `USE_MOCK_DATA = true` for testing without a live backend.

## Development Conventions

- **API Routes:** Located in `backend/api/routes/`. Each module corresponds to a specific functional area (conversation, scene, status, etc.).
- **Models & Schemas:** Defined in `backend/api/models/`. Pydantic is used for request/response validation.
- **Agent State:** The shared pipeline state is defined in `backend/agents/state.py`.
- **Innovations:** Core logic for CCT, AAC, EMR, and CBD is encapsulated in `backend/innovations/`.
- **Android Architecture:** Follows modern Android development (MVVM, UDF with Compose, Hilt for DI).

## Key Files

- `backend/main.py`: Entry point for the FastAPI application.
- `backend/agents/pipeline.py`: Orchestration logic for the multi-agent system.
- `android/app/src/main/java/com/sahayai/android/MainActivity.kt`: Entry point for the Android app.
- `docs/SahayAI_Blueprint_v2.docx`: Detailed architectural design documentation.
- `AGENTS.md`: Technical guide for AI-assisted development.
