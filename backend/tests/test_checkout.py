"""
Phase 6 Integration Tests — Checkout & Payment Simulator
========================================================
Verifies:
1. Successful checkout transitions hold to SOLD, creates confirmed Booking rows in DB,
   records PaymentTransaction, and releases queue admission capacity.
2. Declined payment (simulate_failure=True) records DECLINED transaction, reverts hold to HELD
   so user can safely retry without losing seats, and does NOT release queue capacity.
3. Pending payment (simulate_pending=True) records PROCESSING transaction, keeps hold in PAYING state
   (protected from reaper).
4. Strict idempotency: replaying identical Idempotency-Key returns cached response without duplicate
   charges or duplicate DB bookings.
5. Unauthorized session cannot pay for another user's hold (HTTP 403).
6. Non-existent or expired hold returns HTTP 404 HOLD_NOT_FOUND.
7. Attempting checkout on already SOLD hold returns HTTP 409 HOLD_ALREADY_SOLD.
"""

import time
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient
from sqlalchemy import select
from app.models.booking import Booking, BookingStatus
from app.models.payment import PaymentTransaction, PaymentStatus
from app.models.seat import Seat
from app.redis.client import get_redis
from app.core.config import settings


def test_successful_checkout_confirms_booking_and_marks_sold(client: TestClient):
    """Successful payment creates permanent DB booking, marks Redis seat SOLD, and returns 200."""
    session_id = "checkout_user_success_1"
    headers = {"X-Session-ID": session_id}

    # 1. Claim hold for seats 401, 402
    h_res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [401, 402]},
        headers=headers,
    )
    assert h_res.status_code == 201
    hold_id = h_res.json()["hold_id"]

    # 2. Complete payment
    p_res = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "payment_method": "simulated_card", "simulate_failure": False},
        headers={**headers, "Idempotency-Key": "idem_success_test_401_402"},
    )
    assert p_res.status_code == 200
    data = p_res.json()
    assert data["status"] == "SUCCEEDED"
    assert data["payment_id"] is not None
    assert data["payment_id"].startswith("pay_")
    assert data["booking_id"] is not None
    assert data["booking_id"].startswith("bk_")
    assert sorted(data["seat_ids"]) == [401, 402]
    assert data["total_cents"] > 0
    assert data["confirmed_at"] is not None


@pytest.mark.asyncio
async def test_successful_checkout_db_persistence(db_session_factory):
    """Verify database rows for Booking and PaymentTransaction are persisted permanently."""
    async with db_session_factory() as db:
        # Check bookings for seats 401, 402
        stmt = select(Booking).where(Booking.seat_id.in_([401, 402]), Booking.status == BookingStatus.CONFIRMED.value)
        res = await db.execute(stmt)
        bookings = res.scalars().all()
        assert len(bookings) == 2

        # Check payment transaction
        pay_stmt = select(PaymentTransaction).where(PaymentTransaction.idempotency_key == "idem_success_test_401_402")
        pay_res = await db.execute(pay_stmt)
        tx = pay_res.scalar_one_or_none()
        assert tx is not None
        assert tx.status == PaymentStatus.SUCCEEDED.value


def test_declined_payment_reverts_hold_to_held_and_allows_retry(client: TestClient):
    """Declined payment preserves hold as HELD, allowing user to retry payment."""
    session_id = "checkout_user_retry_flow"
    headers = {"X-Session-ID": session_id}

    # 1. Claim hold for seat 403
    h_res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [403]},
        headers=headers,
    )
    assert h_res.status_code == 201
    hold_id = h_res.json()["hold_id"]

    # 2. Payment fails (e.g. card declined)
    fail_res = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": True},
        headers={**headers, "Idempotency-Key": "idem_attempt_1_failed"},
    )
    assert fail_res.status_code == 200
    fail_data = fail_res.json()
    assert fail_data["status"] == "DECLINED"
    assert fail_data["error_code"] == "CARD_DECLINED"

    # 3. Inspect hold: it was reverted back to HELD, not released or sold!
    get_hold = client.get(f"/api/v1/events/1/holds/{hold_id}", headers=headers)
    assert get_hold.status_code == 200
    assert get_hold.json()["status"] == "HELD"

    # 4. Retry payment with new idempotency key -> succeeds!
    retry_res = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": False},
        headers={**headers, "Idempotency-Key": "idem_attempt_2_success"},
    )
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == "SUCCEEDED"


def test_processing_payment_keeps_hold_in_paying_state(client: TestClient):
    """Pending payment simulation records PROCESSING and leaves hold in PAYING state."""
    session_id = "checkout_user_pending"
    headers = {"X-Session-ID": session_id}

    # 1. Claim hold for seat 404
    h_res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [404]},
        headers=headers,
    )
    assert h_res.status_code == 201
    hold_id = h_res.json()["hold_id"]

    # 2. Simulate pending payment
    p_res = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_pending": True},
        headers={**headers, "Idempotency-Key": "idem_pending_test"},
    )
    assert p_res.status_code == 200
    data = p_res.json()
    assert data["status"] == "PROCESSING"
    assert data["payment_id"] is not None

    # 3. Hold state in Redis is PAYING
    get_hold = client.get(f"/api/v1/events/1/holds/{hold_id}", headers=headers)
    assert get_hold.status_code == 200
    assert get_hold.json()["status"] == "PAYING"


def test_idempotency_key_replay_returns_cached_response(client: TestClient):
    """Replaying the exact same Idempotency-Key returns cached response without duplicate bookings."""
    session_id = "checkout_user_idem"
    headers = {"X-Session-ID": session_id}
    idem_key = "idem_replay_test_key_405"

    # 1. Claim hold for seat 405
    h_res = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [405]},
        headers=headers,
    )
    assert h_res.status_code == 201
    hold_id = h_res.json()["hold_id"]

    # 2. First checkout call
    res1 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": False},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["status"] == "SUCCEEDED"

    # 3. Replay with identical idempotency key
    res2 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": False},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert res2.status_code == 200
    d2 = res2.json()

    # Must match original result
    assert d2["status"] == "SUCCEEDED"
    assert d2["payment_id"] == d1["payment_id"]
    assert d2["booking_id"] == d1["booking_id"]
    assert d2["seat_ids"] == d1["seat_ids"]


def test_checkout_releases_queue_admission_slot_and_promotes_next(client: TestClient, monkeypatch):
    """Completing checkout frees queue capacity slot and automatically promotes the next waiting session."""
    monkeypatch.setattr(settings, "QUEUE_ADMISSION_CAPACITY", 1)

    sess_a = "checkout_queue_user_a"
    sess_b = "checkout_queue_user_b"

    # User A enters queue and gets admitted
    ra = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_a})
    assert ra.json()["status"] == "ADMITTED"
    token_a = ra.json()["admission_token"]

    # User B enters queue and is WAITING at pos 1
    rb = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_b})
    assert rb.json()["status"] == "WAITING"
    assert rb.json()["queue_position"] == 1

    # User A creates hold for seat 406
    ha = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [406]},
        headers={"X-Session-ID": sess_a, "X-Admission-Token": token_a},
    )
    assert ha.status_code == 201
    hold_a = ha.json()["hold_id"]

    # User A completes checkout
    pay_a = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_a, "simulate_failure": False},
        headers={"X-Session-ID": sess_a, "Idempotency-Key": "idem_qa_test"},
    )
    assert pay_a.status_code == 200
    assert pay_a.json()["status"] == "SUCCEEDED"

    # User B polls queue -> automatically promoted to ADMITTED!
    poll_b = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_b})
    assert poll_b.status_code == 200
    assert poll_b.json()["status"] == "ADMITTED"
    assert poll_b.json()["admission_token"] is not None


def test_checkout_unauthorized_session_rejected(client: TestClient):
    """Session attempting checkout for another user's hold is rejected with HTTP 403 FORBIDDEN."""
    # User A creates hold
    ha = client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [407]},
        headers={"X-Session-ID": "owner_session_407"},
    )
    assert ha.status_code == 201
    hold_id = ha.json()["hold_id"]

    # User B attempts to pay for User A's hold
    hb = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id},
        headers={"X-Session-ID": "attacker_session_intruder"},
    )
    assert hb.status_code == 403
    err = hb.json()["error"]
    assert err["code"] == "FORBIDDEN"


def test_checkout_nonexistent_hold_rejected(client: TestClient):
    """Checkout request for non-existent hold returns HTTP 404 HOLD_NOT_FOUND."""
    res = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": "hld_does_not_exist_9999"},
        headers={"X-Session-ID": "any_session"},
    )
    assert res.status_code == 404
    err = res.json()["error"]
    assert err["code"] == "HOLD_NOT_FOUND"


def test_checkout_already_sold_hold_rejected(client: TestClient):
    """Attempting checkout on an already SOLD hold with a new key returns HTTP 409 HOLD_ALREADY_SOLD."""
    session_id = "user_sold_conflict_test"
    headers = {"X-Session-ID": session_id}

    # 1. Claim hold for seat 408
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [408]}, headers=headers)
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]

    # 2. Complete payment
    p1 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": False},
        headers={**headers, "Idempotency-Key": "idem_first_buy_408"},
    )
    assert p1.status_code == 200
    assert p1.json()["status"] == "SUCCEEDED"

    # 3. New payment call on the same hold with a different idempotency key
    p2 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": False},
        headers={**headers, "Idempotency-Key": "idem_second_buy_attempt_408"},
    )
    assert p2.status_code == 409
    assert p2.json()["error"]["code"] == "HOLD_ALREADY_SOLD"


def test_checkout_declined_idempotent_replay(client: TestClient):
    """Replaying the same idempotency key for a DECLINED payment returns the cached DECLINED result."""
    session_id = "user_declined_replay"
    headers = {"X-Session-ID": session_id}
    idem_key = "idem_declined_cache_key"

    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [409]}, headers=headers)
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]

    # First attempt: declined
    r1 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": True},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "DECLINED"

    # Replay identical key
    r2 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_failure": True},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "DECLINED"
    assert "idempotent replay" in r2.json()["message"]


@pytest.mark.asyncio
async def test_reaper_strictly_protects_paying_holds(client: TestClient):
    """A hold in PAYING state is strictly excluded from reaper sweeps even if past expiry."""
    from app.services.reaper_service import reap_expired_holds_once
    from app.redis.client import get_redis

    session_id = "paying_hold_protect_user"
    headers = {"X-Session-ID": session_id}

    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [410]}, headers=headers)
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]

    # Put hold into PROCESSING (state: PAYING)
    p = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_pending": True},
        headers={**headers, "Idempotency-Key": "idem_protect_410"},
    )
    assert p.status_code == 200
    assert p.json()["status"] == "PROCESSING"

    # Force hold into hold_expiry_zset with score in the past
    redis = await get_redis()
    now = int(time.time())
    await redis.zadd("hold_expiry_zset", {hold_id: now - 100})

    # Run reaper sweep
    reaped_holds, reaped_seats = await reap_expired_holds_once()

    # The hold must NOT have been reaped
    hold_meta = await redis.hgetall(f"hold:{hold_id}")
    assert hold_meta is not None
    assert hold_meta.get("status") == "PAYING"

    # Seat status must remain PAYING
    seat_st = await redis.hget("event:1:seat_statuses", "410")
    assert seat_st == "PAYING"


# ══════════════════════════════════════════════════════════════════════════════
# FINAL PAYMENT SAFETY AUDIT TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_idempotency_key_reuse_different_hold_or_session_rejected(client: TestClient):
    """
    AUDIT 1: An idempotency key already used for one hold cannot be reused with a
    different hold_id or different session_id (HTTP 409 IDEMPOTENCY_KEY_REUSE_MISMATCH).
    """
    idem_key = "shared_idem_key_unique_audit_1"

    # User 1 claims hold A for seat 420
    h1 = client.post("/api/v1/events/1/holds", json={"seat_ids": [420]}, headers={"X-Session-ID": "user_one"})
    assert h1.status_code == 201
    hold_a = h1.json()["hold_id"]

    # User 1 pays using idem_key -> succeeds
    p1 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_a, "simulate_failure": False},
        headers={"X-Session-ID": "user_one", "Idempotency-Key": idem_key},
    )
    assert p1.status_code == 200

    # User 2 claims hold B for seat 421
    h2 = client.post("/api/v1/events/1/holds", json={"seat_ids": [421]}, headers={"X-Session-ID": "user_two"})
    assert h2.status_code == 201
    hold_b = h2.json()["hold_id"]

    # User 2 attempts to reuse User 1's idem_key -> must be rejected!
    p2 = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_b, "simulate_failure": False},
        headers={"X-Session-ID": "user_two", "Idempotency-Key": idem_key},
    )
    assert p2.status_code == 409
    err = p2.json()["error"]
    assert err["code"] == "IDEMPOTENCY_KEY_REUSE_MISMATCH"


@pytest.mark.asyncio
async def test_concurrent_idempotency_simulation(client: TestClient, db_session_factory):
    """
    AUDIT 1: Two simultaneous checkout requests with the same Idempotency-Key
    resolve safely so exactly one PaymentTransaction and one set of Booking rows exist.
    """
    import asyncio
    from app.services.checkout_service import CheckoutService

    session_id = "concurrent_idem_session"
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [422]}, headers={"X-Session-ID": session_id})
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]
    idem_key = "concurrent_idem_test_key_422"

    async def _make_pay_request():
        async with db_session_factory() as db:
            return await CheckoutService.process_payment(
                db=db,
                hold_id=hold_id,
                session_id=session_id,
                idempotency_key=idem_key,
                payment_method="simulated_card",
                simulate_failure=False,
            )

    # Launch two simultaneous checkout calls
    res1, res2 = await asyncio.gather(_make_pay_request(), _make_pay_request())

    # Both must report success and share identical payment and booking IDs
    assert res1.status == "SUCCEEDED"
    assert res2.status == "SUCCEEDED"
    assert res1.payment_id == res2.payment_id
    assert res1.booking_id == res2.booking_id

    # Verify database has strictly ONE PaymentTransaction and ONE Booking for seat 422
    async with db_session_factory() as db:
        pt_res = await db.execute(select(PaymentTransaction).where(PaymentTransaction.idempotency_key == idem_key))
        txs = pt_res.scalars().all()
        assert len(txs) == 1

        bk_res = await db.execute(select(Booking).where(Booking.seat_id == 422, Booking.status == BookingStatus.CONFIRMED.value))
        bks = bk_res.scalars().all()
        assert len(bks) == 1


def test_processing_reconciliation_lifecycle(client: TestClient):
    """
    AUDIT 2: PROCESSING payment reconciliation to SUCCEEDED:
    - Authoritative GET /payments/{payment_id} endpoint.
    - POST /reconcile endpoint finalizes payment to SUCCEEDED and creates booking.
    - Subsequent retry of POST /pay with original idempotency key returns the final booking_id.
    - Zero duplicate payment attempts created.
    """
    session_id = "reconciliation_user_flow"
    headers = {"X-Session-ID": session_id}
    idem_key = "reconciliation_idem_key_423"

    # 1. Claim hold for seat 423
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [423]}, headers=headers)
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]

    # 2. Initiate payment with simulate_pending=True -> PROCESSING
    p = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id, "simulate_pending": True},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert p.status_code == 200
    p_data = p.json()
    assert p_data["status"] == "PROCESSING"
    payment_id = p_data["payment_id"]
    assert payment_id is not None
    assert p_data["booking_id"] is None

    # 3. Query status endpoint -> shows PROCESSING
    st_res = client.get(f"/api/v1/checkout/payments/{payment_id}", headers=headers)
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "PROCESSING"
    assert st_res.json()["booking_id"] is None

    # 4. Reconcile to SUCCEEDED via reconciliation endpoint
    rec_res = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": payment_id, "target_outcome": "SUCCEEDED"},
        headers={**headers, "X-Internal-Token": settings.SECRET_KEY},
    )
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["status"] == "SUCCEEDED"
    assert rec_data["payment_id"] == payment_id
    booking_id = rec_data["booking_id"]
    assert booking_id is not None
    assert booking_id.startswith("bk_")

    # 5. Query status endpoint again -> shows SUCCEEDED with booking_id
    st_res2 = client.get(f"/api/v1/checkout/payments/{payment_id}", headers=headers)
    assert st_res2.status_code == 200
    assert st_res2.json()["status"] == "SUCCEEDED"
    assert st_res2.json()["booking_id"] == booking_id

    # 6. Retry original checkout call with the same idempotency key -> returns SUCCEEDED with booking_id!
    retry = client.post(
        "/api/v1/checkout/pay",
        json={"hold_id": hold_id},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "SUCCEEDED"
    assert retry.json()["payment_id"] == payment_id
    assert retry.json()["booking_id"] == booking_id


@pytest.mark.asyncio
async def test_recovery_reconstructs_sold_from_postgres_and_blocks_holds(client: TestClient, db_session_factory):
    """
    AUDIT 3: PostgreSQL has committed booking, but Redis was wiped or failed before transition to SOLD.
    Reconstruction reconstructs SOLD in Redis and blocks new holds or reaper sweeps.
    """
    from app.services.recovery_service import RedisRecoveryService, mark_recovery_complete
    from tests.conftest import test_engine
    from app.redis.client import get_redis
    from app.services.reaper_service import reap_expired_holds_once

    redis = await get_redis()
    seat_id = 424

    # 1. Insert confirmed booking in PostgreSQL
    async with db_session_factory() as db:
        bk = Booking(
            id=f"bk_audit3_{seat_id}",
            event_id=1,
            seat_id=seat_id,
            session_id="pg_committed_user",
            payment_id="pay_audit3_committed",
            amount_cents=5000,
            status=BookingStatus.CONFIRMED.value,
            confirmed_at=datetime.now(timezone.utc),
            idempotency_key=f"idem_audit3_{seat_id}",
        )
        db.add(bk)
        await db.commit()

    # 2. Redis is cleared (or failed before writing SOLD)
    await redis.hdel("event:1:seat_statuses", str(seat_id))
    assert await redis.hget("event:1:seat_statuses", str(seat_id)) is None

    # 3. Run recovery from PostgreSQL
    rec_res = await RedisRecoveryService.reconstruct_state_from_postgres(test_engine, event_id=1)
    assert rec_res["status"] == "SUCCESS"
    mark_recovery_complete()

    # 4. Verify Redis seat status is now reconstructed to SOLD!
    st = await redis.hget("event:1:seat_statuses", str(seat_id))
    assert st == "SOLD"

    # 5. Verify hold creation for seat 424 is rejected with 409 CONFLICT
    h_attempt = client.post("/api/v1/events/1/holds", json={"seat_ids": [seat_id]}, headers={"X-Session-ID": "new_user"})
    assert h_attempt.status_code == 409
    assert h_attempt.json()["error"]["code"] == "SEATS_UNAVAILABLE"

    # 6. Verify reaper cannot reap this confirmed seat
    reaped_holds, reaped_seats = await reap_expired_holds_once()
    st_after = await redis.hget("event:1:seat_statuses", str(seat_id))
    assert st_after == "SOLD"


@pytest.mark.asyncio
async def test_queue_capacity_lifecycle_and_duplicate_callback_safety(client: TestClient, monkeypatch):
    """
    AUDIT 4:
    - DECLINED and PROCESSING retain admission capacity.
    - Successful checkout releases capacity exactly once.
    - Duplicate release/callback attempts cannot release multiple slots or over-promote users.
    """
    from app.services.queue_service import QueueService

    monkeypatch.setattr(settings, "QUEUE_ADMISSION_CAPACITY", 1)
    sess_x = "audit_queue_user_x"
    sess_y = "audit_queue_user_y"
    sess_z = "audit_queue_user_z"

    # User X admitted
    rx = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_x})
    assert rx.json()["status"] == "ADMITTED"
    tok_x = rx.json()["admission_token"]

    # User Y waiting (pos 1), User Z waiting (pos 2)
    ry = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_y})
    assert ry.json()["status"] == "WAITING"
    assert ry.json()["queue_position"] == 1

    rz = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers={"X-Session-ID": sess_z})
    assert rz.json()["status"] == "WAITING"
    assert rz.json()["queue_position"] == 2

    # User X claims hold on seat 425
    hx = client.post("/api/v1/events/1/holds", json={"seat_ids": [425]}, headers={"X-Session-ID": sess_x, "X-Admission-Token": tok_x})
    assert hx.status_code == 201
    hold_x = hx.json()["hold_id"]

    # 1. DECLINED payment retains capacity: User Y is STILL waiting
    fail_p = client.post("/api/v1/checkout/pay", json={"hold_id": hold_x, "simulate_failure": True}, headers={"X-Session-ID": sess_x, "Idempotency-Key": "fail_key_425"})
    assert fail_p.json()["status"] == "DECLINED"

    py = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_y})
    assert py.json()["status"] == "WAITING"

    # 2. PROCESSING payment retains capacity: User Y is STILL waiting
    pend_p = client.post("/api/v1/checkout/pay", json={"hold_id": hold_x, "simulate_pending": True}, headers={"X-Session-ID": sess_x, "Idempotency-Key": "pend_key_425"})
    assert pend_p.json()["status"] == "PROCESSING"

    py2 = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_y})
    assert py2.json()["status"] == "WAITING"

    # 3. Reconcile to SUCCEEDED: releases capacity, User Y is promoted!
    rec = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": pend_p.json()["payment_id"], "target_outcome": "SUCCEEDED"},
        headers={"X-Session-ID": sess_x, "X-Internal-Token": settings.SECRET_KEY},
    )
    assert rec.json()["status"] == "SUCCEEDED"

    py3 = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_y})
    assert py3.json()["status"] == "ADMITTED"

    # User Z is STILL waiting at pos 1 (only 1 user promoted!)
    pz = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_z})
    assert pz.json()["status"] == "WAITING"
    assert pz.json()["queue_position"] == 1

    # 4. Duplicate release call for User X: must return False and NOT promote User Z!
    second_release = await QueueService.release_admission_slot(event_id=1, session_id=sess_x)
    assert second_release is False  # ZREM returned 0

    pz2 = client.get("/api/v1/queue/status?event_id=1", headers={"X-Session-ID": sess_z})
    assert pz2.json()["status"] == "WAITING"
    assert pz2.json()["queue_position"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# RECONCILIATION SECURITY & ENFORCEMENT AUDIT TESTS
# ══════════════════════════════════════════════════════════════════════════════


def test_unauthorized_reconciliation_rejected(client: TestClient):
    """
    AUDIT 1: Reconciliation without X-Internal-Token or with invalid token
    is rejected with HTTP 401 UNAUTHORIZED_RECONCILIATION.
    Ordinary frontend/client requests cannot alter payment or booking states.
    """
    # 1. Without internal token header
    r1 = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": "pay_test_dummy", "target_outcome": "SUCCEEDED"},
    )
    assert r1.status_code == 401
    assert r1.json()["error"]["code"] == "UNAUTHORIZED_RECONCILIATION"

    # 2. With forged/wrong token header
    r2 = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": "pay_test_dummy", "target_outcome": "SUCCEEDED"},
        headers={"X-Internal-Token": "forged_client_token_attempt"},
    )
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "UNAUTHORIZED_RECONCILIATION"


def test_payment_status_ownership_protection(client: TestClient):
    """
    AUDIT 2: GET /payments/{id} verifies session ownership.
    - Missing X-Session-ID -> HTTP 401 UNAUTHORIZED.
    - Different session_id -> HTTP 403 FORBIDDEN.
    - Valid owner session -> HTTP 200 OK.
    Prevents cross-session payment enumeration.
    """
    # Create hold and payment for user A
    sess_a = "legitimate_owner_sess"
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [430]}, headers={"X-Session-ID": sess_a})
    assert h.status_code == 201
    p = client.post("/api/v1/checkout/pay", json={"hold_id": h.json()["hold_id"], "simulate_pending": True}, headers={"X-Session-ID": sess_a})
    pay_id = p.json()["payment_id"]

    # 1. Missing session header
    r_no_header = client.get(f"/api/v1/checkout/payments/{pay_id}")
    assert r_no_header.status_code == 401
    assert r_no_header.json()["error"]["code"] == "UNAUTHORIZED"

    # 2. Unauthorized session B
    r_intruder = client.get(f"/api/v1/checkout/payments/{pay_id}", headers={"X-Session-ID": "snooper_session_b"})
    assert r_intruder.status_code == 403
    assert r_intruder.json()["error"]["code"] == "FORBIDDEN"

    # 3. Legitimate owner A
    r_owner = client.get(f"/api/v1/checkout/payments/{pay_id}", headers={"X-Session-ID": sess_a})
    assert r_owner.status_code == 200
    assert r_owner.json()["payment_id"] == pay_id
    assert r_owner.json()["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_concurrent_mismatched_key_collision_rejected(db_session_factory):
    """
    AUDIT 3: If a concurrent collision occurs where the database transaction was created
    by a different session or for a different hold, collision recovery rejects with
    HTTP 409 IDEMPOTENCY_KEY_REUSE_MISMATCH rather than leaking another session's booking.
    """
    from app.services.checkout_service import CheckoutService
    from fastapi import HTTPException

    # Simulate collision: caller B provides idem_key that belongs to User A
    idem_key = "collision_mismatch_test_key"
    async with db_session_factory() as db:
        # Pre-insert transaction for User A on Hold 100
        tx = PaymentTransaction(
            id="pay_user_a_preexisting",
            hold_id="hld_user_a_100",
            session_id="user_a_legitimate",
            amount_cents=5000,
            status=PaymentStatus.SUCCEEDED.value,
            idempotency_key=idem_key,
            lease_expires_at=datetime.now(timezone.utc),
        )
        db.add(tx)
        await db.commit()

        # User B attempts checkout with the same idem_key but for Hold 200
        with pytest.raises(HTTPException) as exc_info:
            await CheckoutService.process_payment(
                db=db,
                hold_id="hld_user_b_200",
                session_id="user_b_attacker",
                idempotency_key=idem_key,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "IDEMPOTENCY_KEY_REUSE_MISMATCH"


@pytest.mark.asyncio
async def test_concurrent_processing_collision_handled(client: TestClient, db_session_factory):
    """
    AUDIT 3: If two concurrent requests with the same key collide and the first
    created a PROCESSING transaction, collision recovery handles it safely and returns PROCESSING.
    """
    from app.services.checkout_service import CheckoutService

    session_id = "concurrent_proc_user"
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [431]}, headers={"X-Session-ID": session_id})
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]
    idem_key = "concurrent_proc_key_431"

    # Pre-commit a PROCESSING transaction for this exact hold and session (simulating concurrent insert)
    async with db_session_factory() as db:
        tx = PaymentTransaction(
            id="pay_proc_concurrent_test",
            hold_id=hold_id,
            session_id=session_id,
            amount_cents=5000,
            status=PaymentStatus.PROCESSING.value,
            idempotency_key=idem_key,
            lease_expires_at=datetime.now(timezone.utc),
        )
        db.add(tx)
        await db.commit()

        # Process payment with same key -> returns PROCESSING cleanly
        res = await CheckoutService.process_payment(
            db=db,
            hold_id=hold_id,
            session_id=session_id,
            idempotency_key=idem_key,
        )
        assert res.status == "PROCESSING"
        assert res.payment_id == "pay_proc_concurrent_test"


def test_duplicate_reconciliation_is_idempotent(client: TestClient, db_session_factory):
    """
    AUDIT 4: Reconciling an already SUCCEEDED payment:
    - Does NOT create duplicate bookings.
    - Does NOT alter payment status.
    - Returns authoritative confirmed booking.
    """
    session_id = "dup_reconcile_user"
    headers = {"X-Session-ID": session_id}

    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [432]}, headers=headers)
    assert h.status_code == 201
    hold_id = h.json()["hold_id"]

    p = client.post("/api/v1/checkout/pay", json={"hold_id": hold_id, "simulate_pending": True}, headers=headers)
    pay_id = p.json()["payment_id"]

    # First reconciliation -> SUCCEEDED
    r1 = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": pay_id, "target_outcome": "SUCCEEDED"},
        headers={"X-Internal-Token": settings.SECRET_KEY, "X-Session-ID": session_id},
    )
    assert r1.status_code == 200
    b_id1 = r1.json()["booking_id"]

    # Second (duplicate) reconciliation -> idempotent return
    r2 = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": pay_id, "target_outcome": "SUCCEEDED"},
        headers={"X-Internal-Token": settings.SECRET_KEY, "X-Session-ID": session_id},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "SUCCEEDED"
    assert r2.json()["booking_id"] == b_id1
    assert "duplicate reconciliation idempotent" in r2.json()["message"]


def test_attempted_reversal_of_succeeded_rejected(client: TestClient):
    """
    AUDIT 4: SUCCEEDED is a terminal state.
    Attempting to reverse or decline an already confirmed SUCCEEDED payment
    is rejected with HTTP 409 INVALID_STATE_TRANSITION.
    """
    session_id = "reversal_test_user"
    headers = {"X-Session-ID": session_id}

    # Claim and pay successfully
    h = client.post("/api/v1/events/1/holds", json={"seat_ids": [433]}, headers=headers)
    assert h.status_code == 201
    p = client.post("/api/v1/checkout/pay", json={"hold_id": h.json()["hold_id"]}, headers=headers)
    assert p.status_code == 200
    assert p.json()["status"] == "SUCCEEDED"
    pay_id = p.json()["payment_id"]

    # 1. Attempt to reconcile to DECLINED
    rev_declined = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": pay_id, "target_outcome": "DECLINED"},
        headers={"X-Internal-Token": settings.SECRET_KEY, "X-Session-ID": session_id},
    )
    assert rev_declined.status_code == 409
    assert rev_declined.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # 2. Attempt to reconcile to VOIDED
    rev_voided = client.post(
        "/api/v1/checkout/reconcile",
        json={"payment_id": pay_id, "target_outcome": "VOIDED"},
        headers={"X-Internal-Token": settings.SECRET_KEY, "X-Session-ID": session_id},
    )
    assert rev_voided.status_code == 409
    assert rev_voided.json()["error"]["code"] == "INVALID_STATE_TRANSITION"



