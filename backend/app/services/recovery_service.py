import uuid
import asyncio
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from app.redis.client import get_redis
from app.redis.scripts import (
    COMPARE_AND_EXTEND_LOCK_LUA,
    COMPARE_AND_DELETE_LOCK_LUA,
)
from app.models.booking import Booking, BookingStatus
from app.models.payment import PaymentTransaction, PaymentStatus
from app.core.logging import logger

RECOVERY_LOCK_KEY = "redis_recovery_lock"
RECOVERY_LOCK_TTL = 30  # seconds
RECOVERY_GATE_KEY = "redis_recovery_in_progress"

# ---------------------------------------------------------------------------
# Module-level recovery state flags (per application-process lifetime)
# ---------------------------------------------------------------------------
_recovery_complete: bool = False
_recovery_skipped: bool = False


def mark_recovery_complete() -> None:
    """Call after a successful state reconstruction (or in test mode)."""
    global _recovery_complete, _recovery_skipped
    _recovery_complete = True
    _recovery_skipped = False


def mark_recovery_skipped() -> None:
    """Call when recovery could not run (Redis unavailable, timeout, etc.)."""
    global _recovery_skipped
    _recovery_skipped = True


def reset_recovery_state() -> None:
    """Reset both flags. Used in test fixtures to simulate a fresh process."""
    global _recovery_complete, _recovery_skipped
    _recovery_complete = False
    _recovery_skipped = False


def is_recovery_complete() -> bool:
    """
    Returns True only when recovery has successfully finished this process
    lifetime.  Readiness probe must check this before serving booking traffic.
    """
    return _recovery_complete


class RedisRecoveryService:
    @staticmethod
    async def reconstruct_state_from_postgres(
        engine: AsyncEngine,
        event_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Reconstructs authoritative SOLD and PAYING state in Redis after restart/loss.

        Protocol:
        1. Acquire distributed recovery lock with UUID owner token.
        2. Set recovery gate flag 'redis_recovery_in_progress' to block new holds.
        3. Query PostgreSQL for all CONFIRMED bookings -> mark SOLD in Redis hash.
        4. Query PostgreSQL for all PROCESSING payments -> mark PAYING in Redis hash.
        5. Atomically reset active holds counter.
        6. Release recovery gate.
        7. Release distributed lock using compare-token-and-delete Lua.
        """
        try:
            redis = await get_redis()
        except Exception as e:
            logger.warning(f"Cannot perform Redis recovery: Redis unavailable ({e})")
            mark_recovery_skipped()
            return {"status": "SKIPPED", "reason": "REDIS_UNAVAILABLE"}

        owner_token = f"rec_owner_{uuid.uuid4().hex}"

        # 1. Attempt to acquire distributed recovery lock (SET NX EX)
        acquired = await redis.set(RECOVERY_LOCK_KEY, owner_token, nx=True, ex=RECOVERY_LOCK_TTL)
        if not acquired:
            logger.info("Another backend instance is performing Redis state recovery. Waiting...")
            # Wait for peer to complete recovery
            for _ in range(20):
                await asyncio.sleep(0.5)
                in_prog = await redis.get(RECOVERY_GATE_KEY)
                if not in_prog:
                    logger.info("Peer instance completed Redis recovery.")
                    mark_recovery_complete()
                    return {"status": "COMPLETED_BY_PEER"}
            mark_recovery_skipped()
            return {"status": "TIMED_OUT_WAITING_FOR_PEER"}

        logger.info(f"Acquired Redis recovery lock (token={owner_token}). Beginning state reconstruction...")

        try:
            # 2. Block incoming hold requests via gate key
            await redis.set(RECOVERY_GATE_KEY, "1", ex=RECOVERY_LOCK_TTL)

            sold_count = 0
            paying_count = 0
            seat_statuses_key = f"event:{event_id}:seat_statuses"

            # 3. Query PostgreSQL for confirmed sales
            async with AsyncSession(engine) as session:
                # Confirmed sales
                sold_stmt = select(Booking.seat_id).where(
                    Booking.event_id == event_id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                )
                sold_res = await session.execute(sold_stmt)
                sold_seat_ids = list(sold_res.scalars().all())

                if sold_seat_ids:
                    # Pipe in batches to avoid network bottlenecks
                    pipe = redis.pipeline()
                    for sid in sold_seat_ids:
                        pipe.hset(seat_statuses_key, str(sid), "SOLD")
                    await pipe.execute()
                    sold_count = len(sold_seat_ids)

                # Active in-flight payments (lease not expired)
                # Note: Payment simulator integration in Phase 6 will use this
                paying_stmt = select(PaymentTransaction.hold_id).where(
                    PaymentTransaction.status == PaymentStatus.PROCESSING.value
                )
                paying_res = await session.execute(paying_stmt)
                paying_hold_ids = list(paying_res.scalars().all())

                if paying_hold_ids:
                    logger.info(f"Reconstructed {len(paying_hold_ids)} in-flight payments as PAYING.")
                    paying_count = len(paying_hold_ids)

            # 4. Reset holds counter (ephemeral HELD state was discarded during Redis restart)
            await redis.set("holds:active:count", "0")

            logger.info(
                f"Redis state reconstruction complete: {sold_count} seats marked SOLD, "
                f"{paying_count} marked PAYING."
            )
            mark_recovery_complete()
            return {
                "status": "SUCCESS",
                "sold_reconstructed": sold_count,
                "paying_reconstructed": paying_count,
            }

        finally:
            # 5. Clear recovery gate key
            try:
                await redis.delete(RECOVERY_GATE_KEY)
            except Exception:
                pass

            # 6. Release lock using atomic compare-token-and-delete Lua
            try:
                del_res = await redis.eval(
                    COMPARE_AND_DELETE_LOCK_LUA,
                    1,
                    RECOVERY_LOCK_KEY,
                    owner_token,
                )
                if del_res == 1:
                    logger.info("Successfully released Redis recovery lock.")
                else:
                    logger.warning("Recovery lock had already expired or was taken by another instance.")
            except Exception as e:
                logger.error(f"Error releasing recovery lock: {e}")

    @staticmethod
    async def renew_recovery_lock(owner_token: str, extend_seconds: int = 15) -> bool:
        """Atomically renews recovery lock TTL if caller is still the current owner."""
        try:
            redis = await get_redis()
            res = await redis.eval(
                COMPARE_AND_EXTEND_LOCK_LUA,
                1,
                RECOVERY_LOCK_KEY,
                owner_token,
                str(extend_seconds),
            )
            return res == 1
        except Exception:
            return False
