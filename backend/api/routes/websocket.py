"""
WS /ws/alerts/{caregiver_id} — Real-time WebSocket connection for pushing
alerts to the caregiver's Flutter app the instant they're generated,
without polling. The Flutter app opens this connection on the caregiver
dashboard and keeps it alive.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

router = APIRouter()
logger = logging.getLogger("sahayai.ws")

# ---------------------------------------------------------------------------
# Store active WebSocket connections so we can push alerts from any agent.
# Key: caregiver_id, Value: WebSocket connection.
# In production you'd use Redis pub/sub, but for hackathon demo this works.
# ---------------------------------------------------------------------------
active_connections: dict[str, WebSocket] = {}


@router.websocket("/ws/alerts/{caregiver_id}")
async def websocket_alerts(websocket: WebSocket, caregiver_id: str):
    """
    Accepts a WebSocket connection from a caregiver's device and keeps
    it open for real-time alert delivery. When any agent generates a
    caregiver alert, it calls broadcast_alert() which pushes the JSON
    payload through this connection instantly.
    """
    await websocket.accept()
    active_connections[caregiver_id] = websocket
    logger.info(f"Caregiver {caregiver_id} connected via WebSocket")

    try:
        # Keep the connection alive by listening for any incoming messages
        # (the client might send a heartbeat ping or acknowledgments)
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from {caregiver_id}: {data}")
    except WebSocketDisconnect:
        # Clean up when the caregiver closes the app or loses connection
        del active_connections[caregiver_id]
        logger.info(f"Caregiver {caregiver_id} disconnected")


async def broadcast_alert(caregiver_id: str, alert_payload: dict):
    """
    Called by agents (Caregiver Agent, Reasoning Agent) to push an alert
    to a specific caregiver's open WebSocket connection in real time.
    If the caregiver isn't connected, the alert is stored in PostgreSQL
    and they'll see it when they next open the app.
    """
    if caregiver_id in active_connections:
        websocket = active_connections[caregiver_id]
        # Wrap in WsAlertMessage shape expected by Android: {type, message, alert}
        ws_message = {
            "type": "alert",
            "message": alert_payload.get("message", alert_payload.get("description", "Alert")),
            "alert": alert_payload,
        }
        await websocket.send_json(ws_message)
        logger.info(f"Alert pushed to caregiver {caregiver_id}")
    else:
        logger.info(f"Caregiver {caregiver_id} not connected. Alert saved to DB only.")