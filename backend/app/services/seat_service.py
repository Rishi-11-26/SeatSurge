from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.seat import Seat, SeatStatus, SeatTier
from app.models.booking import Booking, BookingStatus
from app.redis.client import get_redis
from app.services.metrics_service import metrics_tracker


class SeatService:

    @staticmethod
    async def get_redis_seat_statuses(event_id: int) -> Dict[int, str]:
        """Fetches temporary hold states (HELD, PAYING) from Redis hash overlay."""
        statuses: Dict[int, str] = {}
        try:
            redis = await get_redis()
            cached = await redis.hgetall(f"event:{event_id}:seat_statuses")
            if cached:
                metrics_tracker.record_cache(hit=True)
                for k, v in cached.items():
                    statuses[int(k)] = v
            else:
                metrics_tracker.record_cache(hit=False)
        except Exception:
            metrics_tracker.record_cache(hit=False)
        return statuses

    @staticmethod
    async def get_event_seats(
        session: AsyncSession,
        event_id: int,
        page: int = 1,
        page_size: int = 100,
        tier: Optional[str] = None,
        row: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieves paginated seats with real-time status overlay.

        Status priority:
            SOLD  — a CONFIRMED Booking row exists in PostgreSQL (durable truth).
            HELD/PAYING — a Redis entry exists (ephemeral, Phase 2+).
            AVAILABLE — no booking row and no Redis entry.

        Only CONFIRMED bookings count as SOLD.
        CANCELLED and REFUNDED bookings do not block the seat.
        """
        stmt = select(Seat).where(Seat.event_id == event_id)
        count_stmt = select(func.count(Seat.id)).where(Seat.event_id == event_id)

        if tier:
            stmt = stmt.where(Seat.tier == tier.upper())
            count_stmt = count_stmt.where(Seat.tier == tier.upper())
        if row:
            stmt = stmt.where(Seat.row == row.upper())
            count_stmt = count_stmt.where(Seat.row == row.upper())

        total_res = await session.execute(count_stmt)
        total_count = total_res.scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Seat.id).offset(offset).limit(page_size)
        result = await session.execute(stmt)
        seats = list(result.scalars().all())

        # Only CONFIRMED bookings mark a seat as permanently SOLD.
        seat_ids = [s.id for s in seats]
        sold_seat_ids: set[int] = set()
        if seat_ids:
            sold_stmt = select(Booking.seat_id).where(
                Booking.event_id == event_id,
                Booking.seat_id.in_(seat_ids),
                Booking.status == BookingStatus.CONFIRMED.value,
            )
            sold_res = await session.execute(sold_stmt)
            sold_seat_ids = set(sold_res.scalars().all())

        # Redis holds overlay (HELD / PAYING from Phase 2 Lua scripts)
        redis_statuses = await SeatService.get_redis_seat_statuses(event_id)

        seat_data = []
        for s in seats:
            if s.id in sold_seat_ids:
                status = SeatStatus.SOLD.value
            elif s.id in redis_statuses:
                status = redis_statuses[s.id]
            else:
                status = SeatStatus.AVAILABLE.value

            seat_data.append({
                "seat_id": s.id,          # Field name matches API contract §4
                "id": s.id,               # Retained as alias for frontend component compatibility
                "event_id": s.event_id,
                "row": s.row,
                "number": s.number,
                "section": s.section,
                "tier": s.tier,
                "price_cents": s.price_cents,
                "is_accessible": s.is_accessible,
                "status": status,
            })

        return seat_data, total_count

    @staticmethod
    async def get_seat_by_id(
        session: AsyncSession,
        event_id: int,
        seat_id: int,
    ) -> Optional[Dict[str, Any]]:
        stmt = select(Seat).where(Seat.event_id == event_id, Seat.id == seat_id)
        result = await session.execute(stmt)
        seat = result.scalar_one_or_none()
        if not seat:
            return None

        # Only CONFIRMED bookings count as sold
        sold_stmt = select(Booking.seat_id).where(
            Booking.event_id == event_id,
            Booking.seat_id == seat_id,
            Booking.status == BookingStatus.CONFIRMED.value,
        )
        sold_res = await session.execute(sold_stmt)
        is_sold = sold_res.scalar_one_or_none() is not None

        if is_sold:
            status = SeatStatus.SOLD.value
        else:
            redis_statuses = await SeatService.get_redis_seat_statuses(event_id)
            status = redis_statuses.get(seat_id, SeatStatus.AVAILABLE.value)

        return {
            "seat_id": seat.id,           # Field name matches API contract §4
            "id": seat.id,                # Retained as alias for frontend component compatibility
            "event_id": seat.event_id,
            "row": seat.row,
            "number": seat.number,
            "section": seat.section,
            "tier": seat.tier,
            "price_cents": seat.price_cents,
            "is_accessible": seat.is_accessible,
            "status": status,
        }

    @staticmethod
    async def get_seat_availability_summary(
        session: AsyncSession,
        event_id: int,
    ) -> Dict[str, Any]:
        """Tier-level availability summary.

        Sold count: CONFIRMED bookings only (CANCELLED/REFUNDED do not reduce availability).
        Held count: sourced from Redis counter 'holds:active:count' (Phase 2+).
        """
        # Total seats per tier
        stmt = select(
            Seat.tier,
            Seat.price_cents,
            func.count(Seat.id),
        ).where(Seat.event_id == event_id).group_by(Seat.tier, Seat.price_cents)
        res = await session.execute(stmt)
        tier_totals = res.all()

        # CONFIRMED sold count per tier only
        sold_stmt = (
            select(Seat.tier, func.count(Booking.id))
            .join(Seat, Seat.id == Booking.seat_id)
            .where(
                Booking.event_id == event_id,
                Booking.status == BookingStatus.CONFIRMED.value,
            )
            .group_by(Seat.tier)
        )
        sold_res = await session.execute(sold_stmt)
        sold_by_tier = {tier: count for tier, count in sold_res.all()}

        # Active hold count from Redis counter (Phase 2 Lua scripts maintain this key)
        held_count = 0
        try:
            redis = await get_redis()
            raw = await redis.get("holds:active:count")
            if raw is not None:
                held_count = int(raw)
        except Exception:
            held_count = 0  # Redis unavailable — report 0, Phase 2 will maintain counter

        tiers_dict = {}
        total_seats = 0
        total_sold = 0

        for tier, price, count in tier_totals:
            sold_count = sold_by_tier.get(tier, 0)
            available = max(0, count - sold_count)
            tiers_dict[tier] = {
                "tier": tier,
                "total": count,
                "available": available,
                "held": 0,     # Per-tier breakdown deferred to Phase 2
                "sold": sold_count,
                "price_cents": price,
            }
            total_seats += count
            total_sold += sold_count

        return {
            "event_id": event_id,
            "total_seats": total_seats,
            "available_seats": max(0, total_seats - total_sold - held_count),
            "held_seats": held_count,
            "sold_seats": total_sold,
            "tiers": tiers_dict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
