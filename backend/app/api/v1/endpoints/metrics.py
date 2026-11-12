"""
GET /api/v1/metrics — Per-instance monitoring snapshot.

IMPORTANT NOTES:
  - All values are LOCAL to the responding backend instance.
  - active_holds_count is sourced from Redis counter key 'holds:active:count'.
    Phase 2 Lua scripts maintain this counter atomically (INCR on hold creation,
    DECR on hold release). It is NOT computed via KEYS — that command is O(N)
    and blocks Redis under load.
  - sold_seats_count counts only CONFIRMED bookings (not CANCELLED/REFUNDED).
"""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.redis.client import get_redis
from app.schemas.metrics import MetricsResponse
from app.services.metrics_service import metrics_tracker

router = APIRouter(prefix="/metrics", tags=["Monitoring & Diagnostics"])


@router.get("", response_model=MetricsResponse)
async def get_system_metrics(db: AsyncSession = Depends(get_db)):
    """
    Authoritative per-instance monitoring dashboard.

    Returns process-local counters for RPS, latency percentiles, cache ratio,
    active holds (from Redis counter), and confirmed sold seats (from PostgreSQL).
    """

    # Count CONFIRMED sold seats from PostgreSQL (authoritative durable truth)
    sold_count = 0
    try:
        stmt = select(func.count(Booking.id)).where(
            Booking.status == BookingStatus.CONFIRMED.value
        )
        res = await db.execute(stmt)
        sold_count = res.scalar() or 0
    except Exception:
        pass

    # Active hold count from Redis counter key maintained by Phase 2 Lua scripts.
    # NEVER use KEYS hold:* — it is O(N) and blocks the entire Redis server under load.
    active_holds: Optional[int] = None
    try:
        redis = await get_redis()
        raw = await redis.get("holds:active:count")
        if raw is not None:
            active_holds = int(raw)
        else:
            # Key does not exist yet — Phase 2 has not run any holds.
            # Return 0 (not null) to indicate Redis is reachable but no holds recorded.
            active_holds = 0
    except Exception:
        # Redis unavailable — return null so callers can distinguish
        # "zero holds" from "unknown / Redis down".
        active_holds = None

    metrics_data = metrics_tracker.get_metrics_snapshot(
        active_holds=active_holds,
        sold_seats=sold_count,
    )
    return MetricsResponse(**metrics_data)
