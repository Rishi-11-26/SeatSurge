"""
SeatSurge Local Development & Evaluation Server
================================================
Runs the full SeatSurge application locally without requiring Docker,
external PostgreSQL, or external Redis.
Uses:
- SQLite (asyncpg compatible via aiosqlite): ./seatsurge_local.db
- In-memory Redis (fakeredis with async Lua script support)
"""

import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Configure local standalone environment
db_path = backend_dir / "seatsurge_local.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
os.environ["APP_ENV"] = "development"
os.environ["PORT"] = "8000"

import asyncio
import fakeredis.aioredis as fake_aioredis
import uvicorn
from app.core.config import settings
from app.redis.client import set_redis_override
from app.db.session import engine
from app.db.init_db import init_db
from app.services.recovery_service import RedisRecoveryService, mark_recovery_complete
from app.main import app


async def prepare_local_environment():
    print("=" * 65)
    print("SEATSURGE LOCAL EVALUATION ENVIRONMENT")
    print("=" * 65)
    print(f"[*] Database: SQLite ({db_path})")
    
    # 1. Initialize in-memory FakeRedis
    print("[*] Initializing in-memory Redis coordinator...")
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)
    set_redis_override(fake_redis)

    # 2. Initialize Database & Seed 5,040 Seats
    print("[*] Checking database tables and seat seed data...")
    await init_db(engine)

    # 3. Reconstruct Redis State from DB
    print("[*] Reconstructing seat availability state in Redis...")
    await RedisRecoveryService.reconstruct_state_from_postgres(engine)
    mark_recovery_complete()

    print("[+] SeatSurge local backend is 100% READY!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(prepare_local_environment())
    print("\nStarting Uvicorn API server on http://127.0.0.1:8000 ...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
