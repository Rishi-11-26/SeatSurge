/**
 * SeatSurge Queue Service
 *
 * Two pluggable adapters — swap mock → real in F5 without touching QueuePage.
 *
 * MOCK ADAPTER  (DEVELOPMENT SIMULATION):
 *   Simulates FIFO queue position updates locally.
 *   Does NOT communicate with backend Redis or any real queue.
 *   All position numbers, estimated-wait values and admission tokens are synthetic.
 *
 * REAL ADAPTER:
 *   Calls POST /api/v1/queue/enter per docs/api-contract.md §5.
 *   Requires backend NGINX + backend instances to be running.
 *
 * Admission tokens are stored in sessionStorage only — never rendered in UI.
 */

import { enterQueue } from './api';

// ─── State Constants ──────────────────────────────────────────────────────────
export const QUEUE_STATUS = Object.freeze({
  NOT_JOINED:    'NOT_JOINED',
  WAITING:       'WAITING',
  ADMITTED:      'ADMITTED',
  EXPIRED:       'EXPIRED',
  CANCELLED:     'CANCELLED',
  ERROR:         'ERROR',
  RECONNECTING:  'RECONNECTING',
});

// ─── Storage Keys ─────────────────────────────────────────────────────────────
const QUEUE_SESSION_KEY    = 'seatsurge_queue_session';
const ADMISSION_TOKEN_KEY  = 'seatsurge_admission_token'; // sessionStorage only

// ─── Queue Session Persistence (localStorage) ─────────────────────────────────
export function getStoredQueueSession() {
  try {
    const raw = localStorage.getItem(QUEUE_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persistQueueSession(session) {
  try {
    localStorage.setItem(QUEUE_SESSION_KEY, JSON.stringify(session));
  } catch { /* quota – ignore */ }
}

export function clearQueueSession() {
  localStorage.removeItem(QUEUE_SESSION_KEY);
  sessionStorage.removeItem(ADMISSION_TOKEN_KEY);
}

// ─── Admission Token (sessionStorage — secure, never rendered) ────────────────
export function getAdmissionToken() {
  return sessionStorage.getItem(ADMISSION_TOKEN_KEY) || null;
}

function persistAdmissionToken(token) {
  if (token) sessionStorage.setItem(ADMISSION_TOKEN_KEY, token);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function uuid() {
  return (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : 'sess_' + Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

// ─── Mock Adapter Constants ───────────────────────────────────────────────────
const MOCK_INITIAL_POSITION_MIN = 18;
const MOCK_INITIAL_POSITION_MAX = 72;
const MOCK_ADVANCE_MIN          = 1;
const MOCK_ADVANCE_MAX          = 5;
export const MOCK_POLL_INTERVAL_MS = 3000;
// Approx seconds per queue position (for estimated wait display)
const SECS_PER_POSITION = 2;

// ─── Mock Adapter ─────────────────────────────────────────────────────────────

/**
 * [DEV SIMULATION] Join queue — returns a synthesised WAITING session.
 * Simulates ~400–900 ms network latency.
 */
export async function joinQueueMock(eventId = 1) {
  await new Promise(r => setTimeout(r, rand(400, 900)));

  const position = rand(MOCK_INITIAL_POSITION_MIN, MOCK_INITIAL_POSITION_MAX);
  const session = {
    status:                  QUEUE_STATUS.WAITING,
    queue_position:          position,
    initial_position:        position,
    estimated_wait_seconds:  position * SECS_PER_POSITION,
    session_id:              uuid(),
    event_id:                eventId,
    joined_at:               Date.now(),
    is_mock:                 true,
  };

  persistQueueSession(session);
  return session;
}

/**
 * [DEV SIMULATION] Poll queue — advances position toward 0.
 * Returns updated session. Caller is responsible for scheduling.
 */
export async function pollQueueMock(currentSession) {
  await new Promise(r => setTimeout(r, rand(150, 400)));

  if (!currentSession || currentSession.status !== QUEUE_STATUS.WAITING) {
    return currentSession;
  }

  const advance    = rand(MOCK_ADVANCE_MIN, MOCK_ADVANCE_MAX);
  const newPos     = Math.max(0, currentSession.queue_position - advance);

  if (newPos === 0) {
    // Admitted — generate a synthetic token (stored securely, never shown)
    const mockToken = 'adm_mock_' + Math.random().toString(36).substring(2, 16);
    persistAdmissionToken(mockToken);

    const admitted = {
      ...currentSession,
      status:                 QUEUE_STATUS.ADMITTED,
      queue_position:         0,
      estimated_wait_seconds: 0,
      admitted_at:            Date.now(),
    };
    persistQueueSession(admitted);
    return admitted;
  }

  const updated = {
    ...currentSession,
    queue_position:          newPos,
    estimated_wait_seconds:  newPos * SECS_PER_POSITION,
  };
  persistQueueSession(updated);
  return updated;
}

// ─── Real Adapter ─────────────────────────────────────────────────────────────

/**
 * Join queue via live backend: POST /api/v1/queue/enter
 * Requires X-Session-ID header (set by api.js request helper).
 */
export async function joinQueueReal(eventId = 1) {
  const response = await enterQueue(eventId);
  return _processRealResponse(response, eventId, Date.now());
}

/**
 * Poll queue status — re-calls POST /api/v1/queue/enter.
 * Per api-contract.md §5: same endpoint is used to check current status.
 */
export async function pollQueueReal(eventId = 1) {
  const response = await enterQueue(eventId);
  return _processRealResponse(response, eventId, null);
}

function _processRealResponse(response, eventId, joinedAt) {
  if (response.status === QUEUE_STATUS.ADMITTED && response.admission_token) {
    persistAdmissionToken(response.admission_token);
  }

  const session = {
    status:                 response.status,
    queue_position:         response.queue_position ?? 0,
    estimated_wait_seconds: response.estimated_wait_seconds ?? 0,
    session_id:             response.session_id ?? uuid(),
    event_id:               eventId,
    joined_at:              joinedAt ?? Date.now(),
    is_mock:                false,
  };

  persistQueueSession(session);
  return session;
}
