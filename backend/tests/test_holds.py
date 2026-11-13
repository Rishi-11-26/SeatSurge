import pytest
import time
from app.redis.scripts import TRANSITION_HOLD_LUA
from app.services.reaper_service import reap_expired_holds_once
from app.services.recovery_service import RedisRecoveryService
from app.models.booking import Booking, BookingStatus


def test_create_single_seat_hold(client):
    """Verifies atomic creation of a single seat hold for 120 seconds."""
    payload = {"seat_ids": [1]}
    headers = {"X-Session-ID": "session_test_single_01"}

    response = client.post("/api/v1/events/1/holds", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["event_id"] == 1
    assert data["seat_ids"] == [1]
    assert data["status"] == "HELD"
    assert data["time_remaining_seconds"] <= 120
    assert data["time_remaining_seconds"] >= 115
    assert data["hold_id"].startswith("hld_")

    # Authoritative seat status overlay must reflect HELD
    seat_res = client.get("/api/v1/events/1/seats/1")
    assert seat_res.status_code == 200
    assert seat_res.json()["status"] == "HELD"

    # Metrics counter must reflect 1 active hold
    metrics_res = client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    assert metrics_res.json()["active_holds_count"] >= 1


def test_create_group_adjacent_hold(client):
    """Verifies group holds up to 6 adjacent seats succeed atomically."""
    # Seats 11, 12, 13, 14 are all Row A (seats 1-60 are Row A)
    payload = {"seat_ids": [11, 12, 13, 14]}
    headers = {"X-Session-ID": "session_group_01"}

    response = client.post("/api/v1/events/1/holds", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()

    assert len(data["seat_ids"]) == 4
    assert data["seat_ids"] == [11, 12, 13, 14]

    # Verify all 4 seats are HELD
    for sid in [11, 12, 13, 14]:
        s_res = client.get(f"/api/v1/events/1/seats/{sid}")
        assert s_res.json()["status"] == "HELD"


def test_group_hold_non_adjacent_rejected(client):
    """Verifies group seats with gaps are rejected (NOT_ADJACENT)."""
    # Seats 20 and 22 have a gap (seat 21 is missing)
    payload = {"seat_ids": [20, 22]}
    headers = {"X-Session-ID": "session_non_adjacent"}

    response = client.post("/api/v1/events/1/holds", json=payload, headers=headers)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "NOT_ADJACENT"

    # Seats must remain AVAILABLE (all-or-nothing guarantee)
    for sid in [20, 22]:
        s_res = client.get(f"/api/v1/events/1/seats/{sid}")
        assert s_res.json()["status"] == "AVAILABLE"


def test_group_hold_different_rows_rejected(client):
    """Verifies group seats spanning multiple rows are rejected."""
    # Seat 60 is Row A (num 60), Seat 61 is Row B (num 1)
    payload = {"seat_ids": [60, 61]}
    headers = {"X-Session-ID": "session_diff_rows"}

    response = client.post("/api/v1/events/1/holds", json=payload, headers=headers)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "NOT_ADJACENT"


def test_group_hold_exceeds_six_seats_rejected(client):
    """Verifies requests with more than 6 seats are rejected by schema."""
    payload = {"seat_ids": [1, 2, 3, 4, 5, 6, 7]}
    headers = {"X-Session-ID": "session_too_many"}

    response = client.post("/api/v1/events/1/holds", json=payload, headers=headers)
    assert response.status_code == 422  # Pydantic validation error for max_length=6


def test_hold_conflict_all_or_nothing(client):
    """
    CRITICAL ZERO DOUBLE BOOKING GUARANTEE:
    Session A holds [30, 31].
    Session B attempts [31, 32].
    Session B must be rejected (409 Conflict), and Seat 32 must remain AVAILABLE.
    """
    headers_a = {"X-Session-ID": "session_A_conflict"}
    headers_b = {"X-Session-ID": "session_B_conflict"}

    # Session A claims 30, 31
    res_a = client.post("/api/v1/events/1/holds", json={"seat_ids": [30, 31]}, headers=headers_a)
    assert res_a.status_code == 201

    # Session B attempts 31, 32 -> MUST FAIL WITH 409
    res_b = client.post("/api/v1/events/1/holds", json={"seat_ids": [31, 32]}, headers=headers_b)
    assert res_b.status_code == 409
    err = res_b.json()["error"]
    assert err["code"] == "SEATS_UNAVAILABLE"
    assert 31 in err["details"]["conflicting_seats"]

    # Seat 32 must still be AVAILABLE (all-or-nothing guarantee)
    s32 = client.get("/api/v1/events/1/seats/32")
    assert s32.json()["status"] == "AVAILABLE"


def test_manual_hold_release(client):
    """Verifies a session can manually release their own hold before expiry."""
    headers = {"X-Session-ID": "session_releaser"}
    res = client.post("/api/v1/events/1/holds", json={"seat_ids": [40]}, headers=headers)
    assert res.status_code == 201
    hold_id = res.json()["hold_id"]

    # Release hold
    del_res = client.delete(f"/api/v1/events/1/holds/{hold_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["released_seats_count"] == 1

    # Repeat release MUST return 404 and cannot decrement counter twice
    del_res_repeat = client.delete(f"/api/v1/events/1/holds/{hold_id}", headers=headers)
    assert del_res_repeat.status_code == 404

    # Seat must revert immediately to AVAILABLE
    s40 = client.get("/api/v1/events/1/seats/40")
    assert s40.json()["status"] == "AVAILABLE"


def test_manual_hold_release_unauthorized(client):
    """Verifies hold privacy and that only the holding session can release or inspect their hold."""
    res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [41]},
        headers={"X-Session-ID": "session_owner_41"},
    )
    assert res.status_code == 201
    hold_id = res.json()["hold_id"]

    # Intruder tries to inspect private hold details -> 403 Forbidden
    intruder_get = client.get(
        f"/api/v1/events/1/holds/{hold_id}",
        headers={"X-Session-ID": "session_intruder"},
    )
    assert intruder_get.status_code == 403
    assert intruder_get.json()["error"]["code"] == "FORBIDDEN"

    # Intruder tries to release -> 403 Forbidden
    intruder_res = client.delete(
        f"/api/v1/events/1/holds/{hold_id}",
        headers={"X-Session-ID": "session_intruder"},
    )
    assert intruder_res.status_code == 403
    assert intruder_res.json()["error"]["code"] == "FORBIDDEN"

    # Owner can inspect their own hold -> 200 OK
    owner_get = client.get(
        f"/api/v1/events/1/holds/{hold_id}",
        headers={"X-Session-ID": "session_owner_41"},
    )
    assert owner_get.status_code == 200
    assert owner_get.json()["hold_id"] == hold_id


@pytest.mark.asyncio
async def test_expiry_reaper_sweeps_expired_held_seats(client, setup_fake_redis):
    """
    CRITICAL REAPER REQUIREMENT:
    Expired HELD holds must be swept and released within 5 seconds of expiry.
    Repeated expiry processing cannot decrement the counter twice.
    """
    redis = setup_fake_redis
    headers = {"X-Session-ID": "session_reap_target"}

    # 1. Create hold on seat 51
    res = client.post("/api/v1/events/1/holds", json={"seat_ids": [51]}, headers=headers)
    assert res.status_code == 201
    hold_id = res.json()["hold_id"]

    # Record counter before reap
    cnt_before = int(await redis.get("holds:active:count") or 0)
    assert cnt_before >= 1

    # 2. Simulate expiry by backdating score in hold_expiry_zset to 10 seconds ago
    now = int(time.time())
    past_timestamp = now - 10
    await redis.zadd("hold_expiry_zset", {hold_id: past_timestamp})

    # 3. Trigger reaper sweep 1 -> Must reap 1 hold
    reaped_holds_1, reaped_seats_1 = await reap_expired_holds_once()
    assert reaped_holds_1 >= 1
    assert reaped_seats_1 >= 1

    # Counter must have decremented by reaped_seats_1
    cnt_after = int(await redis.get("holds:active:count") or 0)
    assert cnt_after == cnt_before - reaped_seats_1

    # 4. Trigger reaper sweep 2 immediately -> Cannot reap or decrement again
    reaped_holds_2, reaped_seats_2 = await reap_expired_holds_once()
    assert reaped_holds_2 == 0
    assert reaped_seats_2 == 0
    cnt_after_repeat = int(await redis.get("holds:active:count") or 0)
    assert cnt_after_repeat == cnt_after

    # 5. Seat 51 must now be AVAILABLE again
    s51 = client.get("/api/v1/events/1/seats/51")
    assert s51.json()["status"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_expiry_reaper_protects_paying_holds(client, setup_fake_redis):
    """
    CRITICAL PAYMENT SAFETY REQUIREMENT:
    An in-flight payment (PAYING state) must NEVER be reaped, even if its original
    120s hold expiry timestamp has passed.
    """
    redis = setup_fake_redis
    headers = {"X-Session-ID": "session_paying_protection"}

    # 1. Create hold on seat 52
    res = client.post("/api/v1/events/1/holds", json={"seat_ids": [52]}, headers=headers)
    assert res.status_code == 201
    hold_id = res.json()["hold_id"]

    # 2. Transition hold to PAYING state
    await redis.eval(
        TRANSITION_HOLD_LUA,
        4,
        f"hold:{hold_id}",
        "event:1:seat_statuses",
        "hold_expiry_zset",
        "holds:active:count",
        "PAYING",
    )

    # 3. Simulate hold timestamp falling in the past
    now = int(time.time())
    await redis.zadd("hold_expiry_zset", {hold_id: now - 10})

    # 4. Run reaper sweep
    await reap_expired_holds_once()

    # 5. Seat 52 must REMAIN PAYING (protected from reaper)
    s52 = client.get("/api/v1/events/1/seats/52")
    assert s52.json()["status"] == "PAYING"


@pytest.mark.asyncio
async def test_redis_recovery_gate(client, db_session_factory, setup_fake_redis):
    """
    CRITICAL REDIS RECOVERY REQUIREMENT:
    Reconstructs SOLD and PAYING state from PostgreSQL after Redis restart/loss.
    """
    from tests.conftest import test_engine

    # 1. Insert confirmed sale in DB for seat 99
    async with db_session_factory() as session:
        booking = Booking(
            id="rec_test_bk_01",
            event_id=1,
            seat_id=99,
            session_id="rec_buyer",
            payment_id="pay_rec_01",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key="key_rec_01",
        )
        session.add(booking)
        await session.commit()

    # 2. Run recovery service
    result = await RedisRecoveryService.reconstruct_state_from_postgres(test_engine, event_id=1)
    assert result["status"] == "SUCCESS"
    assert result["sold_reconstructed"] >= 1

    # 3. Verify Redis has marked seat 99 as SOLD
    redis = setup_fake_redis
    status_in_redis = await redis.hget("event:1:seat_statuses", "99")
    assert status_in_redis == "SOLD"

    # 4. Attempting to hold seat 99 must be rejected immediately as 409
    hold_attempt = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [99]},
        headers={"X-Session-ID": "attempt_on_sold"},
    )
    assert hold_attempt.status_code == 409


def test_hold_idempotency_key(client):
    """Verifies that repeated hold requests with the same Idempotency-Key return the same hold."""
    idem_key = "idem_hold_repeat_123"
    headers = {"X-Session-ID": "session_idem_hold", "Idempotency-Key": idem_key}

    # Request 1
    res1 = client.post("/api/v1/events/1/holds", json={"seat_ids": [55]}, headers=headers)
    assert res1.status_code == 201
    hold_id_1 = res1.json()["hold_id"]

    # Request 2 with same idempotency key
    res2 = client.post("/api/v1/events/1/holds", json={"seat_ids": [55]}, headers=headers)
    assert res2.status_code == 201
    hold_id_2 = res2.json()["hold_id"]

    # Must return exact same hold_id
    assert hold_id_1 == hold_id_2


@pytest.mark.asyncio
async def test_concurrent_competing_holds_zero_double_booking(db_session_factory, setup_fake_redis):
    """
    CRITICAL ZERO DOUBLE BOOKING UNDER CONCURRENCY:
    10 concurrent sessions attempt to hold the exact same seat simultaneously.
    Guarantees:
    - Exactly 1 session succeeds (returns HoldResponse).
    - Exactly 9 sessions fail with 409 Conflict.
    - Zero double bookings occurred.
    - Active hold counter incremented by exactly 1.
    """
    from app.services.hold_service import HoldService
    from fastapi import HTTPException
    import asyncio

    target_seat_id = 77
    sessions = [f"concurrent_session_{i}" for i in range(10)]

    async def attempt_hold(sess_id: str):
        async with db_session_factory() as db:
            try:
                res = await HoldService.create_hold(
                    db=db,
                    event_id=1,
                    seat_ids=[target_seat_id],
                    session_id=sess_id,
                )
                return ("SUCCESS", res)
            except HTTPException as e:
                return ("FAILED", e.status_code, e.detail)

    results = await asyncio.gather(*[attempt_hold(s) for s in sessions])

    successes = [r for r in results if r[0] == "SUCCESS"]
    failures = [r for r in results if r[0] == "FAILED"]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 9, f"Expected exactly 9 failures, got {len(failures)}"
    for f in failures:
        assert f[1] == 409
        assert f[2]["code"] == "SEATS_UNAVAILABLE"

    # Counter in Redis must be exactly 1
    redis = setup_fake_redis
    counter = await redis.get("holds:active:count")
    assert int(counter) == 1
