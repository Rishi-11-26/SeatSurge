import hmac
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any
from app.redis.client import get_redis
from app.core.config import settings
from app.core.logging import logger
from app.schemas.queue import QueueResponse, QueueLeaveResponse


class QueueService:
    @staticmethod
    def generate_signed_token(session_id: str, event_id: int, expires_at: int) -> str:
        """
        Generates a cryptographically signed, event- and session-bound admission token.
        Format: adm_{session_id}_{event_id}_{expires_at}_{signature}
        """
        payload = f"{session_id}:{event_id}:{expires_at}"
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:24]
        return f"adm_{session_id}_{event_id}_{expires_at}_{signature}"

    @classmethod
    async def validate_admission_token(
        cls,
        token: str,
        event_id: int,
        session_id: str,
    ) -> Tuple[bool, str, str]:
        """
        Cryptographically validates an admission token.
        Checks:
        1. Token prefix and structural formatting.
        2. HMAC-SHA256 signature validity.
        3. Event binding (token.event_id == event_id).
        4. Session binding (token.session_id == session_id).
        5. Expiration (token.expires_at >= current_time).
        6. Replay / Single-use check in Redis (must not be bound to another hold).

        Returns: (is_valid: bool, error_code: str, error_message: str)
        """
        if not token or not token.startswith("adm_"):
            return False, "INVALID_ADMISSION_TOKEN", "Malformed or missing admission token."

        rem = token[4:]
        try:
            tok_session, tok_event_str, tok_exp_str, tok_sig = rem.rsplit("_", 3)
            tok_event = int(tok_event_str)
            tok_exp = int(tok_exp_str)
        except (ValueError, AttributeError):
            return False, "INVALID_ADMISSION_TOKEN", "Invalid admission token structure."

        # Verify cryptographic signature
        expected_payload = f"{tok_session}:{tok_event}:{tok_exp}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            expected_payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:24]

        if not hmac.compare_digest(tok_sig, expected_sig):
            return False, "INVALID_ADMISSION_TOKEN", "Admission token cryptographic signature is invalid."

        # Verify event binding
        if tok_event != event_id:
            return False, "INVALID_ADMISSION_TOKEN", f"Token was issued for event {tok_event}, not {event_id}."

        # Verify session binding
        if tok_session != session_id:
            return False, "INVALID_ADMISSION_TOKEN", "Token session mismatch: token does not belong to this session."

        # Verify expiration
        now = int(time.time())
        if now > tok_exp:
            return False, "EXPIRED_ADMISSION_TOKEN", "Admission token has expired. Please re-enter the waiting room."

        # Check Redis token metadata if present
        try:
            redis = await get_redis()
            meta_raw = await redis.get(f"queue:token_meta:{token}")
            if meta_raw:
                meta = json.loads(meta_raw)
                used_for_hold = meta.get("used_for_hold")
                if used_for_hold is not None:
                    return False, "ADMISSION_TOKEN_ALREADY_USED", f"Admission token has already been consumed for hold {used_for_hold}."
        except Exception as exc:
            logger.debug(f"[QueueService] Token metadata check fallback: {exc}")

        return True, "OK", ""

    @classmethod
    async def bind_token_to_hold(cls, token: str, hold_id: str) -> None:
        """Marks an admission token as consumed by a specific hold (single-use enforcement)."""
        if not token:
            return
        try:
            redis = await get_redis()
            meta_key = f"queue:token_meta:{token}"
            raw = await redis.get(meta_key)
            if raw:
                meta = json.loads(raw)
                meta["used_for_hold"] = hold_id
                await redis.set(meta_key, json.dumps(meta), ex=settings.ADMISSION_TOKEN_TTL_SECONDS)
        except Exception as exc:
            logger.debug(f"[QueueService] Could not bind token to hold: {exc}")

    @classmethod
    async def enter_or_poll_queue(cls, event_id: int, session_id: str) -> QueueResponse:
        """
        Enters or polls the FIFO Virtual Waiting Room (docs/api-contract.md §5).
        - Idempotent: repeated calls for the same session return the current position or existing token.
        - Server-controlled FIFO ordering via Redis Sorted Set.
        - Immediately admits if active capacity is below limit.
        """
        redis = await get_redis()
        now = time.time()
        admitted_zset = f"queue:event:{event_id}:admitted"
        waiting_zset = f"queue:event:{event_id}:waiting"
        token_key = f"queue:token:{session_id}:{event_id}"

        # 1. Prune expired admitted sessions
        try:
            await redis.zremrangebyscore(admitted_zset, 0, now)
        except Exception:
            pass

        # 2. Check if this session already has an active admission token
        try:
            existing_token = await redis.get(token_key)
            if existing_token:
                # Check expiration
                score = await redis.zscore(admitted_zset, session_id)
                if score and score > now:
                    expires_iso = datetime.fromtimestamp(int(score), tz=timezone.utc).isoformat()
                    return QueueResponse(
                        status="ADMITTED",
                        queue_position=0,
                        estimated_wait_seconds=0,
                        admission_token=existing_token,
                        token_expires_at=expires_iso,
                        session_id=session_id,
                        event_id=event_id,
                    )
        except Exception as exc:
            logger.debug(f"[QueueService] Active token lookup: {exc}")

        # 3. Check current admitted count vs capacity
        capacity = settings.QUEUE_ADMISSION_CAPACITY
        try:
            current_admitted = await redis.zcard(admitted_zset) or 0
        except Exception:
            current_admitted = 0

        # Check if the user is already in waiting queue
        try:
            waiting_score = await redis.zscore(waiting_zset, session_id)
        except Exception:
            waiting_score = None

        # 4. If under capacity and either no queue or user is at front, admit immediately
        if current_admitted < capacity:
            # If there's an existing queue, only admit if this user is at the front (or queue is empty)
            admit_now = True
            if waiting_score is not None:
                rank = await redis.zrank(waiting_zset, session_id)
                if rank is not None and rank > 0:
                    admit_now = False  # Someone joined before this user

            if admit_now:
                # Remove from waiting queue
                try:
                    await redis.zrem(waiting_zset, session_id)
                except Exception:
                    pass

                expires_at_int = int(now) + settings.ADMISSION_TOKEN_TTL_SECONDS
                token = cls.generate_signed_token(session_id, event_id, expires_at_int)
                expires_iso = datetime.fromtimestamp(expires_at_int, tz=timezone.utc).isoformat()

                # Record admission in Redis
                try:
                    await redis.zadd(admitted_zset, {session_id: expires_at_int})
                    await redis.set(token_key, token, ex=settings.ADMISSION_TOKEN_TTL_SECONDS)
                    meta_payload = {
                        "session_id": session_id,
                        "event_id": event_id,
                        "expires_at": expires_at_int,
                        "used_for_hold": None,
                    }
                    await redis.set(
                        f"queue:token_meta:{token}",
                        json.dumps(meta_payload),
                        ex=settings.ADMISSION_TOKEN_TTL_SECONDS,
                    )
                except Exception as exc:
                    logger.warning(f"[QueueService] Failed to persist admission in Redis: {exc}")

                logger.info(f"[QueueService] Admitted session {session_id} to event {event_id}.")
                return QueueResponse(
                    status="ADMITTED",
                    queue_position=0,
                    estimated_wait_seconds=0,
                    admission_token=token,
                    token_expires_at=expires_iso,
                    session_id=session_id,
                    event_id=event_id,
                )

        # 5. Over capacity or behind other users -> enqueue in waiting sorted set
        if waiting_score is None:
            try:
                await redis.zadd(waiting_zset, {session_id: now})
            except Exception as exc:
                logger.warning(f"[QueueService] Error adding to waiting queue: {exc}")

        try:
            rank = await redis.zrank(waiting_zset, session_id)
            position = (rank + 1) if rank is not None else 1
        except Exception:
            position = 1

        estimated_wait = position * 2  # 2 seconds per position

        logger.debug(f"[QueueService] Session {session_id} queued at position {position} for event {event_id}.")
        return QueueResponse(
            status="WAITING",
            queue_position=position,
            estimated_wait_seconds=estimated_wait,
            admission_token=None,
            token_expires_at=None,
            session_id=session_id,
            event_id=event_id,
        )

    @classmethod
    async def leave_queue(cls, event_id: int, session_id: str) -> QueueLeaveResponse:
        """Removes a session from waiting or admitted state, releasing capacity."""
        redis = await get_redis()
        admitted_zset = f"queue:event:{event_id}:admitted"
        waiting_zset = f"queue:event:{event_id}:waiting"
        token_key = f"queue:token:{session_id}:{event_id}"

        try:
            await redis.zrem(waiting_zset, session_id)
            await redis.zrem(admitted_zset, session_id)
            await redis.delete(token_key)
        except Exception as exc:
            logger.warning(f"[QueueService] Error during leave_queue: {exc}")

        # Automatically promote the next user in line
        await cls.promote_next_waiting(event_id)

        logger.info(f"[QueueService] Session {session_id} left queue for event {event_id}.")
        return QueueLeaveResponse(
            status="LEFT",
            message="Successfully left the queue.",
            session_id=session_id,
            event_id=event_id,
        )

    @classmethod
    async def promote_next_waiting(cls, event_id: int) -> Optional[str]:
        """
        Promotes the next user in FIFO queue if capacity is available.
        Returns the admitted session_id or None.
        """
        redis = await get_redis()
        now = time.time()
        admitted_zset = f"queue:event:{event_id}:admitted"
        waiting_zset = f"queue:event:{event_id}:waiting"

        try:
            # Prune expired
            await redis.zremrangebyscore(admitted_zset, 0, now)
            current_admitted = await redis.zcard(admitted_zset) or 0

            if current_admitted < settings.QUEUE_ADMISSION_CAPACITY:
                # Pop next session in line
                next_items = await redis.zpopmin(waiting_zset, count=1)
                if next_items:
                    next_session_id = next_items[0][0] if isinstance(next_items[0], tuple) else next_items[0]
                    expires_at_int = int(now) + settings.ADMISSION_TOKEN_TTL_SECONDS
                    token = cls.generate_signed_token(next_session_id, event_id, expires_at_int)

                    await redis.zadd(admitted_zset, {next_session_id: expires_at_int})
                    await redis.set(
                        f"queue:token:{next_session_id}:{event_id}",
                        token,
                        ex=settings.ADMISSION_TOKEN_TTL_SECONDS,
                    )
                    meta_payload = {
                        "session_id": next_session_id,
                        "event_id": event_id,
                        "expires_at": expires_at_int,
                        "used_for_hold": None,
                    }
                    await redis.set(
                        f"queue:token_meta:{token}",
                        json.dumps(meta_payload),
                        ex=settings.ADMISSION_TOKEN_TTL_SECONDS,
                    )
                    logger.info(f"[QueueService] Promoted next waiting session {next_session_id} to ADMITTED.")
                    return next_session_id
        except Exception as exc:
            logger.debug(f"[QueueService] Error during promote_next_waiting: {exc}")

        return None
