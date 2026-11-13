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

from app.core.config import settings
settings.APP_ENV = "test"

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.init_db import init_db
from app.redis.client import set_redis_override
from app.services.recovery_service import mark_recovery_complete, reset_recovery_state

try:
    import fakeredis.aioredis as fake_aioredis
    import fakeredis as _fakeredis_sync
except ImportError:
    fake_aioredis = None
    _fakeredis_sync = None

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


@pytest.fixture(autouse=True)
def setup_fake_redis():
    """
    Injects in-memory FakeRedis into app.redis for fast, reliable Lua execution in tests.

    Uses a shared FakeServer so that the async client (injected into the app) and the
    synchronous client (accessible via ``sync_fake_redis`` fixture) share the same keyspace.
    Existing tests that do ``await setup_fake_redis.get(...)`` continue to work because this
    fixture yields the **async** FakeRedis client.

    Also marks recovery complete so the fail-closed readiness gate does not block holds
    during the test suite.
    """
    if fake_aioredis is not None and _fakeredis_sync is not None:
        server = _fakeredis_sync.FakeServer()
        async_client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
        sync_client = _fakeredis_sync.FakeRedis(server=server, decode_responses=True)
        # Stash sync handle so sync_fake_redis fixture can retrieve it
        async_client._sync_handle = sync_client
        set_redis_override(async_client)
        mark_recovery_complete()   # test mode: bypass real recovery
        yield async_client         # backward-compatible: existing tests await this
        set_redis_override(None)
        reset_recovery_state()     # restore flags between tests
    else:
        yield None


@pytest.fixture
def sync_fake_redis(setup_fake_redis):
    """
    Returns the synchronous FakeRedis handle that shares the same FakeServer as
    setup_fake_redis.  Use in tests that need synchronous Redis state manipulation
    (e.g. injecting a gate key) without asyncio.run().
    """
    if setup_fake_redis is not None and hasattr(setup_fake_redis, "_sync_handle"):
        return setup_fake_redis._sync_handle
    return None
