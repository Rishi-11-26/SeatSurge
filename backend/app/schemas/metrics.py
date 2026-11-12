from typing import Optional
from pydantic import BaseModel, Field


class MetricsResponse(BaseModel):
    """
    Per-instance monitoring snapshot.

    IMPORTANT: All values are LOCAL to the responding backend instance.
    With two instances behind NGINX, each instance reports its own counters.
    The `instance_id` field identifies which process responded.
    Phase 8 will aggregate across instances.
    """

    timestamp: str
    instance_id: str = Field(..., description="Backend replica that served this response")
    uptime_seconds: float
    total_requests: int
    requests_per_second: float = Field(..., description="10-second rolling RPS (this instance only)")
    latency_p50_ms: float = Field(..., description="p50 response latency in ms (last 1,000 requests)")
    latency_p95_ms: float = Field(..., description="p95 response latency in ms (last 1,000 requests)")
    latency_p99_ms: float = Field(..., description="p99 response latency in ms (last 1,000 requests)")
    cache_hit_ratio: float = Field(
        ...,
        description="Redis cache hit ratio (0.0–1.0). Reports 0.0 when no cache ops recorded yet.",
    )
    active_holds_count: Optional[int] = Field(
        default=None,
        description=(
            "Active temporary holds sourced from Redis counter key 'holds:active:count'. "
            "null means Redis is unavailable or the counter has not been initialised yet "
            "(Phase 2 Lua scripts maintain it). "
            "0 means Redis is reachable but no holds are currently recorded."
        ),
    )
    sold_seats_count: int = Field(
        default=0,
        description="Total CONFIRMED bookings in PostgreSQL (authoritative, durable count)",
    )
    bots_blocked_count: int = Field(
        default=0,
        description="Requests rejected by bot detection (Phase 7). Always 0 in Phase 1.",
    )
