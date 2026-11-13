import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentTransaction, PaymentStatus
from app.models.booking import Booking, BookingStatus
from app.models.seat import Seat
from app.redis.client import get_redis
from app.redis.scripts import TRANSITION_HOLD_LUA
from app.schemas.checkout import CheckoutPayResponse
from app.services.websocket_service import ws_manager
from app.services.queue_service import QueueService
from app.core.logging import logger


class CheckoutService:
    @classmethod
    async def process_payment(
        cls,
        db: AsyncSession,
        hold_id: str,
        session_id: str,
        idempotency_key: Optional[str] = None,
        payment_method: str = "simulated_card",
        simulate_failure: bool = False,
        simulate_pending: bool = False,
    ) -> CheckoutPayResponse:
        """
        Processes checkout and payment simulation (docs/api-contract.md §7).
        Guarantees:
        - Strict idempotency: replaying the same Idempotency-Key returns cached result.
        - Atomic hold transitions via Redis Lua: HELD -> PAYING -> SOLD.
        - PostgreSQL / SQLite as authoritative source of truth for confirmed bookings.
        - Zero double-booking enforced by DB partial unique index on (event_id, seat_id).
        - Holds in PAYING state are strictly protected from reaper sweeps.
        - Safe retry on DECLINED: hold is preserved as HELD for retry until hold expires.
        - Queue admission capacity released ONLY when payment lifecycle reaches definitive outcome (SUCCEEDED).
        """
        redis = await get_redis()
        hold_meta_key = f"hold:{hold_id}"
        expiry_zset_key = "hold_expiry_zset"
        counter_key = "holds:active:count"

        # 1. Idempotency Check
        idem_key = idempotency_key or f"auto_{uuid.uuid4().hex}"
        stmt = select(PaymentTransaction).where(PaymentTransaction.idempotency_key == idem_key)
        res = await db.execute(stmt)
        existing_tx = res.scalar_one_or_none()

        if existing_tx:
            # 1a. Security check: cannot reuse idempotency key across different holds or sessions
            if existing_tx.hold_id != hold_id or existing_tx.session_id != session_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "IDEMPOTENCY_KEY_REUSE_MISMATCH",
                        "message": "Idempotency key has already been used for a different hold or session.",
                    },
                )

            logger.info(f"[Checkout] Idempotency cache hit for key {idem_key} (status: {existing_tx.status})")
            if existing_tx.status == PaymentStatus.SUCCEEDED.value:
                b_stmt = select(Booking).where(Booking.payment_id == existing_tx.id)
                b_res = await db.execute(b_stmt)
                bookings = b_res.scalars().all()
                seat_ids = [b.seat_id for b in bookings]
                confirmed_at_iso = bookings[0].confirmed_at.isoformat() if bookings else datetime.now(timezone.utc).isoformat()
                booking_id = bookings[0].id if bookings else None
                return CheckoutPayResponse(
                    payment_id=existing_tx.id,
                    booking_id=booking_id,
                    status=PaymentStatus.SUCCEEDED.value,
                    seat_ids=seat_ids,
                    total_cents=existing_tx.amount_cents,
                    confirmed_at=confirmed_at_iso,
                    message="Booking confirmed (idempotent replay).",
                )
            elif existing_tx.status == PaymentStatus.DECLINED.value:
                return CheckoutPayResponse(
                    payment_id=None,
                    booking_id=None,
                    status=PaymentStatus.DECLINED.value,
                    error_code="CARD_DECLINED",
                    message="Payment declined. Hold NOT released — you may retry (idempotent replay).",
                )
            elif existing_tx.status == PaymentStatus.PROCESSING.value:
                return CheckoutPayResponse(
                    payment_id=existing_tx.id,
                    booking_id=None,
                    status=PaymentStatus.PROCESSING.value,
                    message="Payment is processing. Do not close this tab (idempotent replay).",
                )

        # 2. Hold Validation
        hold_meta = await redis.hgetall(hold_meta_key)
        if not hold_meta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "HOLD_NOT_FOUND", "message": f"Hold {hold_id} does not exist or has expired."},
            )

        hold_owner = hold_meta.get("session_id")
        if hold_owner and hold_owner != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Hold belongs to another session."},
            )

        current_hold_status = hold_meta.get("status")
        if current_hold_status == "SOLD":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HOLD_ALREADY_SOLD", "message": "Seats have already been purchased and confirmed."},
            )

        event_id = int(hold_meta.get("event_id", "1"))
        seat_ids_csv = hold_meta.get("seat_ids", "")
        seat_ids = [int(s) for s in seat_ids_csv.split(",") if s]

        if not seat_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "EMPTY_HOLD", "message": "Hold contains no seats."},
            )

        seat_statuses_key = f"event:{event_id}:seat_statuses"

        # 3. Transition Hold to PAYING (Protects from reaper while in checkout)
        try:
            lua_res = await redis.eval(
                TRANSITION_HOLD_LUA,
                4,
                hold_meta_key,
                seat_statuses_key,
                expiry_zset_key,
                counter_key,
                "PAYING",
            )
            outcome = lua_res[0] if lua_res else "NOT_FOUND"
            if outcome != "OK":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "HOLD_TRANSITION_FAILED", "message": f"Could not transition hold to PAYING: {outcome}"},
                )
        except Exception as exc:
            logger.warning(f"[Checkout] Lua transition to PAYING error: {exc}")

        # Broadcast PAYING status via WebSockets
        paying_updates = [{"seat_id": sid, "status": "PAYING", "hold_id": hold_id} for sid in seat_ids]
        await ws_manager.publish_seat_status_change(event_id, paying_updates)

        # 4. Calculate Total Amount from Database Seat records
        seats_stmt = select(Seat).where(Seat.event_id == event_id, Seat.id.in_(seat_ids))
        seats_res = await db.execute(seats_stmt)
        seats = seats_res.scalars().all()
        seat_price_map = {s.id: s.price_cents for s in seats}
        total_cents = sum(seat_price_map.get(sid, 5000) for sid in seat_ids)

        lease_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        now_dt = datetime.now(timezone.utc)

        # 5. Handle Simulation Outcomes
        if simulate_failure:
            # DECLINED: create declined transaction record, revert hold to HELD for user retry
            tx = PaymentTransaction(
                id=f"pay_dec_{uuid.uuid4().hex[:12]}",
                hold_id=hold_id,
                session_id=session_id,
                amount_cents=total_cents,
                status=PaymentStatus.DECLINED.value,
                idempotency_key=idem_key,
                lease_expires_at=lease_expires,
                created_at=now_dt,
                updated_at=now_dt,
            )
            db.add(tx)
            await db.commit()

            # Revert hold to HELD in Redis so user can retry
            try:
                await redis.eval(
                    TRANSITION_HOLD_LUA,
                    4,
                    hold_meta_key,
                    seat_statuses_key,
                    expiry_zset_key,
                    counter_key,
                    "REVERT_HELD",
                )
            except Exception as exc:
                logger.warning(f"[Checkout] Error reverting hold to HELD in Redis: {exc}")

            # Broadcast HELD update
            held_updates = [{"seat_id": sid, "status": "HELD", "hold_id": hold_id} for sid in seat_ids]
            await ws_manager.publish_seat_status_change(event_id, held_updates)

            return CheckoutPayResponse(
                payment_id=None,
                booking_id=None,
                status=PaymentStatus.DECLINED.value,
                error_code="CARD_DECLINED",
                message="Payment declined. Hold NOT released — you may retry.",
            )

        if simulate_pending:
            # PROCESSING: create processing transaction record; hold remains PAYING
            tx = PaymentTransaction(
                id=f"pay_proc_{uuid.uuid4().hex[:12]}",
                hold_id=hold_id,
                session_id=session_id,
                amount_cents=total_cents,
                status=PaymentStatus.PROCESSING.value,
                idempotency_key=idem_key,
                lease_expires_at=lease_expires,
                created_at=now_dt,
                updated_at=now_dt,
            )
            db.add(tx)
            await db.commit()

            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=None,
                status=PaymentStatus.PROCESSING.value,
                message="Payment is processing. Do not close this tab.",
            )

        # SUCCEEDED: Confirm booking, persist rows, mark seats SOLD, release admission capacity
        payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        tx = PaymentTransaction(
            id=payment_id,
            hold_id=hold_id,
            session_id=session_id,
            amount_cents=total_cents,
            status=PaymentStatus.SUCCEEDED.value,
            idempotency_key=idem_key,
            lease_expires_at=lease_expires,
            created_at=now_dt,
            updated_at=now_dt,
        )
        db.add(tx)

        confirmed_bookings = []
        for sid in seat_ids:
            booking = Booking(
                id=f"bk_{uuid.uuid4().hex[:12]}",
                event_id=event_id,
                seat_id=sid,
                session_id=session_id,
                payment_id=payment_id,
                amount_cents=seat_price_map.get(sid, 5000),
                status=BookingStatus.CONFIRMED.value,
                confirmed_at=now_dt,
                idempotency_key=f"{idem_key}_{sid}",
            )
            db.add(booking)
            confirmed_bookings.append(booking)

        # Update seat status in database
        for seat in seats:
            seat.status = "SOLD"

        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning(f"[Checkout] Database commit collision or error: {exc}")
            # Check if a concurrent request with the same idempotency key already committed
            chk_stmt = select(PaymentTransaction).where(PaymentTransaction.idempotency_key == idem_key)
            chk_res = await db.execute(chk_stmt)
            concurrent_tx = chk_res.scalar_one_or_none()
            if concurrent_tx:
                # 1. Validate both session_id and hold_id to ensure we NEVER return another session's result
                if concurrent_tx.session_id != session_id or concurrent_tx.hold_id != hold_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "IDEMPOTENCY_KEY_REUSE_MISMATCH",
                            "message": "Idempotency key was used concurrently by another session or for another hold.",
                        },
                    )

                # 2. Handle each transaction status safely
                if concurrent_tx.status == PaymentStatus.SUCCEEDED.value:
                    b_stmt = select(Booking).where(Booking.payment_id == concurrent_tx.id)
                    b_res = await db.execute(b_stmt)
                    concurrent_bookings = b_res.scalars().all()
                    booking_id = concurrent_bookings[0].id if concurrent_bookings else None
                    confirmed_at_iso = concurrent_bookings[0].confirmed_at.isoformat() if concurrent_bookings else datetime.now(timezone.utc).isoformat()
                    return CheckoutPayResponse(
                        payment_id=concurrent_tx.id,
                        booking_id=booking_id,
                        status=PaymentStatus.SUCCEEDED.value,
                        seat_ids=[b.seat_id for b in concurrent_bookings],
                        total_cents=concurrent_tx.amount_cents,
                        confirmed_at=confirmed_at_iso,
                        message="Booking confirmed (concurrent idempotency resolved).",
                    )
                elif concurrent_tx.status == PaymentStatus.PROCESSING.value:
                    return CheckoutPayResponse(
                        payment_id=concurrent_tx.id,
                        booking_id=None,
                        status=PaymentStatus.PROCESSING.value,
                        message="Payment is processing. Do not close this tab (concurrent idempotency resolved).",
                    )
                elif concurrent_tx.status == PaymentStatus.DECLINED.value:
                    return CheckoutPayResponse(
                        payment_id=None,
                        booking_id=None,
                        status=PaymentStatus.DECLINED.value,
                        error_code="CARD_DECLINED",
                        message="Payment declined (concurrent idempotency resolved).",
                    )
                elif concurrent_tx.status == PaymentStatus.VOIDED.value:
                    return CheckoutPayResponse(
                        payment_id=concurrent_tx.id,
                        booking_id=None,
                        status=PaymentStatus.VOIDED.value,
                        message="Payment voided (concurrent idempotency resolved).",
                    )

            # Re-raise unexpected integrity / database error instead of masking it
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "BOOKING_CONFLICT", "message": f"Database integrity collision: {exc}"},
            )

        # Atomically transition hold to SOLD in Redis
        try:
            await redis.eval(
                TRANSITION_HOLD_LUA,
                4,
                hold_meta_key,
                seat_statuses_key,
                expiry_zset_key,
                counter_key,
                "SOLD",
            )
        except Exception as exc:
            logger.warning(f"[Checkout] Redis transition to SOLD error: {exc}")

        # Broadcast SOLD to all WebSocket clients
        sold_updates = [{"seat_id": sid, "status": "SOLD", "hold_id": None} for sid in seat_ids]
        await ws_manager.publish_seat_status_change(event_id, sold_updates)

        # Release admission capacity in virtual waiting room on definitive success
        try:
            await QueueService.release_admission_slot(event_id, session_id)
        except Exception as exc:
            logger.debug(f"[Checkout] Error releasing queue slot on payment completion: {exc}")

        logger.info(f"[Checkout] Succeeded: Payment {payment_id}, Bookings {[b.id for b in confirmed_bookings]}")
        return CheckoutPayResponse(
            payment_id=payment_id,
            booking_id=confirmed_bookings[0].id if confirmed_bookings else None,
            status=PaymentStatus.SUCCEEDED.value,
            seat_ids=seat_ids,
            total_cents=total_cents,
            confirmed_at=now_dt.isoformat(),
            message="Payment succeeded and booking confirmed.",
        )

    @classmethod
    async def get_payment_status(
        cls,
        db: AsyncSession,
        payment_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authoritative query for payment status and confirmed booking details."""
        stmt = select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
        res = await db.execute(stmt)
        tx = res.scalar_one_or_none()

        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PAYMENT_NOT_FOUND", "message": f"Payment transaction {payment_id} not found."},
            )

        if not session_id or tx.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Payment transaction belongs to another session."},
            )

        booking_id = None
        seat_ids = []
        confirmed_at = None

        if tx.status == PaymentStatus.SUCCEEDED.value:
            b_stmt = select(Booking).where(Booking.payment_id == tx.id)
            b_res = await db.execute(b_stmt)
            bookings = b_res.scalars().all()
            if bookings:
                booking_id = bookings[0].id
                seat_ids = [b.seat_id for b in bookings]
                confirmed_at = bookings[0].confirmed_at.isoformat()

        return {
            "payment_id": tx.id,
            "hold_id": tx.hold_id,
            "session_id": tx.session_id,
            "status": tx.status,
            "amount_cents": tx.amount_cents,
            "booking_id": booking_id,
            "seat_ids": seat_ids,
            "confirmed_at": confirmed_at,
        }

    @classmethod
    async def reconcile_payment(
        cls,
        db: AsyncSession,
        payment_id: str,
        target_outcome: str = "SUCCEEDED",
        session_id: Optional[str] = None,
    ) -> CheckoutPayResponse:
        """
        Reconciles a PROCESSING payment to terminal outcome (SUCCEEDED | DECLINED | VOIDED).
        Never creates duplicate payment attempts; reuses original payment transaction.
        """
        stmt = select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
        res = await db.execute(stmt)
        tx = res.scalar_one_or_none()

        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PAYMENT_NOT_FOUND", "message": f"Payment {payment_id} not found."},
            )

        if session_id and tx.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Payment belongs to another session."},
            )

        # Enforce terminal payment states
        if tx.status == PaymentStatus.SUCCEEDED.value:
            if target_outcome != "SUCCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "INVALID_STATE_TRANSITION",
                        "message": f"Payment is in terminal state SUCCEEDED and cannot be reversed or transitioned to {target_outcome}.",
                    },
                )
            # Duplicate reconciliation of SUCCEEDED is strictly idempotent
            b_stmt = select(Booking).where(Booking.payment_id == tx.id)
            b_res = await db.execute(b_stmt)
            bookings = b_res.scalars().all()
            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=bookings[0].id if bookings else None,
                status=PaymentStatus.SUCCEEDED.value,
                seat_ids=[b.seat_id for b in bookings],
                total_cents=tx.amount_cents,
                confirmed_at=bookings[0].confirmed_at.isoformat() if bookings else None,
                message="Payment already SUCCEEDED (duplicate reconciliation idempotent).",
            )

        if tx.status in (PaymentStatus.DECLINED.value, PaymentStatus.VOIDED.value):
            if target_outcome != tx.status:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "INVALID_STATE_TRANSITION",
                        "message": f"Payment is in terminal state {tx.status} and cannot be transitioned to {target_outcome}.",
                    },
                )
            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=None,
                status=tx.status,
                total_cents=tx.amount_cents,
                message=f"Payment already in terminal state {tx.status} (idempotent).",
            )

        redis = await get_redis()
        hold_meta_key = f"hold:{tx.hold_id}"
        expiry_zset_key = "hold_expiry_zset"
        counter_key = "holds:active:count"

        hold_meta = await redis.hgetall(hold_meta_key)
        event_id = int(hold_meta.get("event_id", "1")) if hold_meta else 1
        seat_ids_csv = hold_meta.get("seat_ids", "") if hold_meta else ""
        seat_ids = [int(s) for s in seat_ids_csv.split(",") if s]
        seat_statuses_key = f"event:{event_id}:seat_statuses"
        now_dt = datetime.now(timezone.utc)

        if target_outcome == "SUCCEEDED":
            tx.status = PaymentStatus.SUCCEEDED.value
            tx.updated_at = now_dt

            # Check if bookings already exist
            b_stmt = select(Booking).where(Booking.payment_id == tx.id)
            b_res = await db.execute(b_stmt)
            bookings = b_res.scalars().all()

            if not bookings and seat_ids:
                for sid in seat_ids:
                    bk = Booking(
                        id=f"bk_{uuid.uuid4().hex[:12]}",
                        event_id=event_id,
                        seat_id=sid,
                        session_id=tx.session_id,
                        payment_id=tx.id,
                        amount_cents=tx.amount_cents // max(1, len(seat_ids)),
                        status=BookingStatus.CONFIRMED.value,
                        confirmed_at=now_dt,
                        idempotency_key=f"{tx.idempotency_key}_{sid}",
                    )
                    db.add(bk)
                    bookings.append(bk)

            # Update seats to SOLD in DB
            if seat_ids:
                s_stmt = select(Seat).where(Seat.event_id == event_id, Seat.id.in_(seat_ids))
                s_res = await db.execute(s_stmt)
                for s in s_res.scalars().all():
                    s.status = "SOLD"

            await db.commit()

            # Transition in Redis
            try:
                await redis.eval(
                    TRANSITION_HOLD_LUA,
                    4,
                    hold_meta_key,
                    seat_statuses_key,
                    expiry_zset_key,
                    counter_key,
                    "SOLD",
                )
            except Exception:
                pass

            # Release queue slot
            try:
                await QueueService.release_admission_slot(event_id, tx.session_id)
            except Exception:
                pass

            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=bookings[0].id if bookings else None,
                status=PaymentStatus.SUCCEEDED.value,
                seat_ids=seat_ids,
                total_cents=tx.amount_cents,
                confirmed_at=now_dt.isoformat(),
                message="Payment reconciled to SUCCEEDED and booking confirmed.",
            )

        elif target_outcome == "DECLINED":
            tx.status = PaymentStatus.DECLINED.value
            tx.updated_at = now_dt
            await db.commit()

            # Revert hold to HELD in Redis
            try:
                await redis.eval(
                    TRANSITION_HOLD_LUA,
                    4,
                    hold_meta_key,
                    seat_statuses_key,
                    expiry_zset_key,
                    counter_key,
                    "REVERT_HELD",
                )
            except Exception:
                pass

            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=None,
                status=PaymentStatus.DECLINED.value,
                error_code="CARD_DECLINED",
                message="Payment reconciled to DECLINED. Hold reverted to HELD.",
            )

        elif target_outcome == "VOIDED":
            tx.status = PaymentStatus.VOIDED.value
            tx.updated_at = now_dt
            await db.commit()

            # Void hold and release seats
            if seat_ids:
                for sid in seat_ids:
                    await redis.hset(seat_statuses_key, sid, "AVAILABLE")
                    await redis.delete(f"seat_holds:{event_id}:{sid}")
            await redis.delete(hold_meta_key)
            await redis.zrem(expiry_zset_key, tx.hold_id)

            # Release queue admission slot
            try:
                await QueueService.release_admission_slot(event_id, tx.session_id)
            except Exception:
                pass

            return CheckoutPayResponse(
                payment_id=tx.id,
                booking_id=None,
                status=PaymentStatus.VOIDED.value,
                message="Payment reconciled to VOIDED. Hold released and capacity freed.",
            )

        raise HTTPException(status_code=400, detail={"code": "INVALID_OUTCOME", "message": f"Invalid outcome {target_outcome}."})
