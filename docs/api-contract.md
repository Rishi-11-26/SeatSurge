# SeatSurge API Contract (v1)

**Target Audience:** Frontend Engineering Agent & Backend Integration  
**Protocol:** REST (JSON) + WebSockets (RFC 6455)  
**Base URL:** `http://localhost:8000/api/v1`  
**WebSocket URL:** `ws://localhost:8000/ws/events`  
**NGINX Gateway:** Port 8000 (Load balances backend-1 and backend-2)

---

## 1. Global Conventions & Headers

### Request Headers
- `Content-Type: application/json`
- `X-Session-ID: <uuid>`: Client session identifier. Required for waiting room queueing, seat holds, rate-limiting, and bot detection tracking.
- `Idempotency-Key: <uuid>`: Required for hold creation and checkout calls to prevent duplicate charge / reservation actions on network retries.

### Standard Response Headers
- `X-Backend-Instance: <backend-1|backend-2>`: Backend replica handling the request.
- `X-Process-Time-Ms: <float>`: Server processing latency in milliseconds.

### Standard Error Schema (RFC 7807 inspired)
All non-2xx HTTP responses from SeatSurge return a uniform JSON error envelope:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Event with ID 999 not found.",
    "details": {},
    "timestamp": "2026-11-13T12:00:00Z"
  }
}
```

Common machine-readable error codes:
- `BAD_REQUEST` (400)
- `UNAUTHORIZED` (401)
- `FORBIDDEN` (403)
- `NOT_FOUND` (404)
- `CONFLICT` (409) — e.g. seat already sold or held
- `VALIDATION_ERROR` (422) — field validation errors included in `details.errors`
- `RATE_LIMIT_EXCEEDED` (429) — header `Retry-After: <seconds>` included
- `INTERNAL_SERVER_ERROR` (500)

---

## 2. Seat Lifecycle & States

Every seat has one of the following authoritative states:

| State | Description | User Action Permitted |
|---|---|---|
| `AVAILABLE` | Seat is free to be held | Can hold |
| `HELD` | Reserved by a session for up to 120 seconds | Holding session can proceed to checkout; others blocked |
| `PAYING` | Checkout initiated; payment in-flight (protected from reaper) | Holding session completing payment |
| `SOLD` | Persisted to PostgreSQL permanently | Read-only |
| `RELEASED` | Hold expired or payment definitively declined | Reverts to `AVAILABLE` |

### Booking Record Statuses (PostgreSQL)
Permanent booking records in the `bookings` table track the full lifecycle:
- `CONFIRMED`: Active, completed sale. Only one CONFIRMED booking per `(event_id, seat_id)` is permitted by database partial unique index.
- `CANCELLED`: Previously booked seat was cancelled. Seat returns to `AVAILABLE` and can be booked again.
- `REFUNDED`: Booking was refunded.

---

## 3. Events Catalogue

### 3.1. List All Active Events
- **Method:** `GET /api/v1/events`
- **Response (200 OK):**
```json
{
  "events": [
    {
      "id": 1,
      "name": "YUKTIK 2026 Grand Concert",
      "description": "YUKTIK 2026 flagship tech & music festival live concert.",
      "venue_name": "YUKTIK Grand Auditorium",
      "total_seats": 5040,
      "start_time": "2026-11-20T18:30:00Z",
      "is_active": true,
      "created_at": "2026-11-13T12:00:00Z"
    }
  ],
  "count": 1
}
```

### 3.2. Get Event Details
- **Method:** `GET /api/v1/events/{event_id}`
- **Response (200 OK):**
```json
{
  "id": 1,
  "name": "YUKTIK 2026 Grand Concert",
  "description": "YUKTIK 2026 flagship tech & music festival live concert.",
  "venue_name": "YUKTIK Grand Auditorium",
  "total_seats": 5040,
  "start_time": "2026-11-20T18:30:00Z",
  "is_active": true,
  "created_at": "2026-11-13T12:00:00Z"
}
```
- **Error (404 Not Found):** `{"error": {"code": "NOT_FOUND", "message": "Event with ID 999 not found.", "details": {}, "timestamp": "..."}}`

---

## 4. Seat Catalog & Live Map

### 4.1. Get Event Seat Map Snapshot (Paginated)
- **Method:** `GET /api/v1/events/{event_id}/seats`
- **Query Parameters:**
  - `page` (int, default: 1): Page number (1-indexed).
  - `page_size` (int, default: 100, max: 1000): Number of seats per page.
  - `tier` (string, optional): Filter by tier (`VIP`, `PREMIUM`, `STANDARD`).
  - `row` (string, optional): Filter by row letter (e.g. `A`, `E`, `AA`).
- **Response (200 OK):**
```json
{
  "event_id": 1,
  "total_seats": 5040,
  "sequence_number": 1,
  "timestamp": "2026-11-13T12:00:00Z",
  "page": 1,
  "page_size": 100,
  "total_pages": 51,
  "seats": [
    {
      "seat_id": 1,
      "event_id": 1,
      "row": "A",
      "number": 1,
      "section": "Floor VIP",
      "tier": "VIP",
      "price_cents": 15000,
      "is_accessible": true,
      "status": "AVAILABLE"
    },
    {
      "seat_id": 2,
      "event_id": 1,
      "row": "A",
      "number": 2,
      "section": "Floor VIP",
      "tier": "VIP",
      "price_cents": 15000,
      "is_accessible": true,
      "status": "HELD"
    }
  ]
}
```

### 4.2. Get Single Seat Status
- **Method:** `GET /api/v1/events/{event_id}/seats/{seat_id}`
- **Response (200 OK):**
```json
{
  "seat_id": 1,
  "event_id": 1,
  "row": "A",
  "number": 1,
  "section": "Floor VIP",
  "tier": "VIP",
  "price_cents": 15000,
  "is_accessible": true,
  "status": "AVAILABLE"
}
```

### 4.3. Get High-Performance Availability Summary
- **Method:** `GET /api/v1/events/{event_id}/availability`
- **Response (200 OK):**
```json
{
  "event_id": 1,
  "total_seats": 5040,
  "available_seats": 5040,
  "held_seats": 0,
  "sold_seats": 0,
  "tiers": {
    "VIP": {
      "tier": "VIP",
      "total": 240,
      "available": 240,
      "held": 0,
      "sold": 0,
      "price_cents": 15000
    },
    "PREMIUM": {
      "tier": "PREMIUM",
      "total": 1200,
      "available": 1200,
      "held": 0,
      "sold": 0,
      "price_cents": 7500
    },
    "STANDARD": {
      "tier": "STANDARD",
      "total": 3600,
      "available": 3600,
      "held": 0,
      "sold": 0,
      "price_cents": 3500
    }
  },
  "timestamp": "2026-11-13T12:00:00Z"
}
```

---

## 5. Waiting Room & Virtual Queue (Phase 5)

### 5.1. Enter Waiting Room / Queue Status
- **Method:** `POST /api/v1/queue/enter`
- **Headers:** `X-Session-ID: <uuid>`
- **Request Body:**
```json
{
  "event_id": 1
}
```
- **Response when queued (200 OK):**
```json
{
  "status": "WAITING",
  "queue_position": 42,
  "estimated_wait_seconds": 15,
  "admission_token": null,
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_id": 1
}
```
- **Response when admitted (200 OK):**
```json
{
  "status": "ADMITTED",
  "queue_position": 0,
  "estimated_wait_seconds": 0,
  "admission_token": "adm_9b1deb4d_1_1763000000_a8f9c0e2193b4",
  "token_expires_at": "2026-11-13T12:15:00Z",
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_id": 1
}
```

### 5.2. Get Queue Status (Polling)
- **Method:** `GET /api/v1/queue/status?event_id={event_id}`
- **Headers:** `X-Session-ID: <uuid>`
- **Response (200 OK):** Identical schema to 5.1 (returns current WAITING rank or ADMITTED token).

### 5.3. Leave Waiting Room
- **Method:** `POST /api/v1/queue/leave`
- **Headers:** `X-Session-ID: <uuid>`
- **Request Body:**
```json
{
  "event_id": 1
}
```
- **Response (200 OK):**
```json
{
  "status": "LEFT",
  "message": "Successfully left the queue.",
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_id": 1
}
```

---

## 6. Atomic Seat Holds (Phase 2)

### 6.1. Create Hold (Single or Group)
- **Method:** `POST /api/v1/events/{event_id}/holds`
- **Headers:**
  - `X-Session-ID: <string>` (Required: client session identifier)
  - `X-Admission-Token: <token>` (Optional until Phase 5 waiting room enforcement)
  - `Idempotency-Key: <string>` (Optional: guarantees identical result on retry)
- **Request Body:**
```json
{
  "seat_ids": [101, 102, 103]
}
```
*Note: Maximum 6 seats per request. Seats must be in the same row and strictly adjacent (consecutive numbers). All-or-nothing atomicity via Redis Lua script.*
- **Response (201 Created):**
```json
{
  "hold_id": "hld_98a7cf2e109",
  "event_id": 1,
  "seat_ids": [101, 102, 103],
  "held_at": "2026-11-13T12:00:00Z",
  "expires_at": "2026-11-13T12:02:00Z",
  "time_remaining_seconds": 120,
  "status": "HELD"
}
```
- **Error Responses:**
  - `409 Conflict`: `SEATS_UNAVAILABLE` (Any seat already held/sold; includes conflicting seat details)
  - `400 Bad Request`: `NOT_ADJACENT` or `EXCEEDS_GROUP_LIMIT`
  - `404 Not Found`: `SEAT_NOT_FOUND`
  - `503 Service Unavailable`: `RECOVERY_IN_PROGRESS` (Redis state reconstruction active)

### 6.2. Release Hold (Manual Cancellation)
- **Method:** `DELETE /api/v1/events/{event_id}/holds/{hold_id}`
- **Headers:**
  - `X-Session-ID: <string>` (Required: must match hold owner session)
- **Response (200 OK):**
```json
{
  "hold_id": "hld_98a7cf2e109",
  "event_id": 1,
  "released_seats": [101, 102, 103],
  "status": "RELEASED",
  "released_at": "2026-11-13T12:01:10Z"
}
```
- **Error Responses:**
  - `404 Not Found`: `HOLD_NOT_FOUND`
  - `403 Forbidden`: `FORBIDDEN` (Session ID does not match hold owner)
  - `409 Conflict`: `HOLD_PAYING` (Hold is currently in checkout/payment and cannot be cancelled)

### 6.3. Inspect Hold Status
- **Method:** `GET /api/v1/events/{event_id}/holds/{hold_id}`
- **Headers:**
  - `X-Session-ID: <string>` (Required)
- **Response (200 OK):**
```json
{
  "hold_id": "hld_98a7cf2e109",
  "event_id": 1,
  "seat_ids": [101, 102, 103],
  "held_at": "2026-11-13T12:00:00Z",
  "expires_at": "2026-11-13T12:02:00Z",
  "time_remaining_seconds": 85,
  "status": "HELD"
}
```
- **Error Responses:**
  - `404 Not Found`: `HOLD_NOT_FOUND` or `HOLD_EXPIRED`

---

## 7. Checkout & Payment Simulator (Phase 6)

### 7.1. Initiate Checkout
- **Method:** `POST /api/v1/checkout/pay`
- **Headers:**
  - `X-Session-ID: <uuid>`
  - `Idempotency-Key: <uuid>`
- **Request Body:**
```json
{
  "hold_id": "hld_98a7cf2e109",
  "payment_method": "simulated_card",
  "simulate_failure": false
}
```
- **Response (200 OK):**
```json
{
  "payment_id": "pay_5f8a0b12",
  "booking_id": "bk_89a0f443",
  "status": "SUCCEEDED",
  "seat_ids": [101, 102, 103],
  "total_cents": 45000,
  "confirmed_at": "2026-11-13T12:01:30Z"
}
```

---

## 8. Real-Time WebSockets (Phase 3)

- **Endpoint:** `ws://localhost:8000/ws/events?event_id=1`
- **Client Protocol:**
  - Connect with event query param.
  - Listen for seat state change messages.

### Message Payload (Server -> Client)
```json
{
  "type": "SEAT_STATUS_CHANGE",
  "seq": 1043,
  "event_id": 1,
  "updates": [
    {
      "seat_id": 101,
      "status": "HELD",
      "hold_id": "hld_98a7cf2e109"
    }
  ],
  "timestamp": "2026-11-13T12:00:01Z"
}
```

### Gap Detection & Recovery
If the client receives a message where `seq > client_last_seq + 1`:
1. Client sends a resync request: `{"action": "RESYNC", "from_seq": 1041}`
2. Or client fetches full snapshot via `GET /api/v1/events/{event_id}/seats`.

---

## 9. Monitoring & Observability

### 9.1. Per-Instance Metrics Dashboard
- **Method:** `GET /api/v1/metrics`
- **Response (200 OK):**
```json
{
  "timestamp": "2026-11-13T12:00:00Z",
  "instance_id": "backend-1",
  "uptime_seconds": 3600.5,
  "total_requests": 14205,
  "requests_per_second": 124.5,
  "latency_p50_ms": 8.42,
  "latency_p95_ms": 42.15,
  "latency_p99_ms": 89.30,
  "cache_hit_ratio": 0.9412,
  "active_holds_count": 18,
  "sold_seats_count": 320,
  "bots_blocked_count": 14
}
```
*Note: `active_holds_count` is null if Redis is unreachable.*

### 9.2. Health Check Endpoints
- `GET /health` / `GET /api/v1/health`: Overall health and service status (database, redis).
- `GET /api/v1/health/liveness`: Container liveness.
- `GET /api/v1/health/readiness`: Container readiness.
