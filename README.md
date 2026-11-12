# SeatSurge — Distributed Flash-Sale Ticketing Platform

SeatSurge is a distributed, high-throughput ticketing engine engineered for flash sales with extreme concurrency, designed for **YUKTIK 2026**.

## Core Capabilities
- **Capacity:** 5,040 seats in a tiered auditorium.
- **High Concurrency:** Sub-200ms p95 latency under 500 RPS load.
- **Zero Double Bookings:** Atomic Redis Lua hold engine + PostgreSQL unique constraints.
- **Fair Queuing:** Redis sorted-set FIFO virtual waiting room with stable session admission tokens.
- **Live Seat Map:** Sub-second real-time fan-out via WebSockets and Redis Pub/Sub with gap detection.
- **Two-Minute Holds:** Automatic 120s hold lifecycle with a 5-second background expiry reaper.
- **Fault Tolerance:** Dual FastAPI instances behind NGINX, Redis AOF persistence, and disaster recovery state reconstruction.

---

## Architecture Overview

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

## Directory Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Versioned REST APIs & health endpoints
│   │   ├── core/           # Config (pydantic-settings), logging
│   │   ├── db/             # SQLAlchemy async engine, sessionmaker
│   │   ├── models/         # Database models (bookings, seats, payments)
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Domain logic (hold reaper, payments)
│   │   ├── redis/          # Redis connection pool & Lua scripts
│   │   ├── websocket/      # Real-time WebSocket connection manager
│   │   ├── ml/             # Bot detection inference engine
│   │   └── main.py         # FastAPI application entrypoint
│   ├── tests/              # Pytest test suite
│   ├── Dockerfile          # Production multi-stage Docker build
│   └── requirements.txt    # Python dependencies
├── nginx/
│   └── nginx.conf          # Reverse proxy, load balancing & IP protection
├── docs/
│   ├── api-contract.md     # Authoritative contract for frontend agent
│   ├── architecture.md     # System design & concurrency guarantees
│   └── decisions.md        # Architecture Decision Records (ADRs)
├── docker-compose.yml      # Orchestration (PostgreSQL, Redis, Backend x2, NGINX)
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
└── README.md
```

---

## Quickstart & Local Setup

### Option 1: Run with Docker Compose (Recommended)
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Build and start all services
docker compose up --build -d

# 3. Verify container statuses
docker compose ps

# 4. Access SeatSurge Gateway
# API & Health: http://localhost:8000/health
# Swagger Docs: http://localhost:8000/docs
```

### Option 2: Run Tests Locally (Python 3.10+)
```bash
# Run pytest test suite
python -m pytest backend/tests -v
```

---

## API Contract & Frontend Integration
The frontend engineering agent should consult [docs/api-contract.md](docs/api-contract.md) for complete specifications of REST endpoints, request schemas, seat states, waiting room tokens, and WebSocket message schemas.
