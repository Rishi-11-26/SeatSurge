/**
 * SeatSurge Centralized API Client Service Layer
 * Authoritative endpoints defined per docs/api-contract.md (v1)
 * Protocol: REST (JSON) + WebSockets (RFC 6455)
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws/events';

/**
 * Stable Session ID stored in localStorage across tabs/refreshes
 */
export function getOrCreateSessionId() {
  const STORAGE_KEY = 'seatsurge_session_id';
  let sessionId = localStorage.getItem(STORAGE_KEY);
  if (!sessionId) {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      sessionId = crypto.randomUUID();
    } else {
      sessionId = 'sess_' + Math.random().toString(36).substring(2, 15);
    }
    localStorage.setItem(STORAGE_KEY, sessionId);
  }
  return sessionId;
}

/**
 * Generate unique Idempotency Key for hold and checkout mutations
 */
export function generateIdempotencyKey() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'idem_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10);
}

/**
 * Standard fetch helper with Session and Error handling
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const sessionId = getOrCreateSessionId();

  const headers = {
    'Content-Type': 'application/json',
    'X-Session-ID': sessionId,
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : null;

    if (!response.ok) {
      // Backend RFC 7807 inspired error schema
      const errorPayload = data?.error || {
        code: `HTTP_${response.status}`,
        message: response.statusText || 'Unknown API Error',
      };
      const error = new Error(errorPayload.message);
      error.code = errorPayload.code;
      error.details = errorPayload.details;
      error.status = response.status;
      throw error;
    }

    return data;
  } catch (err) {
    // If backend is not running yet during early development
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const netError = new Error(`Cannot connect to SeatSurge API Gateway at ${API_BASE_URL}. Ensure backend instances and NGINX are running.`);
      netError.code = 'NETWORK_GATEWAY_UNAVAILABLE';
      throw netError;
    }
    throw err;
  }
}

/**
 * 3. Waiting Room API
 * POST /api/v1/queue/enter
 */
export async function enterQueue(eventId = 1) {
  return request('/queue/enter', {
    method: 'POST',
    body: JSON.stringify({ event_id: eventId }),
  });
}

/**
 * 4. Seat Catalog & Live Map Snapshot
 * GET /api/v1/events/{event_id}/seats
 */
export async function getSeatMapSnapshot(eventId = 1) {
  return request(`/events/${eventId}/seats`, {
    method: 'GET',
  });
}

/**
 * 5. Atomic Seat Holds
 * POST /api/v1/events/{event_id}/holds
 * Max 6 seats. Adjacent required. Idempotent.
 */
export async function createSeatHold({
  eventId = 1,
  seatIds,
  admissionToken,
  idempotencyKey = generateIdempotencyKey(),
}) {
  const headers = {
    'Idempotency-Key': idempotencyKey,
  };
  if (admissionToken) {
    headers['X-Admission-Token'] = admissionToken;
  }

  return request(`/events/${eventId}/holds`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ seat_ids: seatIds }),
  });
}

/**
 * 6. Checkout & Payment Simulation
 * POST /api/v1/checkout/pay
 */
export async function checkoutPay({
  holdId,
  paymentMethod = 'simulated_card',
  simulateFailure = false,
  idempotencyKey = generateIdempotencyKey(),
}) {
  return request('/checkout/pay', {
    method: 'POST',
    headers: {
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      hold_id: holdId,
      payment_method: paymentMethod,
      simulate_failure: simulateFailure,
    }),
  });
}

/**
 * 8. Health & Observability
 * GET /api/v1/health or GET /health
 */
export async function getHealthStatus() {
  return request('/health', { method: 'GET' });
}
