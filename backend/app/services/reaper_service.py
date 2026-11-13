import asyncio
import time
from typing import List, Tuple
from app.redis.client import get_redis
from app.redis.scripts import REAP_EXPIRED_HOLD_LUA
from app.core.logging import logger

REAPER_INTERVAL_SECONDS = 5
MAX_REAP_BATCH_SIZE = 100


async def reap_expired_holds_once() -> Tuple[int, int]:
    """
    Executes a single sweep to harvest and release expired HELD holds.

    EXPIRY LIFECYCLE:
    - Hold TTL (logical expiry): 120 seconds from hold creation.
    - After logical expiry, the hold is eligible for collection by the reaper.
    - The reaper runs on a fixed interval (default: 5 seconds).
    - Maximum elapsed time before seat release: 120 s (TTL) + up to 5 s (reaper
      interval) = up to 125 seconds under normal event-loop load.
    - Under high event-loop saturation or scheduler jitter the actual release
      time MAY exceed 125 seconds.  An unconditional "5-second release guarantee"
      MUST NOT be claimed based solely on asyncio.sleep(5).  Actual reaper delay
      should be measured with real Redis integration / load testing.

    Guarantees:
    - Never releases a PAYING hold (payment in-flight).
    - Uses atomic Lua script to release seats, delete metadata, prune zset, and
      decrement counter — preventing double-decrement under concurrent sweeps.
    - Returns (reaped_holds_count, reaped_seats_count).
    """
    try:
        redis = await get_redis()
    except Exception as exc:
        logger.warning(f"Reaper cannot connect to Redis: {exc}")
        return 0, 0

    now = int(time.time())
    expiry_zset_key = "hold_expiry_zset"
    counter_key = "holds:active:count"

    # Clean up expired queue admissions and promote waiting sessions even if no new client polls
    try:
        from app.services.queue_service import QueueService
        await QueueService.cleanup_expired_admissions(event_id=1)
    except Exception as exc:
        logger.debug(f"Error running queue admission cleanup in reaper: {exc}")

    try:
        # Find all holds where expires_at <= current time
        # Using zrangebyscore with limit to prevent blocking event loop on large bursts
        expired_holds = await redis.zrangebyscore(
            expiry_zset_key,
            min=0,
            max=now,
            start=0,
            num=MAX_REAP_BATCH_SIZE,
        )
    except Exception as exc:
        logger.warning(f"Error querying expired holds: {exc}")
        return 0, 0

    if not expired_holds:
        return 0, 0

    total_reaped_holds = 0
    total_reaped_seats = 0

    for hold_id in expired_holds:
        hold_meta_key = f"hold:{hold_id}"
        # Inspect event_id from hold metadata or default to 1
        event_id = 1
        try:
            stored_event = await redis.hget(hold_meta_key, "event_id")
            if stored_event:
                event_id = int(stored_event)
        except Exception:
            pass

        seat_statuses_key = f"event:{event_id}:seat_statuses"
        session_id = None
        try:
            stored_session = await redis.hget(hold_meta_key, "session_id")
            if stored_session:
                session_id = stored_session
        except Exception:
            pass

        try:
            lua_res = await redis.eval(
                REAP_EXPIRED_HOLD_LUA,
                4,
                hold_meta_key,
                seat_statuses_key,
                expiry_zset_key,
                counter_key,
                hold_id,
            )
            outcome = lua_res[0] if lua_res else "NOT_FOUND"
            if outcome == "REAPED":
                num_seats = int(lua_res[1]) if len(lua_res) > 1 else 0
                seat_ids = lua_res[2] if len(lua_res) > 2 else ""
                total_reaped_holds += 1
                total_reaped_seats += num_seats
                logger.info(f"Reaper released expired hold {hold_id} ({num_seats} seats: [{seat_ids}])")

                # Broadcast seat release to WebSocket subscribers
                if seat_ids:
                    try:
                        from app.services.websocket_service import ws_manager
                        reaped_ids = [int(s) for s in seat_ids.split(",") if s]
                        updates = [{"seat_id": sid, "status": "AVAILABLE", "hold_id": None} for sid in reaped_ids]
                        await ws_manager.publish_seat_status_change(event_id, updates)
                    except Exception as exc:
                        logger.warning(f"Failed to broadcast reaper release to WebSockets: {exc}")

                # Release queue capacity slot and promote next waiting user in FIFO queue
                if session_id:
                    try:
                        from app.services.queue_service import QueueService
                        await QueueService.release_admission_slot(event_id, session_id)
                    except Exception as q_err:
                        logger.debug(f"Failed to release queue slot on reaper expiry: {q_err}")
            elif outcome == "PROTECTED_PAYING":
                logger.debug(f"Hold {hold_id} is in PAYING state. Excluded from reaper sweep.")
        except Exception as exc:
            logger.error(f"Error reaping hold {hold_id}: {exc}")

    return total_reaped_holds, total_reaped_seats


class ExpiryReaperTask:
    def __init__(self, interval_seconds: int = REAPER_INTERVAL_SECONDS):
        self.interval = interval_seconds
        self._running = False
        self._task: asyncio.Task = None

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info(f"Started Hold Expiry Reaper (sweep interval: {self.interval}s)")

    async def stop(self) -> None:
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Stopped Hold Expiry Reaper.")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await reap_expired_holds_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in Hold Expiry Reaper loop: {e}")
            await asyncio.sleep(self.interval)


hold_expiry_reaper = ExpiryReaperTask()
