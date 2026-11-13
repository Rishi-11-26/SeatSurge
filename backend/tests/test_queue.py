"""
Phase 5 Integration Tests — Virtual Waiting Room & FIFO Queue
============================================================
Verifies:
1. Entering queue returns ADMITTED with signed token when capacity is available.
2. Multiple users receive strict FIFO ordering when capacity is exceeded.
3. Idempotent queue entry: repeated calls return current status/token without duplication.
4. Token cryptographic validation: tamper-proofing and event/session binding.
5. Invalid admission token cannot create seat holds (HTTP 403).
6. Expired admission token cannot create seat holds (HTTP 403).
7. Valid admission token creates seat hold and is bound to that hold.
8. Leaving queue frees capacity and promotes the next waiting user.
"""

import time
import pytest
from starlette.testclient import TestClient
from app.services.queue_service import QueueService
from app.core.config import settings


def test_queue_enter_admitted_when_under_capacity(client: TestClient):
    """When under capacity, user is immediately admitted with a signed token."""
    session_id = "queue_user_direct_admit"
    res = client.post(
        "/api/v1/queue/enter",
        json={"event_id": 1},
        headers={"X-Session-ID": session_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ADMITTED"
    assert data["queue_position"] == 0
    assert data["admission_token"] is not None
    assert data["admission_token"].startswith("adm_")
    assert data["token_expires_at"] is not None
    assert data["session_id"] == session_id
    assert data["event_id"] == 1


def test_queue_polling_is_idempotent(client: TestClient):
    """Repeated calls to /queue/enter or /queue/status return the same token."""
    session_id = "queue_user_idempotent"
    headers = {"X-Session-ID": session_id}

    # First call
    res1 = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    assert res1.status_code == 200
    token1 = res1.json()["admission_token"]

    # Second call (polling via POST)
    res2 = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    assert res2.status_code == 200
    token2 = res2.json()["admission_token"]

    # Third call (polling via GET)
    res3 = client.get("/api/v1/queue/status?event_id=1", headers=headers)
    assert res3.status_code == 200
    token3 = res3.json()["admission_token"]

    assert token1 == token2 == token3


def test_fifo_ordering_when_capacity_exceeded(client: TestClient, monkeypatch):
    """When capacity is 1, user 1 is admitted, user 2 and user 3 are queued in FIFO order."""
    # Constrain capacity to 1 for this test
    monkeypatch.setattr(settings, "QUEUE_ADMISSION_CAPACITY", 1)

    sess_1 = "fifo_user_1"
    sess_2 = "fifo_user_2"
    sess_3 = "fifo_user_3"

    # User 1 enters -> ADMITTED
    res1 = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_1})
    assert res1.status_code == 200
    assert res1.json()["status"] == "ADMITTED"
    assert res1.json()["queue_position"] == 0

    # User 2 enters -> WAITING at position 1
    res2 = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_2})
    assert res2.status_code == 200
    assert res2.json()["status"] == "WAITING"
    assert res2.json()["queue_position"] == 1
    assert res2.json()["admission_token"] is None

    # User 3 enters -> WAITING at position 2
    res3 = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_3})
    assert res3.status_code == 200
    assert res3.json()["status"] == "WAITING"
    assert res3.json()["queue_position"] == 2

    # User 1 leaves -> User 2 should be promoted!
    leave_res = client.post("/api/v1/queue/leave", json={"event_id": 1}, headers={"X-Session-ID": sess_1})
    assert leave_res.status_code == 200

    # User 2 polls -> now ADMITTED
    poll_u2 = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_2})
    assert poll_u2.status_code == 200
    assert poll_u2.json()["status"] == "ADMITTED"
    assert poll_u2.json()["admission_token"] is not None

    # User 3 polls -> now WAITING at position 1
    poll_u3 = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_3})
    assert poll_u3.status_code == 200
    assert poll_u3.json()["status"] == "WAITING"
    assert poll_u3.json()["queue_position"] == 1


def test_invalid_admission_token_rejected_on_hold(client: TestClient):
    """Providing an invalid/forged admission token returns 403 INVALID_ADMISSION_TOKEN."""
    res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [301]},
        headers={
            "X-Session-ID": "tamper_session",
            "X-Admission-Token": "adm_forged_token_abc_123_invalid",
        },
    )
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "INVALID_ADMISSION_TOKEN"


def test_expired_admission_token_rejected_on_hold(client: TestClient):
    """Providing an expired admission token returns 403 EXPIRED_ADMISSION_TOKEN."""
    session_id = "expired_tok_session"
    # Generate token that expired 60 seconds ago
    past_exp = int(time.time()) - 60
    expired_token = QueueService.generate_signed_token(session_id, event_id=1, expires_at=past_exp)

    res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [302]},
        headers={
            "X-Session-ID": session_id,
            "X-Admission-Token": expired_token,
        },
    )
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "EXPIRED_ADMISSION_TOKEN"


def test_session_mismatch_admission_token_rejected(client: TestClient):
    """User B cannot use User A's admission token."""
    tok_user_a = QueueService.generate_signed_token("user_a", event_id=1, expires_at=int(time.time()) + 900)

    res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [303]},
        headers={
            "X-Session-ID": "user_b",  # mismatch!
            "X-Admission-Token": tok_user_a,
        },
    )
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "INVALID_ADMISSION_TOKEN"


def test_valid_admission_token_allows_hold_and_binds(client: TestClient):
    """A valid admission token from /queue/enter successfully creates a hold."""
    session_id = "valid_flow_user"
    headers = {"X-Session-ID": session_id}

    # 1. Enter queue to obtain valid token
    q_res = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    assert q_res.status_code == 200
    token = q_res.json()["admission_token"]
    assert token is not None

    # 2. Use token to create hold on seat 304
    headers["X-Admission-Token"] = token
    hold_res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [304]},
        headers=headers,
    )
    assert hold_res.status_code == 201
    assert hold_res.json()["status"] == "HELD"


def test_token_single_use_enforcement(client: TestClient):
    """Once consumed for a hold, attempting to reuse the same token for a different hold is rejected."""
    session_id = "single_use_tester"
    headers = {"X-Session-ID": session_id}

    # 1. Obtain token
    q_res = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    token = q_res.json()["admission_token"]
    headers["X-Admission-Token"] = token

    # 2. Hold seat 305 -> Success
    res1 = client.post("/api/v1/events/1/holds", json={"seat_ids": [305]}, headers=headers)
    assert res1.status_code == 201

    # 3. Try to reuse same token for seat 306 -> Rejected!
    res2 = client.post("/api/v1/events/1/holds", json={"seat_ids": [306]}, headers=headers)
    assert res2.status_code == 403
    assert res2.json()["error"]["code"] == "ADMISSION_TOKEN_ALREADY_USED"
