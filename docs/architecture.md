# SeatSurge Architecture Documentation

## 1. System Overview

SeatSurge is a distributed, high-throughput flash-sale ticketing platform engineered for zero double bookings, strict fair queuing, sub-200ms seat map latency at 500 RPS, and resilient disaster recovery.

```
                   +-----------------------+
                   |  Clients / Web Browsers |
                   +-----------------------+
                              |
                              v
                   +-----------------------+
                   |    NGINX Load Balancer | (Port 8000)
                   |  - Overwrites IP headers
                   |  - WebSockets & Reverse Proxy
                   +-----------------------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
    +-------------------+           +-------------------+
    | FastAPI Replica 1 |           | FastAPI Replica 2 |
    |    (backend-1)    |           |    (backend-2)    |
    +-------------------+           +-------------------+
              |          \         /          |
              |           \       /           |
              v            v     v            v
     +------------------------------------------------+
     |                    Redis 7                     |
     |  - AOF Persistence (Named Volume)              |
     |  - Atomic Lua Hold Engine (All-or-Nothing)      |
     |  - FIFO Sorted-Set Waiting Room                |
     |  - Ephemeral Pub/Sub Fan-Out with Sequence Nums |
     +------------------------------------------------+
                              ^
                              |
     +------------------------------------------------+
     |                 PostgreSQL 16                  |
     |  - Durable Source of Truth                     |
     |  - Confirmed Sales with UNIQUE(event_id, seat) |
     |  - Persistent Payment State Machine            |
     |  - Advisory Lock Startup Safe Seeding          |
     +------------------------------------------------+
```

---

## 2. Component Responsibilities

### 2.1. PostgreSQL (Durable Source of Truth)
- Permanent ledger of confirmed ticket sales (`bookings`, `sold_seats`).
- Unbreakable defense: Database-level `UNIQUE(event_id, seat_id)` prevents double selling even under extreme edge-case failover.
- Persistent state machine for payment processing (`PROCESSING`, `SUCCEEDED`, `DECLINED`, `VOIDED`).
- Concurrency-safe initialization via PostgreSQL advisory locks.

### 2.2. Redis (Real-Time Coordination & Fast Path)
- Atomic temporary seat holds via custom Lua scripts.
- FIFO Virtual Waiting Room implemented via Sorted Sets (`ZADD`, `ZRANGEBYSCORE`).
- Ephemeral real-time broadcast via Redis Pub/Sub with monotonically increasing sequence numbers.
- Rate limiting and sliding window token buckets.
- Redis AOF (`appendonly yes`, `appendfsync everysec`) guarantees durability across unexpected restarts.

### 2.3. NGINX Reverse Proxy
- Front door for all client traffic.
- Overwrites and sanitizes `X-Forwarded-For` with `$remote_addr` to prevent IP spoofing attacks.
- Load balances HTTP and WebSockets connections across multiple backend replicas (`backend1`, `backend2`).

---

## 3. Atomic Seat Booking & Adjacency
- **No Python check-then-act:** Python never queries Redis and then issues a separate write.
- **Single Lua Execution:** A single atomic Lua script validates that all requested seats (up to 6) are currently `AVAILABLE`, checks row adjacency, and transitions them to `HELD` with an expiration TTL (120 seconds). If any single seat fails, the entire transaction aborts atomically.

---

## 4. Hold Lifecycle State Machine
```
AVAILABLE ---> (Hold created via Lua) ---> HELD (120s TTL)
                                             |
                  +--------------------------+--------------------------+
                  |                                                     |
           (TTL expires)                                        (Checkout initiated)
                  |                                                     |
                  v                                                     v
          [Expiry Reaper]                                             PAYING (Lease heartbeat)
                  |                                                     |
                  v                                          +----------+----------+
              AVAILABLE                                      |                     |
                                                        (Success)              (Failure)
                                                             v                     v
                                                           SOLD                 RELEASED
                                                  (PostgreSQL Committed)           |
                                                                                   v
                                                                               AVAILABLE
```

---

## 5. High-Availability & Disaster Recovery
- **Redis Recovery Gate:** Upon Redis restart or loss, a designated backend replica acquires an exclusive recovery lock with an owner token (renewed via Lua). It repopulates Redis seat state from PostgreSQL (`SOLD` and `PAYING` states) before opening the gate for new hold requests.
- **Multi-Instance Resilience:** If one FastAPI replica fails, NGINX instantly routes traffic to the remaining healthy instance with zero data loss or state divergence.
