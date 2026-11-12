# Architecture Decision Records (ADRs)

## ADR 001: Technology Stack Selection
- **Status:** Accepted
- **Context:** SeatSurge requires low latency (<200ms p95 at 500 RPS), strict zero double bookings, real-time WebSocket updates, and resilience under high load.
- **Decision:** Use Python 3.10+ with FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), PostgreSQL 16, Redis 7 (with AOF persistence), NGINX, and Docker Compose.
- **Consequences:** Provides native async I/O throughout the stack, high throughput, and zero external SaaS dependencies. Celery and Kafka were explicitly avoided to minimize complexity and resource overhead.

---

## ADR 002: Dual-Store Responsibility Model
- **Status:** Accepted
- **Context:** High concurrency flash-sales can overwhelm standard relational databases if raw temporary holds are written to disk on every click. Conversely, in-memory stores can lose state on crash.
- **Decision:** 
  1. PostgreSQL is the durable source of truth for confirmed bookings and transactions, enforced with a `UNIQUE(event_id, seat_id)` constraint.
  2. Redis coordinates temporary holds (120s TTL), the FIFO waiting room, rate limiting, and real-time Pub/Sub fan-out.
- **Consequences:** Eliminates database lock contention on seat clicks while guaranteeing zero duplicate confirmed sales.

---

## ADR 003: Atomic Holds via Redis Lua Scripting
- **Status:** Accepted
- **Context:** Multi-seat group reservations (up to 6 seats) must be atomic and adjacent. Python check-then-write sequences introduce race conditions under concurrency.
- **Decision:** Execute atomic Lua scripts inside Redis for seat availability checks, adjacency validation, and state transitions. Redis server time (`redis.call('TIME')`) is used for deterministic expiration timestamps.
- **Consequences:** Guarantees all-or-nothing group holds with zero race conditions between concurrent worker instances.

---

## ADR 004: Client IP Sanitization in NGINX
- **Status:** Accepted
- **Context:** Waiting room fairness, bot detection, and rate limiting rely on client IP addresses. Untrusted clients can spoof `X-Forwarded-For` headers.
- **Decision:** Configure NGINX to explicitly overwrite `X-Forwarded-For` with `$remote_addr`. The backend application only trusts client IP headers originating from configured private subnet ranges.
- **Consequences:** Prevents IP spoofing attacks and ensures accurate bot scoring and rate limiting.

---

## ADR 005: Multi-Instance Containerization & Persistence
- **Status:** Accepted
- **Context:** The system must survive the crash of an application instance or restart of data stores without catastrophic data loss.
- **Decision:** Run at least two FastAPI replicas (`backend1`, `backend2`) behind an NGINX load balancer. Use named Docker volumes (`postgres_data`, `redis_data`) and enable Redis AOF (`appendfsync everysec`).
- **Consequences:** Zero single point of failure at the application tier. Durable recovery of data upon container restarts.
