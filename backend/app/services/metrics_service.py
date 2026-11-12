import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
from app.core.config import settings

START_TIME = time.time()


class MetricsTracker:
    def __init__(self, max_history: int = 1000):
        self.total_requests: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.bots_blocked: int = 0
        self._latencies: deque = deque(maxlen=max_history)
        self._request_timestamps: deque = deque(maxlen=5000)

    def record_request(self, latency_ms: float) -> None:
        self.total_requests += 1
        now = time.time()
        self._latencies.append(latency_ms)
        self._request_timestamps.append(now)

    def record_cache(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_bot_blocked(self) -> None:
        self.bots_blocked += 1

    def get_metrics_snapshot(
        self,
        active_holds: Optional[int] = None,
        sold_seats: int = 0,
    ) -> Dict[str, Any]:
        now = time.time()
        uptime = round(now - START_TIME, 2)

        # 10-second rolling RPS calculation
        window_start = now - 10.0
        recent_requests = sum(1 for t in self._request_timestamps if t >= window_start)
        rps = round(recent_requests / 10.0, 2)

        # Percentile latencies
        if self._latencies:
            latencies_array = np.array(list(self._latencies))
            p50 = float(np.percentile(latencies_array, 50))
            p95 = float(np.percentile(latencies_array, 95))
            p99 = float(np.percentile(latencies_array, 99))
        else:
            p50 = p95 = p99 = 0.0

        # Cache hit ratio — 0.0 when no cache operations recorded yet (honest cold-start default)
        total_cache = self.cache_hits + self.cache_misses
        hit_ratio = round(self.cache_hits / total_cache, 4) if total_cache > 0 else 0.0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instance_id": settings.INSTANCE_ID,
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "requests_per_second": rps,
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "cache_hit_ratio": hit_ratio,
            "active_holds_count": active_holds,
            "sold_seats_count": sold_seats,
            "bots_blocked_count": self.bots_blocked,
        }


metrics_tracker = MetricsTracker()
