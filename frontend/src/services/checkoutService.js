/**
 * SeatSurge Checkout Service
 *
 * Manages:
 *  - Active hold retrieval / countdown from localStorage:
 *    Uses backend expires_at as authoritative source if present; falls back to heldAt + 120s.
 *  - Idempotency key lifecycle: one stable key per hold_id, never regenerated on retry
 *  - Mock payment adapter [DEV SIMULATION]
 *  - Real payment adapter POST /api/v1/checkout/pay per api-contract.md §7
 */

import { checkoutPay } from './api';

// ─── Payment Status Constants ─────────────────────────────────────────────────
export const PAYMENT_STATUS = Object.freeze({
  IDLE:               'IDLE',
  PROCESSING:         'PROCESSING',
  SUCCEEDED:          'SUCCEEDED',
  DECLINED:           'DECLINED',
  PENDING:            'PENDING',
  ERROR:              'ERROR',
  DUPLICATE_BLOCKED:  'DUPLICATE_BLOCKED',
});

// ─── Hold Management ──────────────────────────────────────────────────────────
const HOLD_KEY     = 'seatsurge_active_hold';
const HOLD_TTL_MS  = 120_000; // 120 s per api-contract.md §6.1

/**
 * Read active hold from localStorage and annotate with live countdown.
 * Uses backend `expires_at` timestamp as authoritative source if present.
 * Returns null if no hold exists.
 * Returns hold object with { isExpired, remainingMs, remainingSeconds }.
 */
export function getActiveHold() {
  try {
    const raw = localStorage.getItem(HOLD_KEY);
    if (!raw) return null;
    const hold = JSON.parse(raw);
    if (!hold) return null;

    let remainingMs = 0;
    let elapsedMs = 0;

    if (hold.expires_at) {
      // Authoritative backend expiration timestamp
      const expiresAtMs = new Date(hold.expires_at).getTime();
      remainingMs = Math.max(0, expiresAtMs - Date.now());
      elapsedMs = Math.max(0, HOLD_TTL_MS - remainingMs);
    } else if (hold.heldAt) {
      // Fallback client timestamp
      elapsedMs = Date.now() - hold.heldAt;
      remainingMs = Math.max(0, HOLD_TTL_MS - elapsedMs);
    } else {
      return null;
    }

    const remainingSeconds = Math.ceil(remainingMs / 1000);

    return {
      ...hold,
      elapsedMs,
      remainingMs,
      remainingSeconds,
      isExpired: remainingMs <= 0,
    };
  } catch {
    return null;
  }
}

export function clearActiveHold() {
  localStorage.removeItem(HOLD_KEY);
}

// ─── Idempotency Key Lifecycle ────────────────────────────────────────────────
// Rule: one key per logical hold/payment transaction; stable across retries.
// Stored in sessionStorage so it persists across page renders but not new sessions.
const IDEM_PREFIX = 'seatsurge_idem_';

export function getOrCreateIdempotencyKey(holdId) {
  if (!holdId) {
    return _newKey();
  }
  const storageKey = IDEM_PREFIX + holdId;
  let key = sessionStorage.getItem(storageKey);
  if (!key) {
    key = _newKey();
    sessionStorage.setItem(storageKey, key);
  }
  return key;
}

export function clearIdempotencyKey(holdId) {
  if (holdId) sessionStorage.removeItem(IDEM_PREFIX + holdId);
}

function _newKey() {
  return (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : 'idem_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10);
}

// ─── Mock Payment Adapter [DEV SIMULATION] ────────────────────────────────────
/**
 * Simulates backend payment processing response shapes.
 * Does NOT call any real payment gateway or backend endpoint.
 * Latency is synthetic. Use simulateFailure / simulatePending to test UI states.
 */
export async function processPaymentMock({
  holdId,
  seats = [],
  simulateFailure  = false,
  simulatePending  = false,
}) {
  // Simulate backend processing latency
  await new Promise(r => setTimeout(r, 1200 + Math.random() * 1000));

  if (simulateFailure) {
    return {
      payment_id: null,
      booking_id: null,
      status:     'DECLINED',
      error_code: 'CARD_DECLINED',
      message:    '[DEV SIMULATION] Payment declined. Hold NOT released — you may retry.',
      is_mock:    true,
    };
  }

  if (simulatePending) {
    return {
      payment_id: 'pay_pending_' + Math.random().toString(36).substring(2, 10),
      booking_id: null,
      status:     'PENDING',
      message:    '[DEV SIMULATION] Payment is processing. Do not close this tab.',
      is_mock:    true,
    };
  }

  // Compute total using integer cents — no floating-point arithmetic
  const totalCents = seats.reduce((sum, s) => sum + (s.price_cents || 0), 0);
  const bookingRef = 'SS-' + Date.now().toString(36).toUpperCase().substring(2)
                   + '-' + Math.random().toString(36).toUpperCase().substring(2, 6);

  return {
    payment_id:   'pay_mock_' + Math.random().toString(36).substring(2, 12),
    booking_id:   bookingRef,
    status:       'SUCCEEDED',
    seat_ids:     seats.map(s => s.id ?? s.seat_id),
    total_cents:  totalCents,
    confirmed_at: new Date().toISOString(),
    is_mock:      true,
  };
}

// ─── Real Payment Adapter ─────────────────────────────────────────────────────
/**
 * Calls POST /api/v1/checkout/pay per docs/api-contract.md §7.
 * Uses stable idempotency key — safe to retry on network error.
 */
export async function processPaymentReal({
  holdId,
  simulateFailure = false,
  idempotencyKey,
}) {
  try {
    const data = await checkoutPay({
      holdId,
      paymentMethod: 'simulated_card',
      simulateFailure,
      idempotencyKey,
    });
    return {
      ...data,
      is_mock: false,
    };
  } catch (err) {
    if (err.status === 404) {
      const pendingErr = new Error('Checkout Payment endpoint (POST /api/v1/checkout/pay) returned HTTP 404: Payment simulation is pending backend Phase 6 implementation.');
      pendingErr.code = 'BACKEND_DEPENDENCY_PENDING';
      pendingErr.status = 404;
      throw pendingErr;
    }
    throw err;
  }
}
