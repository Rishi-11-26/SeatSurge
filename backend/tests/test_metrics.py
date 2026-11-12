import pytest
from app.services.metrics_service import MetricsTracker


def test_metrics_tracker_cold_start():
    """
    CRITICAL OBSERVABILITY REQUIREMENT:
    Cold start must return honest 0.0 values, never fabricated or falsely optimistic 1.0.
    """
    tracker = MetricsTracker()
    snapshot = tracker.get_metrics_snapshot()

    # Latencies must be 0.0 when no observations exist
    assert snapshot["latency_p50_ms"] == 0.0
    assert snapshot["latency_p95_ms"] == 0.0
    assert snapshot["latency_p99_ms"] == 0.0
    assert snapshot["total_requests"] == 0
    assert snapshot["requests_per_second"] == 0.0

    # Cache hit ratio must be 0.0 on cold start (0 hits, 0 misses), not 1.0
    assert snapshot["cache_hit_ratio"] == 0.0
    assert snapshot["bots_blocked_count"] == 0


def test_metrics_endpoint(client):
    """Verifies that /metrics endpoint returns valid, real process-local metrics."""
    # Make a few requests to populate metrics
    client.get("/api/v1/events")
    client.get("/api/v1/events/1")

    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "instance_id" in data
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert data["total_requests"] >= 2
    assert "requests_per_second" in data
    assert "latency_p50_ms" in data
    assert "latency_p95_ms" in data
    assert "cache_hit_ratio" in data
    assert "active_holds_count" in data
    assert "sold_seats_count" in data
    assert "bots_blocked_count" in data
