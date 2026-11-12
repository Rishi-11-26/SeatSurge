import time
import uuid
import pytest
from fastapi import FastAPI, Depends, Request
from starlette.testclient import TestClient
from app.core.rate_limit import (
    check_rate_limit,
    _in_memory_rate_cache,
    _record_in_memory_request,
    _MAX_IN_MEMORY_CLIENTS,
)
from app.core.exceptions import register_exception_handlers

# Dedicated mini-app to test rate limiting thresholds cleanly
rate_limit_app = FastAPI()
register_exception_handlers(rate_limit_app)


async def strict_rate_limit(request: Request):
    await check_rate_limit(request, limit=5, window_seconds=60)


@rate_limit_app.get("/test-limited", dependencies=[Depends(strict_rate_limit)])
async def limited_endpoint():
    return {"message": "success"}


def test_rate_limiting_enforcement():
    # Use a unique session ID per test run to avoid cross-run cache pollution.
    # Also clear any stale in-memory cache entries before starting.
    _in_memory_rate_cache.clear()

    unique_session = f"test-rate-{uuid.uuid4().hex}"
    client = TestClient(rate_limit_app)
    headers = {"X-Session-ID": unique_session}

    # First 5 requests within the limit must succeed
    for i in range(5):
        res = client.get("/test-limited", headers=headers)
        assert res.status_code == 200, (
            f"Request {i + 1}/5 expected 200, got {res.status_code}: {res.text}"
        )
        assert res.json()["message"] == "success"

    # 6th request exceeds the limit of 5 → must trigger 429
    res_blocked = client.get("/test-limited", headers=headers)
    assert res_blocked.status_code == 429, (
        f"6th request expected 429, got {res_blocked.status_code}: {res_blocked.text}"
    )
    # Check structured error envelope
    body = res_blocked.json()
    assert "error" in body
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit exceeded" in body["error"]["message"].lower()
    assert "Retry-After" in res_blocked.headers


def test_in_memory_fallback_memory_bounding():
    """
    CRITICAL RESOURCE SAFETY:
    In-memory fallback cache must be bounded (max 10,000 entries) with LRU eviction.
    Flooding unique sessions during Redis outage must not cause OOM.
    """
    _in_memory_rate_cache.clear()
    now = time.time()

    # Insert capacity + 50 distinct clients
    test_capacity = _MAX_IN_MEMORY_CLIENTS + 50
    for i in range(test_capacity):
        client_id = f"flooding-client-{i}"
        _record_in_memory_request(client_id, now, window_seconds=60, limit=100)

    # Size must not exceed max bound
    assert len(_in_memory_rate_cache) == _MAX_IN_MEMORY_CLIENTS

    # Oldest clients (0-49) must have been evicted (LRU)
    assert "flooding-client-0" not in _in_memory_rate_cache
    assert "flooding-client-49" not in _in_memory_rate_cache
    # Recent clients must still be present
    assert f"flooding-client-{test_capacity - 1}" in _in_memory_rate_cache
