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
- `X-Session-ID: <uuid>`: Client session identifier. Required for waiting room queueing, seat holds, and bot detection tracking.
- `Idempotency-Key: <uuid>`: Required for hold creation and checkout calls to prevent duplicate charge / reservation actions on network retries.

### Standard Response Headers
- `X-Backend-Instance: <backend-1|backend-2>`: Replicas handling the request.
- `X-Process-Time-Ms: <float>`: Server processing latency in milliseconds.

### Standard Error Schema (RFC 7807 inspired)
```json
{
  "error": {
    "code": "SEAT_ALREADY_HELD",
    "message": "One or more requested seats are no longer available.",
    "details": {
      "conflicting_seats": [102, 103]
    },
    "timestamp": "2026-11-13T12:00:00Z"
  }
}
```

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

---

## 3. Waiting Room & Virtual Queue

### 3.1. Enter Waiting Room / Queue Status
- **Method:** `POST /api/v1/queue/enter`
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
  "status": "WAITING",
  "queue_position": 42,
  "estimated_wait_seconds": 15,
  "admission_token": null,
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```
- **Response when admitted (200 OK):**
```json
{
  "status": "ADMITTED",
  "queue_position": 0,
  "estimated_wait_seconds": 0,
  "admission_token": "adm_tok_a8f9c0e2193b4",
  "token_expires_at": "2026-11-13T12:15:00Z",
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

---

## 4. Seat Catalog & Live Map

### 4.1. Get Event Seat Map Snapshot
- **Method:** `GET /api/v1/events/{event_id}/seats`
- **Response (200 OK):**
```json
{
  "event_id": 1,
  "total_seats": 5040,
  "sequence_number": 1042,
  "timestamp": "2026-11-13T12:00:00Z",
  "seats": [
    {
      "seat_id": 1,
      "row": "A",
      "number": 1,
      "tier": "VIP",
      "price_cents": 15000,
      "status": "AVAILABLE"
    },
    {
      "seat_id": 2,
      "row": "A",
      "number": 2,
      "tier": "VIP",
      "price_cents": 15000,
      "status": "HELD"
    }
  ]
}
```

---

## 5. Atomic Seat Holds

### 5.1. Create Hold (Single or Group)
- **Method:** `POST /api/v1/events/{event_id}/holds`
- **Headers:**
  - `X-Session-ID: <uuid>`
  - `X-Admission-Token: <token>`
  - `Idempotency-Key: <uuid>`
- **Request Body:**
```json
{
  "seat_ids": [101, 102, 103]
}
```
*Note: Maximum 6 seats. Must be adjacent for group reservations. All-or-nothing guarantee.*
- **Response (201 Created):**
```json
{
  "hold_id": "hld_98a7cf2e109",
  "event_id": 1,
  "seat_ids": [101, 102, 103],
  "held_at": "2026-11-13T12:00:00Z",
  "expires_at": "2026-11-13T12:02:00Z",
  "time_remaining_seconds": 120
}
```
- **Error Responses:**
  - `409 Conflict`: `SEATS_UNAVAILABLE` (Any seat already held/sold)
  - `400 Bad Request`: `NOT_ADJACENT` or `EXCEEDS_GROUP_LIMIT`
  - `401 Unauthorized`: `INVALID_ADMISSION_TOKEN`

---

## 6. Checkout & Payment Simulator

### 6.1. Initiate Checkout
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

## 7. Real-Time WebSockets

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
1. Client must send a resync request: `{"action": "RESYNC", "from_seq": 1041}`
2. Or client fetches full snapshot via `GET /api/v1/events/{event_id}/seats`.

---

## 8. Health & Observability

- `GET /health` / `GET /api/v1/health`: Overall health and service statuses (database, redis).
- `GET /api/v1/health/liveness`: Container liveness.
- `GET /api/v1/health/readiness`: Container readiness.
