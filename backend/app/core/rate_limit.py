"""
Sliding-window rate limiter for SeatSurge.

Architecture & High-Availability Semantics:
1. Primary shared rate limiter: Redis Sorted Sets (ZSET).
   - Atomic MULTI/EXEC pipeline ensures zero race conditions across distributed instances.
   - Globally consistent rate limits across all FastAPI replicas behind NGINX.

2. Fallback degraded-mode rate limiter: In-memory sliding window.
   - Activated ONLY when Redis is unavailable or times out.
   - ARCHITECTURAL NOTE: The in-memory fallback is strictly process-local.
     Behind a multi-instance load balancer (e.g. 2 replicas), clients may effectively
     experience up to 2x the rate limit during an active Redis outage.
   - Memory is bounded to a maximum of 10,000 tracked client identifiers with
     LRU eviction to prevent unbounded memory growth / OOM during high-volume outages.
"""

import time
from collections import OrderedDict
from typing import Optional
from fastapi import Request, HTTPException, status
from app.core.config import settings
from app.core.logging import logger
from app.redis.client import get_redis

# Bounded in-memory fallback cache: client_id -> list of timestamps
# Using OrderedDict for LRU eviction of stale client keys
_MAX_IN_MEMORY_CLIENTS = 10000
_in_memory_rate_cache: OrderedDict[str, list[float]] = OrderedDict()
_MAX_WINDOW_SECONDS = 60
_DEFAULT_RATE_LIMIT = 120  # requests per minute per IP / Session


def get_client_identifier(request: Request) -> str:
    """Extracts client IP safely from sanitized proxy header or direct peer."""
    # NGINX overwrites X-Forwarded-For with true peer IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return f"session:{session_id}"
    return f"ip:{client_ip}"


def _record_in_memory_request(client_id: str, now: float, window_seconds: int, limit: int) -> bool:
    """
    Records request in process-local sliding window with bounded memory.
    Returns True if request is allowed, False if rate limit is exceeded.
    """
    global _in_memory_rate_cache

    # LRU management: move key to end if already present
    if client_id in _in_memory_rate_cache:
        timestamps = _in_memory_rate_cache.pop(client_id)
    else:
        # Evict oldest entry if at capacity
        if len(_in_memory_rate_cache) >= _MAX_IN_MEMORY_CLIENTS:
            _in_memory_rate_cache.popitem(last=False)
        timestamps = []

    cutoff = now - window_seconds
    # Retain timestamps within sliding window
    timestamps = [t for t in timestamps if t >= cutoff]
    timestamps.append(now)
    _in_memory_rate_cache[client_id] = timestamps

    return len(timestamps) <= limit


async def check_rate_limit(
    request: Request,
    limit: int = _DEFAULT_RATE_LIMIT,
    window_seconds: int = _MAX_WINDOW_SECONDS,
) -> None:
    """
    Enforces sliding window rate limit. Raises HTTP 429 when threshold exceeded.
    Tries Redis first (global across instances), falls back to bounded in-memory.
    """
    client_id = get_client_identifier(request)
    now = time.time()

    # 1. Primary: Redis atomic sliding window
    try:
        redis = await get_redis()
        redis_key = f"rate_limit:{client_id}"
        pipe = redis.pipeline()
        # Remove timestamps older than window
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        # Add current timestamp
        pipe.zadd(redis_key, {str(now): now})
        # Count requests in window
        pipe.zcard(redis_key)
        # Set expiration on the key
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()

        request_count = results[2]
        if request_count > limit:
            logger.warning(f"Rate limit exceeded (Redis) for {client_id}: {request_count}/{limit}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please throttle your requests.",
                headers={"Retry-After": str(window_seconds)},
            )
        return
    except HTTPException:
        raise
    except Exception:
        # Fall back gracefully to in-memory sliding window
        pass

    # 2. Fallback: Process-local bounded sliding window
    allowed = _record_in_memory_request(client_id, now, window_seconds, limit)
    if not allowed:
        logger.warning(f"In-memory rate limit exceeded for {client_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please throttle your requests.",
            headers={"Retry-After": str(window_seconds)},
        )
