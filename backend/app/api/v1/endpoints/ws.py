import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_service import ws_manager
from app.core.logging import logger

router = APIRouter(tags=["Real-Time WebSockets"])


@router.websocket("/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    event_id: int = Query(1, description="Event ID for seat map subscription"),
):
    """
    Real-Time WebSocket Fan-Out Endpoint (docs/api-contract.md §8).
    URL: ws://<host>/ws/events?event_id={event_id}

    Lifecycle:
    1. Connects & registers client to event channel.
    2. Sends immediate initial seat status SNAPSHOT with current sequence number.
    3. Streams incremental SEAT_STATUS_CHANGE events with monotonic sequence numbers.
    4. Handles client RESYNC requests for gap recovery.
    5. Handles PING / PONG heartbeat messages.
    6. Automatically cleans up connections on disconnect.
    """
    await ws_manager.connect(event_id, websocket)

    try:
        # Send initial full SNAPSHOT on connection
        current_seq = await ws_manager.get_current_seq(event_id)
        seats = await ws_manager.get_snapshot_data(event_id)
        initial_snapshot = {
            "type": "SNAPSHOT",
            "seq": current_seq,
            "event_id": event_id,
            "seats": seats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await websocket.send_text(json.dumps(initial_snapshot))

        # Inbound message loop (RESYNC, PING, etc.)
        while True:
            raw_text = await websocket.receive_text()
            await ws_manager.handle_client_message(websocket, event_id, raw_text)

    except WebSocketDisconnect:
        ws_manager.disconnect(event_id, websocket)
    except Exception as exc:
        logger.debug(f"[WebSocket] Connection closed with exception: {exc}")
        ws_manager.disconnect(event_id, websocket)
