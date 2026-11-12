import asyncio
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import logger

redis_pool: Optional[aioredis.ConnectionPool] = None
redis_client: Optional[aioredis.Redis] = None


def init_redis_pool() -> aioredis.ConnectionPool:
    global redis_pool, redis_client
    if redis_pool is None:
        redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        redis_client = aioredis.Redis(connection_pool=redis_pool)
    return redis_pool


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        init_redis_pool()
    return redis_client


async def check_redis_health() -> bool:
    try:
        client = await get_redis()
        response = await asyncio.wait_for(client.ping(), timeout=1.5)
        return response is True or response == "PONG"
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False


async def close_redis() -> None:
    global redis_pool, redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
    logger.info("Redis connection closed.")
