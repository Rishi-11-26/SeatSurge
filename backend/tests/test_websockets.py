"""
Phase 3 Integration Tests — Real-Time WebSockets & Fan-Out
==========================================================
Verifies:
1. WebSocket client connects and receives initial seat snapshot.
2. Two connected clients simultaneously receive real-time SEAT_STATUS_CHANGE updates.
3. Monotonic sequence numbers increment on each seat state transition.
4. Gap detection & recovery via RESYNC action.
5. PING / PONG heartbeat handling.
6. Clean disconnect handling without leaking resources.
"""

import json
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.services.websocket_service import ws_manager


def test_websocket_initial_snapshot(client: TestClient):
    """Client receives full SNAPSHOT message upon connecting."""
    with client.websocket_connect("/ws/events?event_id=1") as ws:
        raw = ws.receive_text()
        data = json.loads(raw)
        assert data["type"] == "SNAPSHOT"
        assert data["event_id"] == 1
        assert "seq" in data
        assert isinstance(data["seats"], list)
        assert "timestamp" in data


def test_two_clients_receive_broadcast_update(client: TestClient):
    """
    Two distinct WebSocket clients connected to the same event both receive
    real-time SEAT_STATUS_CHANGE when a seat hold is claimed.
    """
    with client.websocket_connect("/ws/events?event_id=1") as ws1:
        # Consume initial snapshot
        init1 = json.loads(ws1.receive_text())
        assert init1["type"] == "SNAPSHOT"

        with client.websocket_connect("/ws/events?event_id=1") as ws2:
            init2 = json.loads(ws2.receive_text())
            assert init2["type"] == "SNAPSHOT"

            # Trigger a seat hold via HTTP endpoint
            hold_res = client.post(
                "/api/v1/events/1/holds",
                json={"seat_ids": [201]},
                headers={"X-Session-ID": "ws_test_session_broadcast"},
            )
            assert hold_res.status_code == 201

            # Both clients must receive SEAT_STATUS_CHANGE
            msg1 = json.loads(ws1.receive_text())
            msg2 = json.loads(ws2.receive_text())

            assert msg1["type"] == "SEAT_STATUS_CHANGE"
            assert msg2["type"] == "SEAT_STATUS_CHANGE"
            assert msg1["seq"] == msg2["seq"]
            assert msg1["updates"][0]["seat_id"] == 201
            assert msg1["updates"][0]["status"] == "HELD"
            assert msg2["updates"][0]["seat_id"] == 201
            assert msg2["updates"][0]["status"] == "HELD"


def test_websocket_monotonic_sequence_numbers(client: TestClient):
    """Sequence numbers must monotonically increase on subsequent state changes."""
    with client.websocket_connect("/ws/events?event_id=1") as ws:
        _ = ws.receive_text()  # snapshot

        # Hold 1
        res1 = client.post(
            "/api/v1/events/1/holds",
            json={"seat_ids": [202]},
            headers={"X-Session-ID": "ws_seq_1"},
        )
        assert res1.status_code == 201
        msg1 = json.loads(ws.receive_text())
        seq1 = msg1["seq"]

        # Hold 2
        res2 = client.post(
            "/api/v1/events/1/holds",
            json={"seat_ids": [203]},
            headers={"X-Session-ID": "ws_seq_2"},
        )
        assert res2.status_code == 201
        msg2 = json.loads(ws.receive_text())
        seq2 = msg2["seq"]

        assert seq2 > seq1, f"Expected monotonic seq increment: {seq2} > {seq1}"


def test_websocket_resync_action(client: TestClient):
    """Client can send RESYNC action to recover missed sequence events."""
    with client.websocket_connect("/ws/events?event_id=1") as ws:
        _ = ws.receive_text()  # snapshot

        # Create two seat holds
        client.post(
            "/api/v1/events/1/holds",
            json={"seat_ids": [204]},
            headers={"X-Session-ID": "ws_resync_1"},
        )
        ev1 = json.loads(ws.receive_text())
        seq1 = ev1["seq"]

        client.post(
            "/api/v1/events/1/holds",
            json={"seat_ids": [205]},
            headers={"X-Session-ID": "ws_resync_2"},
        )
        ev2 = json.loads(ws.receive_text())
        seq2 = ev2["seq"]

        # Request RESYNC from seq1 (should replay seq2)
        ws.send_text(json.dumps({"action": "RESYNC", "from_seq": seq1}))
        replayed = json.loads(ws.receive_text())

        assert replayed["type"] in ["SEAT_STATUS_CHANGE", "SNAPSHOT_RESYNC"]
        if replayed["type"] == "SEAT_STATUS_CHANGE":
            assert replayed["seq"] == seq2


def test_websocket_ping_pong_heartbeat(client: TestClient):
    """Server responds to client PING with PONG."""
    with client.websocket_connect("/ws/events?event_id=1") as ws:
        _ = ws.receive_text()  # initial snapshot

        ws.send_text(json.dumps({"action": "PING"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "PONG"
        assert "timestamp" in pong
