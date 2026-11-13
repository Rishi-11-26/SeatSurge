/**
 * SeatSurge Centralized API Client Service Layer
 * Authoritative endpoints defined per docs/api-contract.md (v1)
 * Protocol: REST (JSON) + WebSockets (RFC 6455)
 */

const env = (typeof import.meta !== 'undefined' && import.meta.env) ? import.meta.env : {};
const isBrowser = typeof window !== 'undefined';
const hostOrigin = isBrowser ? window.location.origin : 'http://localhost:8000';
const wsProto = (isBrowser && window.location.protocol === 'https:') ? 'wss:' : 'ws:';
const wsHost = isBrowser ? window.location.host : 'localhost:8000';

export const API_BASE_URL = env.VITE_API_BASE_URL || `${hostOrigin}/api/v1`;
export const GATEWAY_ROOT = env.VITE_GATEWAY_ROOT || hostOrigin;
export const WS_BASE_URL = env.VITE_WS_BASE_URL || `${wsProto}//${wsHost}/ws/events`;

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
 * Standard fetch helper with Session and Error handling (RFC 7807)
 */
async function request(endpoint, options = {}) {
  // Allow full URL (e.g. root /health) or relative to API_BASE_URL
  const url = endpoint.startsWith('http://') || endpoint.startsWith('https://')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;

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
      // Extract backend error details supporting both FastAPI details and RFC 7807 schemas
      let code = `HTTP_${response.status}`;
      let message = response.statusText || 'API Request Failed';
      let details = {};

      if (data) {
        if (typeof data.detail === 'object' && data.detail !== null) {
          code = data.detail.code || code;
          message = data.detail.message || message;
          details = data.detail;
        } else if (typeof data.detail === 'string') {
          message = data.detail;
        } else if (data.error) {
          code = data.error.code || code;
          message = data.error.message || message;
          details = data.error.details || data.error;
        } else if (data.code || data.message) {
          code = data.code || code;
          message = data.message || message;
        }
      }

      // Capture rate limit Retry-After header if present
      const retryAfter = response.headers.get('retry-after');
      if (retryAfter) {
        details.retryAfter = parseInt(retryAfter, 10) || 60;
      }

      const error = new Error(message || 'API request failed');
      error.code = code;
      error.details = details;
      error.status = response.status;
      error.timestamp = data?.timestamp || new Date().toISOString();
      throw error;
    }

    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const netError = new Error(`Cannot connect to SeatSurge API Gateway at ${url}. Ensure backend instances and NGINX are running.`);
      netError.code = 'NETWORK_GATEWAY_UNAVAILABLE';
      netError.status = 0;
      throw netError;
    }
    throw err;
  }
}

/**
 * 1. Events Catalog API
 * GET /api/v1/events
 */
export async function getEvents() {
  return request('/events', { method: 'GET' });
}

/**
 * GET /api/v1/events/{event_id}
 */
export async function getEvent(eventId = 1) {
  return request(`/events/${eventId}`, { method: 'GET' });
}

/**
 * 2. Seat Catalog & Live Map Snapshot
 * GET /api/v1/events/{event_id}/seats
 * Query params: page, page_size, tier, row
 */
export async function getSeatMapSnapshot(eventId = 1, { page = 1, page_size = 100, tier, row } = {}) {
  const params = new URLSearchParams();
  if (page) params.append('page', page);
  if (page_size) params.append('page_size', page_size);
  if (tier) params.append('tier', tier);
  if (row) params.append('row', row);

  const query = params.toString() ? `?${params.toString()}` : '';
  return request(`/events/${eventId}/seats${query}`, { method: 'GET' });
}

/**
 * Fetch all 5,040 seats paginated from backend
 * Backend max page_size is 1,000 (le=1000 validation in FastAPI).
 * Fetches page 1, determines total_pages (6 pages for 5,040 seats),
 * and fetches the rest concurrently.
 */
export async function fetchFullSeatMap(eventId = 1) {
  const PAGE_SIZE = 1000;
  const firstPage = await getSeatMapSnapshot(eventId, { page: 1, page_size: PAGE_SIZE });

  let allSeats = [...(firstPage.seats || [])];
  const totalPages = firstPage.total_pages || 1;

  if (totalPages > 1) {
    const pagePromises = [];
    for (let p = 2; p <= totalPages; p++) {
      pagePromises.push(getSeatMapSnapshot(eventId, { page: p, page_size: PAGE_SIZE }));
    }
    const subsequentPages = await Promise.all(pagePromises);
    for (const pageData of subsequentPages) {
      if (pageData && Array.isArray(pageData.seats)) {
        allSeats = allSeats.concat(pageData.seats);
      }
    }
  }

  // Normalize seats so `id` and `seat_id` are consistently available
  const normalizedSeats = allSeats.map(seat => ({
    ...seat,
    id: seat.seat_id ?? seat.id,
    seat_id: seat.seat_id ?? seat.id,
  }));

  return {
    seats: normalizedSeats,
    total_seats: firstPage.total_seats || normalizedSeats.length,
    sequence_number: firstPage.sequence_number || 0,
    timestamp: firstPage.timestamp || new Date().toISOString(),
    isLive: true,
  };
}

/**
 * GET /api/v1/events/{event_id}/seats/{seat_id}
 */
export async function getSingleSeat(eventId = 1, seatId) {
  return request(`/events/${eventId}/seats/${seatId}`, { method: 'GET' });
}

/**
 * GET /api/v1/events/{event_id}/availability
 */
export async function getSeatAvailability(eventId = 1) {
  return request(`/events/${eventId}/availability`, { method: 'GET' });
}

/**
 * 3. Waiting Room API (Phase 5)
 * POST /api/v1/queue/enter
 */
export async function enterQueue(eventId = 1) {
  return request('/queue/enter', {
    method: 'POST',
    body: JSON.stringify({ event_id: eventId }),
  });
}

/**
 * GET /api/v1/queue/status
 * Queries current FIFO queue position or admission status per Phase 5.
 * Strictly uses GET /api/v1/queue/status without silent fallback.
 */
export async function getQueueStatus(eventId = 1) {
  return request(`/queue/status?event_id=${eventId}`, { method: 'GET' });
}

/**
 * POST /api/v1/queue/leave
 * Notifies queue manager that user voluntarily vacated their queue slot.
 */
export async function leaveQueue(eventId = 1) {
  return request('/queue/leave', {
    method: 'POST',
    body: JSON.stringify({ event_id: eventId }),
  });
}

/**
 * 4. Atomic Seat Holds (Phase 2)
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
 * DELETE /api/v1/events/{event_id}/holds/{hold_id}
 * Explicitly releases held seats back to the AVAILABLE pool.
 */
export async function releaseSeatHold({ eventId = 1, holdId }) {
  if (!holdId) return null;
  return request(`/events/${eventId}/holds/${holdId}`, {
    method: 'DELETE',
  });
}

/**
 * GET /api/v1/events/{event_id}/holds/{hold_id}
 * Inspects active hold metadata, time remaining, and status.
 */
export async function getSeatHold({ eventId = 1, holdId }) {
  if (!holdId) return null;
  return request(`/events/${eventId}/holds/${holdId}`, {
    method: 'GET',
  });
}

/**
 * 5. Checkout & Payment Simulation (Phase 6)
 * POST /api/v1/checkout/pay
 */
export async function checkoutPay({
  holdId,
  paymentMethod = 'simulated_card',
  simulateFailure = false,
  simulatePending = false,
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
      simulate_pending: simulatePending,
    }),
  });
}

/**
 * GET /api/v1/checkout/payments/{payment_id}
 * Authoritative query for payment transaction status and confirmed booking ID.
 */
export async function getPaymentStatus(paymentId) {
  return request(`/checkout/payments/${paymentId}`, { method: 'GET' });
}

/**
 * 6. Health & Diagnostics
 * GET /health or GET /api/v1/health
 */
export async function getHealthStatus() {
  // Probe root /health or /api/v1/health
  try {
    return await request(`${GATEWAY_ROOT}/health`, { method: 'GET' });
  } catch {
    return request('/health', { method: 'GET' });
  }
}

/**
 * 7. Monitoring & Metrics
 * GET /api/v1/metrics
 */
export async function getMetrics() {
  return request('/metrics', { method: 'GET' });
}
