import time
from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from app.core.config import settings
from app.schemas.health import HealthResponse, ReadinessResponse, ServiceStatus
from app.db.session import check_db_health
from app.redis.client import check_redis_health
from app.services.recovery_service import is_recovery_complete

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Authoritative health check for SeatSurge backend instance."""
    start_time = time.perf_counter()
    db_ok = await check_db_health()
    db_latency = (time.perf_counter() - start_time) * 1000

    start_time = time.perf_counter()
    redis_ok = await check_redis_health()
    redis_latency = (time.perf_counter() - start_time) * 1000

    services = {
        "database": ServiceStatus(
            status="healthy" if db_ok else "unreachable",
            latency_ms=round(db_latency, 2) if db_ok else None,
        ),
        "redis": ServiceStatus(
            status="healthy" if redis_ok else "unreachable",
            latency_ms=round(redis_latency, 2) if redis_ok else None,
        ),
    }

    if db_ok and redis_ok:
        overall_status = "ok"
    elif db_ok or redis_ok:
        overall_status = "degraded"
    else:
        overall_status = "down"

    return HealthResponse(
        status=overall_status,
        instance_id=settings.INSTANCE_ID,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
    )


@router.get("/health/liveness")
async def get_liveness():
    """Kubernetes/Container liveness probe verifying HTTP server responsiveness."""
    return {
        "status": "alive",
        "instance_id": settings.INSTANCE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/readiness", response_model=ReadinessResponse)
async def get_readiness(response: Response):
    """
    Readiness probe — FAIL-CLOSED.

    Returns 200 only when ALL three conditions are met:
      1. Database is reachable.
      2. Redis is reachable.
      3. Redis state recovery has successfully completed this process lifetime.

    If recovery returned SKIPPED (Redis was unavailable at startup) or has not
    finished yet, this endpoint returns 503 so that the load balancer does NOT
    route booking traffic to this instance.
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    recovery_ok = is_recovery_complete()
    is_ready = db_ok and redis_ok and recovery_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        ready=is_ready,
        instance_id=settings.INSTANCE_ID,
        database=db_ok,
        redis=redis_ok,
        recovery_complete=recovery_ok,
    )
