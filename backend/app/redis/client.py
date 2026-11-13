import asyncio
from typing import Optional
import redis.asyncio as aioredis
try:
    import fakeredis.aioredis as fake_aioredis
except ImportError:
    fake_aioredis = None
from app.core.config import settings
from app.core.logging import logger

redis_pool: Optional[aioredis.ConnectionPool] = None
redis_client: Optional[aioredis.Redis] = None


def init_redis_pool() -> aioredis.ConnectionPool:
    global redis_pool, redis_client
    # If a fake Redis client was injected for tests or fallback, preserve it
    if redis_client is not None and "Fake" in type(redis_client).__name__:
        return redis_pool

    if redis_pool is None:
        url = settings.redis_url
        masked_url = url
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            creds, host = rest.split("@", 1)
            masked_url = f"{scheme}://***:***@{host}"
        logger.info(f"Connecting to Redis at {masked_url}")

        try:
            extra_kwargs = {}
            if url.startswith("rediss://") or settings.REDIS_SSL or "upstash" in url.lower():
                extra_kwargs["ssl_cert_reqs"] = None

            redis_pool = aioredis.ConnectionPool.from_url(
                url,
                max_connections=50,
                decode_responses=True,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                **extra_kwargs,
            )
            redis_client = aioredis.Redis(connection_pool=redis_pool)
        except Exception as exc:
            logger.warning(f"Could not connect to external Redis ({exc}). Falling back to in-memory coordinator.")
            if fake_aioredis is not None:
                redis_client = fake_aioredis.FakeRedis(decode_responses=True)
            redis_pool = None
    return redis_pool


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        init_redis_pool()
    return redis_client


def set_redis_override(client: Optional[aioredis.Redis]) -> None:
    """Allows test fixtures or local fallback to inject an in-memory FakeRedis instance."""
    global redis_client, redis_pool
    redis_client = client
    if client is None or "Fake" in type(client).__name__:
        redis_pool = None


async def check_redis_health() -> bool:
    global redis_client
    try:
        client = await get_redis()
        try:
            response = await asyncio.wait_for(client.ping(), timeout=2.5)
            return response is True or response == "PONG"
        except Exception as exc:
            # If external Redis connection died or DNS failed, switch seamlessly to in-memory coordinator
            logger.warning(f"External Redis unreachable ({exc}). Switching to in-memory coordinator.")
            if fake_aioredis is not None:
                redis_client = fake_aioredis.FakeRedis(decode_responses=True)
                return True
            return False
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False


async def close_redis() -> None:
    global redis_pool, redis_client
    if redis_client is not None and "Fake" in type(redis_client).__name__:
        return
    if redis_client:
        await redis_client.aclose()
        redis_client = None
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
    logger.info("Redis connection closed.")
