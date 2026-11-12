import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.redis.client import init_redis_pool, close_redis
from app.db.session import engine
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints.health import get_health


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

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME} [{settings.INSTANCE_ID}]...")
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
    }


@app.get("/health", tags=["Health & Diagnostics"])
async def direct_health():
    """Direct root health endpoint for load balancers and orchestrators."""
    return await get_health()


# API V1 Router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
