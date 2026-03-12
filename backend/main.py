"""
SahayAI Backend — FastAPI Entry Point
======================================
This is the main server file for SahayAI. It initializes the FastAPI app,
mounts all route modules, sets up CORS so the Flutter app can talk to us,
and handles startup/shutdown events for database and ChromaDB connections.

Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables from .env file FIRST, before anything else
# needs API keys or DB URLs. This must happen before importing route modules
# because they may initialize clients at import time.
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Import all route modules — each one owns a specific API surface area.
# We import the routers here and mount them below in the app.
# ---------------------------------------------------------------------------
from api.routes.scene import router as scene_router
from api.routes.conversation import router as conversation_router
from api.routes.status import router as status_router
from api.routes.caregiver import router as caregiver_router
from api.routes.reminders import router as reminders_router
from api.routes.websocket import router as websocket_router

# ---------------------------------------------------------------------------
# Configure logging — we want structured logs so we can debug agent decisions
# during the hackathon demo. INFO level shows the flow, DEBUG shows payloads.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sahayai")


# ---------------------------------------------------------------------------
# Lifespan handler — runs once on startup and once on shutdown.
# We use this to initialize expensive resources (DB pool, ChromaDB client,
# load the ML classifier into memory) so they're ready before the first
# request hits. This avoids cold-start latency during the demo.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: connect to PostgreSQL, initialize ChromaDB, load classifier.
    Shutdown: close DB connections cleanly so we don't leak resources.
    """
    logger.info("=" * 60)
    logger.info("  SahayAI Backend Starting Up")
    logger.info("=" * 60)

    # --- Startup Phase ---

    # 1. Verify critical environment variables are set so we fail fast
    #    rather than getting a cryptic error on the first API call
    required_env_vars = ["GROQ_API_KEY"]
    missing = [var for var in required_env_vars if not os.getenv(var)]
    if missing:
        logger.warning(
            f"Missing environment variables: {missing}. "
            f"Some features will use fallback models or be disabled."
        )

    # 2. Initialize the database connection pool
    #    We import and call this here so the pool is ready before requests
    try:
        from api.models.database import init_db
        await init_db()
        logger.info("PostgreSQL connection pool initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL init failed: {e}. Running without DB — demo mode.")

    # 3. Initialize ChromaDB client and verify collections exist
    #    ChromaDB is our RAG vector store — it holds Ramesh's profile,
    #    routines, past events, caregiver prefs, and EMR memories
    try:
        from rag.chromadb_setup import init_chromadb
        init_chromadb()
        logger.info("ChromaDB initialized with all collections")
    except Exception as e:
        logger.warning(f"ChromaDB init failed: {e}. RAG features will be limited.")

    # 4. Load the wearable classifier (Random Forest) into memory
    #    This is a ~50KB joblib file that classifies smartwatch data into
    #    normal/fall/wandering/distress. Loading once here avoids repeated
    #    disk reads on every /check-status call
    try:
        from classifier.predict import load_classifier
        load_classifier()
        logger.info("Wearable classifier loaded into memory")
    except Exception as e:
        logger.warning(f"Classifier load failed: {e}. /check-status will use rule-based fallback.")

    # 5. Start the background scheduler — handles auto-summaries,
    #    AAC recalculation every 15 min, missed medication detection
    try:
        from utils.scheduler import start_scheduler
        start_scheduler()
        logger.info("Background scheduler started (summaries, AAC, reminders)")
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}. Background tasks disabled.")

    logger.info("SahayAI Backend ready to serve requests")
    logger.info("=" * 60)

    # --- Hand control to the app (it runs until shutdown) ---
    yield

    # --- Shutdown Phase ---
    logger.info("SahayAI Backend shutting down...")
    try:
        from api.models.database import close_db
        await close_db()
        logger.info("Database connections closed")
    except Exception:
        pass

    try:
        from utils.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    try:
        from utils.llm import close_llm_clients
        await close_llm_clients()
    except Exception:
        pass

    logger.info("Goodbye!")


# ---------------------------------------------------------------------------
# Create the FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SahayAI",
    description=(
        "Agentic AI assistive platform for persons with disabilities "
        "and their caregivers. Built by Team Pied Piper at NMIMS Hackathon 2026."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
from api.dependencies import global_exception_handler

app.add_exception_handler(Exception, global_exception_handler)

# CORS Middleware — allows the Flutter app (running on any port/device) to
# make requests to this backend. We allow all origins during hackathon dev;
# in production you'd lock this down to your app's domain.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Flutter app can run on any port/emulator
    allow_credentials=True,
    allow_methods=["*"],          # Allow GET, POST, PUT, DELETE, OPTIONS, etc.
    allow_headers=["*"],          # Allow Authorization, Content-Type, etc.
)

# ---------------------------------------------------------------------------
# Mount all route modules under their respective prefixes.
# Each router handles a specific part of the API surface:
#   - /analyze-scene       → camera frame → AI scene description
#   - /conversation        → free-form chat (user or caregiver)
#   - /check-status        → wearable data → risk classification
#   - /caregiver/*         → alerts, summaries, acknowledgments
#   - /patient/reminders/* → medication & routine reminders
#   - /ws/*                → real-time WebSocket alert stream
# ---------------------------------------------------------------------------
app.include_router(scene_router,        tags=["Scene Analysis"])
app.include_router(conversation_router, tags=["Conversation"])
app.include_router(status_router,       tags=["Wearable Status"])
app.include_router(caregiver_router,    tags=["Caregiver"])
app.include_router(reminders_router,    tags=["Reminders"])
app.include_router(websocket_router,    tags=["WebSocket"])


# ---------------------------------------------------------------------------
# Health check endpoint — quick way to verify the server is alive.
# The Flutter app can ping this on startup to confirm backend connectivity
# before sending real requests. Also useful for docker health checks.
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """
    Returns a simple status object so the Flutter app knows the backend
    is alive and which services initialized successfully. The frontend
    can use this to show a 'connected' indicator on the dashboard.
    """
    return {
        "status": "healthy",
        "service": "SahayAI Backend",
        "version": "1.0.0",
        "team": "Pied Piper",
    }


# ---------------------------------------------------------------------------
# Root endpoint — friendly message when someone hits the base URL.
# Mostly for when you open http://localhost:8000 in a browser during dev.
# ---------------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "message": "SahayAI is running. Visit /docs for API documentation.",
        "docs_url": "/docs",
    }