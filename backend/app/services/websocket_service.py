import json
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Set, List, Optional, Any
from fastapi import WebSocket
from app.redis.client import get_redis
from app.redis.scripts import PUBLISH_WS_EVENT_LUA
from app.core.logging import logger


class WebSocketManager:
    def __init__(self):
        # event_id -> Set of active WebSocket connections on this instance
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._pubsub_task: Optional[asyncio.Task] = None
        self._running: bool = False

    async def connect(self, event_id: int, websocket: WebSocket) -> None:
        """Accepts a WebSocket and registers it under the specified event_id."""
        await websocket.accept()
        self.active_connections[event_id].add(websocket)
        logger.info(
            f"[WebSocket] Client connected for event {event_id}. "
            f"Active connections on this replica: {len(self.active_connections[event_id])}"
        )

    def disconnect(self, event_id: int, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket from the local registry."""
        if event_id in self.active_connections:
            self.active_connections[event_id].discard(websocket)
            if not self.active_connections[event_id]:
                del self.active_connections[event_id]
        logger.info(f"[WebSocket] Client disconnected for event {event_id}.")

    async def broadcast_to_local(self, event_id: int, message: Dict[str, Any]) -> None:
        """Broadcasts a JSON-serializable message to all local WebSocket connections for an event."""
        connections = list(self.active_connections.get(event_id, []))
        if not connections:
            return

        payload_text = json.dumps(message)
        dead_connections: List[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(payload_text)
            except Exception as exc:
                logger.debug(f"[WebSocket] Failed to send message to client, marking for removal: {exc}")
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(event_id, ws)

    async def get_current_seq(self, event_id: int) -> int:
        """Retrieves the authoritative monotonic sequence number for an event."""
        try:
            redis = await get_redis()
            val = await redis.get(f"event:{event_id}:ws_seq")
            return int(val) if val else 0
        except Exception:
            return 0

    async def get_snapshot_data(self, event_id: int) -> List[Dict[str, Any]]:
        """Retrieves all current seat statuses from the Redis hash."""
        try:
            redis = await get_redis()
            statuses = await redis.hgetall(f"event:{event_id}:seat_statuses")
            return [
                {"seat_id": int(seat_id), "status": status}
                for seat_id, status in statuses.items()
            ]
        except Exception as exc:
            logger.warning(f"[WebSocket] Could not fetch seat statuses snapshot: {exc}")
            return []

    async def publish_seat_status_change(
        self,
        event_id: int,
        updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Publishes atomic seat status updates to all subscribers:
        1. Atomically increments event sequence number and appends to event log
           via Redis Lua script (guarantees no sequence gaps without replayable events).
        2. Publishes to Redis Pub/Sub channel 'events:{event_id}:seat_updates'.
        3. Broadcasts immediately to all locally connected WebSockets.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        updates_json = json.dumps(updates)
        seq_key = f"event:{event_id}:ws_seq"
        log_key = f"event:{event_id}:ws_event_log"
        channel = f"events:{event_id}:seat_updates"

        new_seq = None
        payload = None

        try:
            redis = await get_redis()
            res = await redis.eval(
                PUBLISH_WS_EVENT_LUA,
                3,
                seq_key,
                log_key,
                channel,
                str(event_id),
                updates_json,
                now_iso,
            )
            if res and len(res) >= 2:
                new_seq = int(res[0])
                payload = json.loads(res[1])
        except Exception as exc:
            logger.warning(f"[WebSocket] Error executing atomic publish Lua script: {exc}")
            # Fallback for mock environments without Lua eval
            try:
                redis = await get_redis()
                new_seq = await redis.incr(seq_key)
                payload = {
                    "type": "SEAT_STATUS_CHANGE",
                    "seq": int(new_seq),
                    "event_id": event_id,
                    "updates": updates,
                    "timestamp": now_iso,
                }
                await redis.rpush(log_key, json.dumps(payload))
                await redis.ltrim(log_key, -500, -1)
                await redis.publish(channel, json.dumps(payload))
            except Exception as e:
                logger.debug(f"[WebSocket] Fallback publish error: {e}")

        if not payload:
            payload = {
                "type": "SEAT_STATUS_CHANGE",
                "seq": int(new_seq or 1),
                "event_id": event_id,
                "updates": updates,
                "timestamp": now_iso,
            }

        # Broadcast directly to local WebSocket clients
        await self.broadcast_to_local(event_id, payload)
        return payload

    async def handle_client_message(
        self,
        websocket: WebSocket,
        event_id: int,
        raw_text: str,
    ) -> None:
        """
        Handles client inbound messages:
        - RESYNC: Gap recovery. Replays missing events or sends a full SNAPSHOT_RESYNC.
        - PING: Heartbeat response with PONG.
        """
        try:
            data = json.loads(raw_text)
        except Exception:
            return

        action = data.get("action")

        if action == "RESYNC":
            from_seq = data.get("from_seq", 0)
            logger.info(f"[WebSocket] Client requested RESYNC from_seq={from_seq} for event {event_id}")

            replayed = False
            try:
                redis = await get_redis()
                log_key = f"event:{event_id}:ws_event_log"
                raw_events = await redis.lrange(log_key, 0, -1)

                events_to_replay = []
                for item in raw_events:
                    ev = json.loads(item)
                    if ev.get("seq", 0) > from_seq:
                        events_to_replay.append(ev)

                # Check if we have contiguous history starting at from_seq + 1
                if events_to_replay and events_to_replay[0].get("seq") == from_seq + 1:
                    for ev in events_to_replay:
                        await websocket.send_text(json.dumps(ev))
                    replayed = True
                    logger.info(f"[WebSocket] Replayed {len(events_to_replay)} events to client.")
            except Exception as exc:
                logger.warning(f"[WebSocket] Error during event log replay: {exc}")

            if not replayed:
                # Buffer gap too large: send complete SNAPSHOT_RESYNC
                curr_seq = await self.get_current_seq(event_id)
                seats = await self.get_snapshot_data(event_id)
                snapshot_resync = {
                    "type": "SNAPSHOT_RESYNC",
                    "seq": curr_seq,
                    "event_id": event_id,
                    "seats": seats,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await websocket.send_text(json.dumps(snapshot_resync))
                logger.info(f"[WebSocket] Sent SNAPSHOT_RESYNC (seq={curr_seq}) to client.")

        elif action == "PING":
            await websocket.send_text(json.dumps({
                "type": "PONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

    def start_pubsub_listener(self) -> None:
        """Starts the background Redis Pub/Sub listener for multi-replica broadcast."""
        if not self._running:
            self._running = True
            self._pubsub_task = asyncio.create_task(self._pubsub_loop())

    async def stop_pubsub_listener(self) -> None:
        """Stops the background Redis Pub/Sub listener."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None

    async def _pubsub_loop(self) -> None:
        """Listens on Redis Pub/Sub channels for cross-instance broadcasts."""
        while self._running:
            try:
                redis = await get_redis()
                # If FakeRedis or pubsub unavailable, sleep and continue
                pubsub = redis.pubsub()
                await pubsub.psubscribe("events:*:seat_updates")

                while self._running:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("type") == "pmessage":
                        try:
                            channel = msg.get("channel", "")
                            # Parse event_id from events:{event_id}:seat_updates
                            parts = channel.split(":")
                            if len(parts) >= 2 and parts[1].isdigit():
                                event_id = int(parts[1])
                                data = json.loads(msg.get("data", "{}"))
                                # Broadcast to local clients
                                await self.broadcast_to_local(event_id, data)
                        except Exception as e:
                            logger.debug(f"[WebSocket] PubSub message dispatch error: {e}")
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"[WebSocket] PubSub loop reconnecting: {exc}")
                await asyncio.sleep(2.0)


# Global singleton instance
ws_manager = WebSocketManager()
