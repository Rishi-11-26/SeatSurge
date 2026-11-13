import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from app.models.event import Event
from app.models.seat import Seat, SeatTier
from app.models.booking import Booking, BookingStatus
from app.services.booking_service import BookingService, BookingConflictError
from app.db.init_db import init_db, verify_seat_distribution, EXPECTED_TOTAL_SEATS


@pytest.mark.asyncio
async def test_seeding_5040_seats(db_session_factory):
    async with db_session_factory() as session:
        # 1. Total seats count
        count_stmt = select(func.count(Seat.id)).where(Seat.event_id == 1)
        res = await session.execute(count_stmt)
        total_seats = res.scalar()
        assert total_seats == 5040, f"Expected 5,040 seats, got {total_seats}"

        # 2. VIP seats (4 rows * 60 = 240)
        vip_stmt = select(func.count(Seat.id)).where(Seat.event_id == 1, Seat.tier == SeatTier.VIP.value)
        vip_res = await session.execute(vip_stmt)
        vip_count = vip_res.scalar()
        assert vip_count == 240, f"Expected 240 VIP seats, got {vip_count}"

        # 3. PREMIUM seats (12 rows * 100 = 1200)
        prem_stmt = select(func.count(Seat.id)).where(Seat.event_id == 1, Seat.tier == SeatTier.PREMIUM.value)
        prem_res = await session.execute(prem_stmt)
        prem_count = prem_res.scalar()
        assert prem_count == 1200, f"Expected 1,200 PREMIUM seats, got {prem_count}"

        # 4. STANDARD seats (18 rows * 200 = 3600)
        std_stmt = select(func.count(Seat.id)).where(Seat.event_id == 1, Seat.tier == SeatTier.STANDARD.value)
        std_res = await session.execute(std_stmt)
        std_count = std_res.scalar()
        assert std_count == 3600, f"Expected 3,600 STANDARD seats, got {std_count}"

        # 5. Verify authoritative tier pricing
        vip_p = (await session.execute(select(Seat.price_cents).where(Seat.tier == SeatTier.VIP.value).limit(1))).scalar()
        prem_p = (await session.execute(select(Seat.price_cents).where(Seat.tier == SeatTier.PREMIUM.value).limit(1))).scalar()
        std_p = (await session.execute(select(Seat.price_cents).where(Seat.tier == SeatTier.STANDARD.value).limit(1))).scalar()
        assert vip_p == 15000, f"Expected VIP price 15000, got {vip_p}"
        assert prem_p == 7500, f"Expected PREMIUM price 7500, got {prem_p}"
        assert std_p == 3500, f"Expected STANDARD price 3500, got {std_p}"


@pytest.mark.asyncio
async def test_booking_unique_constraint(db_session_factory):
    """
    CRITICAL ARCHITECTURAL GUARANTEE:
    Partial unique index on (event_id, seat_id) WHERE status = 'CONFIRMED'
    guarantees zero duplicate confirmed sales under any concurrent condition.
    """
    async with db_session_factory() as session:
        seat_id = 10
        # Create first confirmed booking
        booking1 = Booking(
            event_id=1,
            seat_id=seat_id,
            session_id="session-user-1",
            payment_id="pay_test_001",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=f"key_{uuid.uuid4().hex}",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(booking1)
        await session.commit()

        # Attempt duplicate confirmed booking for the exact same event and seat
        booking2 = Booking(
            event_id=1,
            seat_id=seat_id,
            session_id="session-user-2",
            payment_id="pay_test_002",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=f"key_{uuid.uuid4().hex}",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(booking2)

        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()


@pytest.mark.asyncio
async def test_booking_cancellation_and_rebooking(db_session_factory):
    """
    CRITICAL LIFECYCLE REQUIREMENT:
    1. Confirm a booking on a seat.
    2. Cancel the booking (history preserved with status='CANCELLED' and cancelled_at timestamp).
    3. The same seat can now be booked again by another session (status='CONFIRMED').
    4. Both booking records are retained in database for audit integrity.
    5. A 3rd booking while booking 2 is active must be rejected.
    """
    async with db_session_factory() as session:
        seat_id = 50

        # Step 1: Confirm first booking
        booking1 = Booking(
            id=str(uuid.uuid4()),
            event_id=1,
            seat_id=seat_id,
            session_id="session-initial-buyer",
            payment_id="pay_init_123",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=f"key_init_{uuid.uuid4().hex}",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(booking1)
        await session.commit()

        # Step 2: Cancel first booking (do NOT delete history)
        booking1.status = BookingStatus.CANCELLED.value
        booking1.cancelled_at = datetime.now(timezone.utc)
        booking1.cancellation_reason = "Customer change of mind"
        await session.commit()

        # Step 3: Re-book the same seat for a second customer -> MUST SUCCEED
        booking2 = Booking(
            id=str(uuid.uuid4()),
            event_id=1,
            seat_id=seat_id,
            session_id="session-second-buyer",
            payment_id="pay_second_456",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=f"key_second_{uuid.uuid4().hex}",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(booking2)
        await session.commit()

        # Step 4: Verify both records exist in DB
        history_stmt = select(Booking).where(Booking.event_id == 1, Booking.seat_id == seat_id)
        history_res = await session.execute(history_stmt)
        records = history_res.scalars().all()
        assert len(records) == 2, f"Expected 2 historical bookings, found {len(records)}"
        statuses = {r.status for r in records}
        assert statuses == {BookingStatus.CANCELLED.value, BookingStatus.CONFIRMED.value}

        # Step 5: Attempting a 3rd confirmed booking while booking 2 is active must fail
        booking3 = Booking(
            id=str(uuid.uuid4()),
            event_id=1,
            seat_id=seat_id,
            session_id="session-third-buyer",
            payment_id="pay_third_789",
            amount_cents=15000,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=f"key_third_{uuid.uuid4().hex}",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(booking3)
        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()


@pytest.mark.asyncio
async def test_idempotent_booking_workflow(db_session_factory):
    """
    CRITICAL IDEMPOTENCY REQUIREMENT:
    1. First request with Idempotency-Key creates the booking (is_new=True).
    2. Repeated request with the SAME Idempotency-Key returns the existing booking (is_new=False).
    3. Request with a DIFFERENT Idempotency-Key for the same sold seat raises BookingConflictError (409).
    """
    async with db_session_factory() as session:
        seat_id = 75
        idem_key = f"idem_test_{uuid.uuid4().hex}"

        # 1. Initial checkout request
        booking_first, is_new = await BookingService.confirm_booking_idempotent(
            session=session,
            event_id=1,
            seat_id=seat_id,
            session_id="session-user-alpha",
            payment_id="pay_alpha_01",
            amount_cents=15000,
            idempotency_key=idem_key,
        )
        assert is_new is True
        assert booking_first.idempotency_key == idem_key
        assert booking_first.status == BookingStatus.CONFIRMED.value

        # 2. Duplicate retry with same idempotency key
        booking_retry, is_retry_new = await BookingService.confirm_booking_idempotent(
            session=session,
            event_id=1,
            seat_id=seat_id,
            session_id="session-user-alpha",
            payment_id="pay_alpha_01",
            amount_cents=15000,
            idempotency_key=idem_key,
        )
        assert is_retry_new is False
        assert booking_retry.id == booking_first.id

        # 3. Conflicting request with DIFFERENT idempotency key for same seat -> 409 Conflict
        different_key = f"idem_different_{uuid.uuid4().hex}"
        with pytest.raises(BookingConflictError) as exc_info:
            await BookingService.confirm_booking_idempotent(
                session=session,
                event_id=1,
                seat_id=seat_id,
                session_id="session-user-beta",
                payment_id="pay_beta_02",
                amount_cents=15000,
                idempotency_key=different_key,
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_seat_row_num_uniqueness(db_session_factory):
    """Ensures duplicate seat coordinates (row, number) within same event are prohibited."""
    async with db_session_factory() as session:
        duplicate_seat = Seat(
            event_id=1,
            row="A",
            number=1,  # Row A Number 1 already seeded
            section="Floor VIP",
            tier=SeatTier.VIP.value,
            price_cents=15000,
            is_accessible=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(duplicate_seat)
        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()


@pytest.mark.asyncio
async def test_init_db_repeated_and_recovery(db_session_factory):
    """
    CRITICAL DATABASE SEEDING REQUIREMENT:
    1. Repeated execution on fully seeded database is an idempotent no-op.
    2. Simulated partial-seed (deleting seats) is safely recovered and filled.
    3. Layout and tier distribution validation passes.
    """
    # 1. Repeated run on existing full DB
    from tests.conftest import test_engine
    await init_db(test_engine)

    async with db_session_factory() as session:
        is_valid = await verify_seat_distribution(session, event_id=1)
        assert is_valid is True

        # 2. Simulate partial seed: delete 20 seats (e.g. from row D)
        del_stmt = delete(Seat).where(Seat.event_id == 1, Seat.row == "D", Seat.number <= 20)
        await session.execute(del_stmt)
        await session.commit()

        count_res = await session.execute(select(func.count(Seat.id)).where(Seat.event_id == 1))
        assert count_res.scalar() == EXPECTED_TOTAL_SEATS - 20

    # 3. Run init_db to recover missing seats
    await init_db(test_engine)

    async with db_session_factory() as session:
        # Must be back to exactly 5,040 seats with perfect distribution
        count_res = await session.execute(select(func.count(Seat.id)).where(Seat.event_id == 1))
        assert count_res.scalar() == EXPECTED_TOTAL_SEATS

        is_valid = await verify_seat_distribution(session, event_id=1)
        assert is_valid is True
