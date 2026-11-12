import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"timeout": 2},
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health() -> bool:
    try:
        async def _ping():
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1

        return await asyncio.wait_for(_ping(), timeout=1.5)
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return False
