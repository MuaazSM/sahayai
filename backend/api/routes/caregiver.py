"""
Caregiver-facing endpoints:
  GET  /caregiver/alerts/{patient_id}       — fetch alert feed
  GET  /caregiver/summary/{patient_id}      — AI-generated daily summary
  POST /caregiver/alerts/{alert_id}/acknowledge — mark alert as handled
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/caregiver/alerts/{patient_id}")
async def get_alerts(patient_id: str):
    # TODO: Muaaz — query PostgreSQL alerts table
    return {"alerts": []}


@router.get("/caregiver/summary/{patient_id}")
async def get_summary(patient_id: str):
    # TODO: Muaaz — generate summary via Caregiver Agent
    return {
        "summary_text": "Ramesh had a calm day. All medications taken on time.",
        "date": "2026-03-12",
        "metrics": {
            "medication_adherence": 1.0,
            "steps": 3200,
            "alerts_count": 0,
            "avg_aac_score": 75,
            "cct_trend": "stable",
        },
        "events": [],
        "cct_scores": [],
    }


@router.post("/caregiver/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: dict):
    # TODO: Muaaz — update alert status in PostgreSQL
    return {"success": True, "updated_alert": {}}