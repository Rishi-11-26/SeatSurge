import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.redis.client import init_redis_pool, close_redis
from app.db.session import engine
from app.db.init_db import init_db
from app.services.metrics_service import metrics_tracker
from app.services.reaper_service import hold_expiry_reaper
from app.services.recovery_service import RedisRecoveryService, mark_recovery_complete, mark_recovery_skipped
from app.services.websocket_service import ws_manager
from app.api.v1.endpoints.ws import websocket_events_endpoint, router as ws_router
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints.health import get_health
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.INSTANCE_ID}] in {settings.APP_ENV} mode")
    try:
        init_redis_pool()
        logger.info(f"Initialized Redis connection pool targeting {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    except Exception as exc:
        logger.warning(f"Could not eagerly initialize Redis pool: {exc}")

    # Database initialization, recovery & background services (production/staging)
    if settings.APP_ENV != "test":
        try:
            await asyncio.wait_for(init_db(engine), timeout=30.0)
            logger.info("Database initialization and seed verification complete.")
        except Exception as exc:
            logger.warning(f"Database initialization deferred (database may still be starting): {exc}")

        try:
            recovery_result = await asyncio.wait_for(
                RedisRecoveryService.reconstruct_state_from_postgres(engine), timeout=15.0
            )
            status_val = recovery_result.get("status") if recovery_result else "UNKNOWN"
            if status_val == "SUCCESS":
                logger.info(f"Redis recovery: SUCCESS — {recovery_result}")
            elif status_val == "COMPLETED_BY_PEER":
                logger.info("Redis recovery: completed by peer instance.")
            else:
                logger.warning(f"Redis recovery: {status_val}. Reconstructing state using in-memory coordinator...")
                from app.redis.client import set_redis_override
                import fakeredis.aioredis as fake_aioredis
                set_redis_override(fake_aioredis.FakeRedis(decode_responses=True))
                await RedisRecoveryService.reconstruct_state_from_postgres(engine)
                mark_recovery_complete()
                logger.info("State reconstructed successfully using in-memory coordinator.")
        except Exception as exc:
            logger.warning(f"External Redis recovery error ({exc}). Reconstructing state using in-memory coordinator...")
            try:
                from app.redis.client import set_redis_override
                import fakeredis.aioredis as fake_aioredis
                set_redis_override(fake_aioredis.FakeRedis(decode_responses=True))
                await RedisRecoveryService.reconstruct_state_from_postgres(engine)
                mark_recovery_complete()
                logger.info("State reconstructed successfully using in-memory coordinator.")
            except Exception as e2:
                mark_recovery_skipped()
                logger.error(f"In-memory recovery failed: {e2}")

        # Start background services
        hold_expiry_reaper.start()
        ws_manager.start_pubsub_listener()

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME} [{settings.INSTANCE_ID}]...")
    if settings.APP_ENV != "test":
        await hold_expiry_reaper.stop()
        await ws_manager.stop_pubsub_listener()
    await close_redis()
    await engine.dispose()
    logger.info("Database and Redis connections gracefully cleaned up.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="High-throughput distributed flash-sale ticketing platform for YUKTIK 2026.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register custom exception handlers for structured error envelope (docs/api-contract.md)
register_exception_handlers(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if "*" not in settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_instance_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000

    # Record metrics for latency tracking
    metrics_tracker.record_request(process_time)

    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    response.headers["X-Backend-Instance"] = settings.INSTANCE_ID
    return response


# Root and convenience health endpoints
@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "instance_id": settings.INSTANCE_ID,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "health": "/health",
        "metrics": f"{settings.API_V1_STR}/metrics",
    }


@app.get("/health", tags=["Health & Diagnostics"])
async def direct_health():
    """Direct root health endpoint for load balancers and orchestrators."""
    return await get_health()


# API V1 Router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Real-Time WebSocket endpoint at root path /ws/events (matching frontend VITE_WS_BASE_URL default)
app.add_api_websocket_route("/ws/events", websocket_events_endpoint)
