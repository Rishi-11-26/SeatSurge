import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.booking import Booking, BookingStatus
from app.core.logging import logger


class BookingConflictError(HTTPException):
    def __init__(self, detail: str, seat_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": detail, "conflicting_seats": [seat_id]},
        )


class BookingService:
    @staticmethod
    async def get_booking_by_idempotency_key(
        session: AsyncSession,
        idempotency_key: str,
    ) -> Optional[Booking]:
        """Looks up existing booking by client idempotency key."""
        stmt = select(Booking).where(Booking.idempotency_key == idempotency_key)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_active_booking_for_seat(
        session: AsyncSession,
        event_id: int,
        seat_id: int,
    ) -> Optional[Booking]:
        """Returns active CONFIRMED booking for (event_id, seat_id), if any."""
        stmt = select(Booking).where(
            Booking.event_id == event_id,
            Booking.seat_id == seat_id,
            Booking.status == BookingStatus.CONFIRMED.value,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def confirm_booking_idempotent(
        session: AsyncSession,
        event_id: int,
        seat_id: int,
        session_id: str,
        payment_id: str,
        amount_cents: int,
        idempotency_key: str,
        user_id: Optional[str] = None,
    ) -> Tuple[Booking, bool]:
        """
        Confirms a seat booking with strict idempotency and zero double-booking guarantee.

        Returns:
            Tuple[Booking, bool]: (booking_record, is_newly_created)

        Idempotency workflow:
            1. Query by idempotency_key. If found, return existing record (is_new=False).
            2. Check if seat already has an active CONFIRMED booking. If so, raise 409 Conflict.
            3. Insert new CONFIRMED booking.
            4. If concurrent INSERT triggers UniqueConstraint on idempotency_key:
               lookup and return the winner's record (idempotent retry).
            5. If concurrent INSERT triggers partial unique index (already confirmed):
               catch IntegrityError and raise HTTP 409 Conflict (not a 500 error).
        """
        # 1. Check if this exact request was already processed
        existing = await BookingService.get_booking_by_idempotency_key(session, idempotency_key)
        if existing:
            logger.info(f"Idempotent hit for key {idempotency_key} -> returning existing booking {existing.id}")
            return existing, False

        # 2. Check if seat is already actively confirmed
        active_booking = await BookingService.get_active_booking_for_seat(session, event_id, seat_id)
        if active_booking:
            raise BookingConflictError(
                detail=f"Seat {seat_id} for event {event_id} is already confirmed as sold.",
                seat_id=seat_id,
            )

        # 3. Create new CONFIRMED booking
        new_booking = Booking(
            id=str(uuid.uuid4()),
            event_id=event_id,
            seat_id=seat_id,
            session_id=session_id,
            user_id=user_id,
            payment_id=payment_id,
            amount_cents=amount_cents,
            status=BookingStatus.CONFIRMED.value,
            idempotency_key=idempotency_key,
            confirmed_at=datetime.now(timezone.utc),
        )

        session.add(new_booking)
        try:
            await session.commit()
            await session.refresh(new_booking)
            return new_booking, True
        except IntegrityError as exc:
            await session.rollback()
            exc_str = str(exc).lower()

            # Concurrent duplicate idempotency key race: return existing booking
            if "idempotency_key" in exc_str:
                existing = await BookingService.get_booking_by_idempotency_key(session, idempotency_key)
                if existing:
                    return existing, False

            # Concurrent different keys competing for the same seat: raise 409 Conflict
            logger.warning(f"Concurrent booking conflict on seat {seat_id} for event {event_id}: {exc}")
            raise BookingConflictError(
                detail=f"Seat {seat_id} was just booked by another concurrent transaction.",
                seat_id=seat_id,
            )

    @staticmethod
    async def cancel_booking(
        session: AsyncSession,
        booking_id: str,
        reason: Optional[str] = "Customer requested cancellation",
    ) -> Optional[Booking]:
        """
        Transitions a booking from CONFIRMED to CANCELLED.
        Preserves the booking record for audit history.
        The seat is immediately freed for future bookings.
        """
        stmt = select(Booking).where(Booking.id == booking_id)
        res = await session.execute(stmt)
        booking = res.scalar_one_or_none()
        if not booking:
            return None

        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancellation_reason = reason

        await session.commit()
        await session.refresh(booking)
        logger.info(f"Booking {booking_id} cancelled. Seat {booking.seat_id} is now available again.")
        return booking

    @staticmethod
    async def refund_booking(
        session: AsyncSession,
        booking_id: str,
        refund_id: str,
    ) -> Optional[Booking]:
        """
        Transitions a booking from CONFIRMED to REFUNDED.
        Preserves full audit trail and links the refund transaction identifier.
        """
        stmt = select(Booking).where(Booking.id == booking_id)
        res = await session.execute(stmt)
        booking = res.scalar_one_or_none()
        if not booking:
            return None

        booking.status = BookingStatus.REFUNDED.value
        booking.refund_id = refund_id
        booking.cancelled_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(booking)
        logger.info(f"Booking {booking_id} refunded (refund_id={refund_id}).")
        return booking
