import sys
import os
import asyncio
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure backend root is on Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.init_db import init_db

TEST_DB_FILE = Path(__file__).resolve().parent / "test_seatsurge.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes tables and seeds 5,040 seats into test database."""
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()

    asyncio.run(init_db(test_engine))
    yield
    # Teardown
    asyncio.run(test_engine.dispose())
    if TEST_DB_FILE.exists():
        try:
            TEST_DB_FILE.unlink()
        except Exception:
            pass


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session_factory():
    return TestingSessionLocal
