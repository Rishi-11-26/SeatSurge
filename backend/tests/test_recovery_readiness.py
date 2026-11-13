"""
Phase 2 Final Hardening — Fail-Closed Recovery & Readiness Tests
=================================================================
Tests the fail-closed readiness behaviour and hold-creation guards that ensure
no booking traffic is served before Redis state recovery is complete.

INFRASTRUCTURE NOTE:
These tests use fakeredis in place of real Redis 7.  Behaviour is validated
at the application logic layer.  Real Redis 7 and PostgreSQL 16 integration
tests remain BLOCKED pending provisioned infrastructure (see Docker Compose
procedure in docs/verification-procedure.md).
"""

import pytest
from starlette.testclient import TestClient

from app.services.recovery_service import (
    is_recovery_complete,
    mark_recovery_complete,
    mark_recovery_skipped,
    reset_recovery_state,
)
from app.redis.client import set_redis_override

# Full path: /api/v1/events/{event_id}/holds
HOLDS_URL = "/api/v1/events/1/holds"
READINESS_URL = "/api/v1/health/readiness"


# ---------------------------------------------------------------------------
# A1. Readiness returns 503 when recovery has NOT completed
# ---------------------------------------------------------------------------

class TestReadinessFailClosed:
    def test_readiness_503_when_recovery_not_complete(self, client: TestClient):
        """
        Readiness probe must return 503 when recovery_complete is False.
        The setup_fake_redis autouse fixture calls mark_recovery_complete(); we
        reset it here to simulate a fresh-startup state before recovery runs.
        """
        reset_recovery_state()          # simulate: recovery not yet run
        response = client.get(READINESS_URL)
        mark_recovery_complete()        # restore so other tests are unaffected

        assert response.status_code == 503, (
            f"Expected 503 when recovery incomplete, got {response.status_code}"
        )
        body = response.json()
        assert body["ready"] is False
        assert body["recovery_complete"] is False

    def test_readiness_503_when_recovery_skipped(self, client: TestClient):
        """
        If recovery returned SKIPPED (Redis was unavailable at startup),
        readiness must remain 503 — the instance must NOT serve booking traffic.
        """
        reset_recovery_state()
        mark_recovery_skipped()         # simulate: Redis was down at startup
        response = client.get(READINESS_URL)
        mark_recovery_complete()        # restore

        assert response.status_code == 503, (
            f"Expected 503 when recovery was skipped, got {response.status_code}"
        )
        body = response.json()
        assert body["ready"] is False
        assert body["recovery_complete"] is False

    def test_readiness_200_when_recovery_complete(self, client: TestClient, monkeypatch):
        """
        Readiness probe returns 200 when DB, Redis, AND recovery are all healthy.
        Patches check_db_health to simulate healthy database connectivity in the
        isolated test environment (where PostgreSQL daemon is not active).
        """
        async def mock_db_ok():
            return True

        monkeypatch.setattr("app.api.v1.endpoints.health.check_db_health", mock_db_ok)
        response = client.get(READINESS_URL)
        assert response.status_code == 200, (
            f"Expected 200 when recovery complete, got {response.status_code}"
        )
        body = response.json()
        assert body["ready"] is True
        assert body["database"] is True
        assert body["redis"] is True
        assert body["recovery_complete"] is True

    def test_readiness_response_schema_has_recovery_complete_field(self, client: TestClient):
        """ReadinessResponse must expose recovery_complete so orchestrators can inspect it."""
        response = client.get(READINESS_URL)
        body = response.json()
        assert "recovery_complete" in body, "recovery_complete field missing from ReadinessResponse"


# ---------------------------------------------------------------------------
# A2. Hold creation blocked when Redis is unavailable (None override)
# ---------------------------------------------------------------------------

class TestHoldCreationFailClosed:
    def test_hold_rejected_when_redis_unavailable(self, client: TestClient, setup_fake_redis):
        """
        Hold creation must return 503 REDIS_UNAVAILABLE when get_redis() returns None.
        This simulates total Redis loss after startup (pool exhausted / network partition).
        """
        # Remove FakeRedis so get_redis() returns None
        set_redis_override(None)
        try:
            response = client.post(
                HOLDS_URL,
                json={"seat_ids": [1]},
                headers={"X-Session-ID": "test-session-unavail"},
            )
        finally:
            # Restore the fixture's fake client
            set_redis_override(setup_fake_redis)

        assert response.status_code == 503, (
            f"Expected 503 when Redis is None, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["error"]["code"] == "REDIS_UNAVAILABLE"

    def test_hold_rejected_when_recovery_incomplete(self, client: TestClient):
        """
        Hold creation must return 503 RECOVERY_INCOMPLETE when recovery has not completed.
        Enforces that no booking traffic can proceed before recovery finishes.
        """
        reset_recovery_state()
        try:
            response = client.post(
                HOLDS_URL,
                json={"seat_ids": [1]},
                headers={"X-Session-ID": "test-session-incomplete"},
            )
        finally:
            mark_recovery_complete()

        assert response.status_code == 503, (
            f"Expected 503 when recovery incomplete, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["error"]["code"] == "RECOVERY_INCOMPLETE"

    def test_hold_rejected_during_recovery_gate(self, client: TestClient, sync_fake_redis):
        """
        Hold creation must return 503 RECOVERY_IN_PROGRESS while the Redis
        recovery gate key ('redis_recovery_in_progress') is set.
        Uses the sync FakeRedis fixture handle to inject the gate key.
        """
        sync_fake_redis.set("redis_recovery_in_progress", "1", ex=30)

        try:
            response = client.post(
                HOLDS_URL,
                json={"seat_ids": [1]},
                headers={"X-Session-ID": "test-session-gate"},
            )
        finally:
            sync_fake_redis.delete("redis_recovery_in_progress")

        assert response.status_code == 503, (
            f"Expected 503 during recovery gate, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["error"]["code"] == "RECOVERY_IN_PROGRESS"

    def test_hold_succeeds_after_recovery_complete(self, client: TestClient):
        """
        Hold creation succeeds normally when Redis is available and
        recovery_complete is True (happy-path set by conftest).
        Seat 50 chosen to avoid collisions with other test files.
        """
        response = client.post(
            HOLDS_URL,
            json={"seat_ids": [50]},
            headers={"X-Session-ID": "test-session-success"},
        )
        assert response.status_code == 201, (
            f"Expected 201 on normal hold, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["hold_id"].startswith("hld_")
        assert body["status"] == "HELD"


# ---------------------------------------------------------------------------
# A3. Recovery state flags behave correctly across transitions
# ---------------------------------------------------------------------------

class TestRecoveryStateFlags:
    def test_initial_state_is_not_complete(self):
        """After reset, is_recovery_complete() must return False."""
        reset_recovery_state()
        assert is_recovery_complete() is False
        mark_recovery_complete()   # restore

    def test_mark_complete_sets_flag(self):
        """mark_recovery_complete() makes is_recovery_complete() True."""
        reset_recovery_state()
        mark_recovery_complete()
        assert is_recovery_complete() is True

    def test_mark_skipped_does_not_complete(self):
        """mark_recovery_skipped() must NOT satisfy is_recovery_complete()."""
        reset_recovery_state()
        mark_recovery_skipped()
        assert is_recovery_complete() is False
        mark_recovery_complete()   # restore

    def test_reset_clears_complete_flag(self):
        """reset_recovery_state() must clear is_recovery_complete()."""
        mark_recovery_complete()
        reset_recovery_state()
        assert is_recovery_complete() is False
        mark_recovery_complete()   # restore
