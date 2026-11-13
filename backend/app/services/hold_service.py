import json
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.seat import Seat, SeatStatus
from app.schemas.hold import HoldResponse, HoldReleaseResponse
from app.redis.client import get_redis
from app.redis.scripts import (
    CLAIM_HOLD_LUA,
    RELEASE_HOLD_LUA,
    TRANSITION_HOLD_LUA,
)
from app.services.recovery_service import is_recovery_complete
from app.core.config import settings
from app.core.logging import logger

HOLD_DURATION_SECONDS = 120
MAX_SEATS_PER_HOLD = 6


def validate_group_adjacency(seats: List[Seat]) -> None:
    """
    Validates seat limit per transaction (up to 6 seats).
    """
    if len(seats) > MAX_SEATS_PER_HOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EXCEEDS_GROUP_LIMIT",
                "message": f"Cannot hold more than {MAX_SEATS_PER_HOLD} seats in a single request.",
            },
        )
    return


class HoldService:
    @staticmethod
    async def create_hold(
        db: AsyncSession,
        event_id: int,
        seat_ids: List[int],
        session_id: str,
        idempotency_key: Optional[str] = None,
        admission_token: Optional[str] = None,
    ) -> HoldResponse:
        """
        Atomically claims 1 to 6 seats using Redis Lua scripts.
        Guarantees zero double-booking under extreme concurrent requests.
        All-or-nothing: if any seat is unavailable, the entire request is rejected.

        SECURITY NOTE (Phase 2 Development Limitation):
        X-Session-ID is supplied by the client as a plain HTTP header containing a
        UUID generated and stored in browser localStorage.  It is used only for
        hold-ownership enforcement within the session's lifetime (Lua FORBIDDEN check).
        Client-supplied X-Session-ID alone does NOT constitute secure authentication.
        In production, session identity must be established via server-issued,
        cryptographically signed tokens (e.g. JWT or opaque session tokens).

        ADMISSION TOKEN (Phase 5 Pending):
        The admission_token parameter is accepted but not cryptographically validated
        yet.  Phase 5 will add:
          • Token issuance (server-signed JWT, bound to event_id + user identity).
          • Signature and expiry validation before hold creation.
          • Replay and reuse protection (single-use marker in Redis).
          • Checkout retry exclusion: idempotency-key collision on payment retry MUST
            NOT trigger TOKEN_ALREADY_USED for the same hold_id.
        Until Phase 5 is implemented, admission_token is logged at DEBUG level only
        and is never written to logs at INFO/WARNING/ERROR to avoid token leakage.

        EXPIRY LIFECYCLE:
        Hold TTL is 120 seconds.  After logical expiry the background reaper sweeps
        hold_expiry_zset on each interval (default 5 s).  Maximum elapsed time before
        release: TTL (120 s) + reaper interval (up to 5 s) = up to 125 seconds under
        normal event-loop load.  Actual release time under production load must be
        measured with real Redis integration / load testing.
        """
        # 0. Fail-closed: refuse hold creation if recovery is incomplete or Redis is unavailable
        if not is_recovery_complete():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "RECOVERY_INCOMPLETE",
                    "message": "Redis state recovery is incomplete. Booking traffic cannot be served.",
                },
                headers={"Retry-After": "2"},
            )

        try:
            redis = await get_redis()
            if redis is None:
                raise ValueError("Redis client unavailable")
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"Cannot acquire Redis client: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "REDIS_UNAVAILABLE",
                    "message": "Redis is currently unavailable. Please retry shortly.",
                },
                headers={"Retry-After": "5"},
            )

        # 1. Check recovery gate: reject while state reconstruction is active
        try:
            recovery_active = await redis.get("redis_recovery_in_progress")
            if recovery_active:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "RECOVERY_IN_PROGRESS",
                        "message": "Redis state recovery is in progress. Please retry shortly.",
                    },
                    headers={"Retry-After": "1"},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"Redis connection error when checking recovery gate: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "REDIS_UNAVAILABLE",
                    "message": "Redis is currently unavailable. Please retry shortly.",
                },
                headers={"Retry-After": "5"},
            )

        # 2. Check Idempotency Key cache if provided
        if idempotency_key:
            try:
                cached_hold = await redis.get(f"hold_idem:{idempotency_key}")
                if cached_hold:
                    cached_data = json.loads(cached_hold)
                    # Calculate remaining time
                    now_ts = int(time.time())
                    exp_ts = cached_data.get("expires_at_ts", now_ts + 120)
                    rem = max(0, exp_ts - now_ts)
                    cached_data["time_remaining_seconds"] = rem
                    return HoldResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Idempotency cache lookup failed: {e}")

        # 3. Validate Admission Token (Phase 5 Virtual Waiting Room)
        if admission_token or settings.ENFORCE_ADMISSION_TOKEN:
            from app.services.queue_service import QueueService
            if not admission_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "ADMISSION_TOKEN_REQUIRED",
                        "message": "A valid admission token is required to hold seats.",
                    },
                )
            is_valid, err_code, err_msg = await QueueService.validate_admission_token(
                token=admission_token,
                event_id=event_id,
                session_id=session_id,
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": err_code,
                        "message": err_msg,
                    },
                )

        # 4. Fetch seat records from database and validate existence
        stmt = select(Seat).where(Seat.event_id == event_id, Seat.id.in_(seat_ids))
        res = await db.execute(stmt)
        seats = list(res.scalars().all())

        if len(seats) != len(seat_ids):
            found_ids = {s.id for s in seats}
            missing = [sid for sid in seat_ids if sid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SEAT_NOT_FOUND",
                    "message": f"Requested seat IDs not found for event {event_id}: {missing}",
                },
            )

        # 4. Validate group adjacency
        validate_group_adjacency(seats)

        # 5. Execute atomic Lua claim script
        hold_id = f"hld_{uuid.uuid4().hex[:12]}"
        seat_statuses_key = f"event:{event_id}:seat_statuses"
        expiry_zset_key = "hold_expiry_zset"
        counter_key = "holds:active:count"
        hold_meta_key = f"hold:{hold_id}"

        seat_ids_csv = ",".join(str(sid) for sid in seat_ids)
        seat_id_args = [str(sid) for sid in seat_ids]

        try:
            lua_result = await redis.eval(
                CLAIM_HOLD_LUA,
                4,
                seat_statuses_key,
                expiry_zset_key,
                counter_key,
                hold_meta_key,
                hold_id,
                str(event_id),
                session_id,
                str(HOLD_DURATION_SECONDS),
                seat_ids_csv,
                *seat_id_args,
            )
        except Exception as exc:
            logger.error(f"Redis Lua script execution failed: {exc}")
            err_msg = str(exc).lower()
            if "timeout" in err_msg or "connection" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"code": "REDIS_UNAVAILABLE", "message": "Redis is currently unavailable. Please retry shortly."},
                    headers={"Retry-After": "5"},
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "REDIS_ERROR", "message": "Could not complete seat hold operation."},
            )

        # Evaluate Lua script outcome
        status_code = lua_result[0]
        if status_code == "CONFLICT":
            conflicting_seat = int(lua_result[1])
            conflict_state = lua_result[2] if len(lua_result) > 2 else "HELD"
            logger.info(f"Hold conflict: Seat {conflicting_seat} is currently {conflict_state}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SEATS_UNAVAILABLE",
                    "message": "One or more requested seats are no longer available.",
                    "details": {"conflicting_seats": [conflicting_seat], "state": conflict_state},
                },
            )

        if status_code != "OK":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "HOLD_FAILED", "message": "Hold operation could not be confirmed."},
            )

        expires_at_sec = int(lua_result[1])
        now_sec = int(lua_result[2])
        time_remaining = max(0, expires_at_sec - now_sec)

        held_at_iso = datetime.fromtimestamp(now_sec, tz=timezone.utc).isoformat()
        expires_at_iso = datetime.fromtimestamp(expires_at_sec, tz=timezone.utc).isoformat()

        response = HoldResponse(
            hold_id=hold_id,
            event_id=event_id,
            seat_ids=seat_ids,
            held_at=held_at_iso,
            expires_at=expires_at_iso,
            time_remaining_seconds=time_remaining,
            status="HELD",
        )

        # 6. Cache response for idempotency
        if idempotency_key:
            try:
                cache_payload = response.model_dump()
                cache_payload["expires_at_ts"] = expires_at_sec
                await redis.set(
                    f"hold_idem:{idempotency_key}",
                    json.dumps(cache_payload),
                    ex=HOLD_DURATION_SECONDS,
                )
            except Exception as e:
                logger.warning(f"Failed to cache hold idempotency key: {e}")

        logger.info(f"Successfully claimed hold {hold_id} for seats {seat_ids}")

        # 7. Broadcast seat hold update via WebSockets
        try:
            from app.services.websocket_service import ws_manager
            updates = [{"seat_id": sid, "status": "HELD", "hold_id": hold_id} for sid in seat_ids]
            await ws_manager.publish_seat_status_change(event_id, updates)
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast hold to WebSockets: {ws_err}")

        # 8. Mark admission token as consumed for this hold
        if admission_token:
            try:
                from app.services.queue_service import QueueService
                await QueueService.bind_token_to_hold(admission_token, hold_id)
            except Exception as e:
                logger.debug(f"Could not bind admission token: {e}")

        return response

    @staticmethod
    async def release_hold(
        event_id: int,
        hold_id: str,
        session_id: str,
    ) -> HoldReleaseResponse:
        """
        Manually releases an active HELD hold.
        Protected: will never release a PAYING hold.
        """
        redis = await get_redis()
        hold_meta_key = f"hold:{hold_id}"
        seat_statuses_key = f"event:{event_id}:seat_statuses"
        expiry_zset_key = "hold_expiry_zset"
        counter_key = "holds:active:count"

        try:
            lua_result = await redis.eval(
                RELEASE_HOLD_LUA,
                4,
                hold_meta_key,
                seat_statuses_key,
                expiry_zset_key,
                counter_key,
                hold_id,
                session_id,
            )
        except Exception as exc:
            logger.error(f"Release hold Lua error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "REDIS_ERROR", "message": "Failed to release hold."},
            )

        outcome = lua_result[0]
        if outcome == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Hold {hold_id} not found or already expired."},
            )
        elif outcome == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You do not own this hold."},
            )
        elif outcome == "PROTECTED_PAYING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "HOLD_IN_PAYMENT",
                    "message": "Hold cannot be released because payment is currently in-flight.",
                },
            )

        released_count = int(lua_result[1]) if len(lua_result) > 1 else 0
        released_seats_csv = lua_result[2] if len(lua_result) > 2 else ""

        # Broadcast seat release to WebSocket subscribers
        if released_seats_csv:
            try:
                from app.services.websocket_service import ws_manager
                released_ids = [int(s) for s in released_seats_csv.split(",") if s]
                updates = [{"seat_id": sid, "status": "AVAILABLE", "hold_id": None} for sid in released_ids]
                await ws_manager.publish_seat_status_change(event_id, updates)
            except Exception as ws_err:
                logger.warning(f"Failed to broadcast release to WebSockets: {ws_err}")

        logger.info(f"Released hold {hold_id} ({released_count} seats)")

        # Release admission slot and promote next waiting user in queue
        try:
            from app.services.queue_service import QueueService
            await QueueService.release_admission_slot(event_id, session_id)
        except Exception as q_err:
            logger.debug(f"Failed to release queue slot on hold release: {q_err}")

        return HoldReleaseResponse(
            hold_id=hold_id,
            message="Hold released successfully.",
            released_seats_count=released_count,
        )

    @staticmethod
    async def get_hold_details(
        event_id: int,
        hold_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves raw hold metadata from Redis."""
        redis = await get_redis()
        raw = await redis.hgetall(f"hold:{hold_id}")
        if not raw:
            return None

        now = int(time.time())
        expires_at = int(raw.get("expires_at", 0))
        rem = max(0, expires_at - now)

        seat_ids_raw = raw.get("seat_ids", "")
        seat_ids = [int(s) for s in seat_ids_raw.split(",") if s]

        return {
            "hold_id": raw.get("hold_id"),
            "event_id": int(raw.get("event_id", event_id)),
            "session_id": raw.get("session_id"),
            "seat_ids": seat_ids,
            "status": raw.get("status"),
            "held_at": datetime.fromtimestamp(int(raw.get("held_at", now)), tz=timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "time_remaining_seconds": rem,
        }
