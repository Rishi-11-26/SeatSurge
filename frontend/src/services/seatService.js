/**
 * SeatSurge Seat Map Service Layer
 * 
 * Manages 5,040 authoritative stadium seats.
 * Adheres to docs/api-contract.md & backend init_db.py:
 * - VIP: Rows A–D (4 rows × 60 = 240 seats, IDs 1–240, 15,000 cents)
 * - PREMIUM: Rows E–P (12 rows × 100 = 1,200 seats, IDs 241–1,440, 7,500 cents)
 * - STANDARD: Rows Q–Z & AA–AH (18 rows × 200 = 3,600 seats, IDs 1,441–5,040, 3,500 cents)
 */

import { fetchFullSeatMap, getSeatMapSnapshot } from './api.js';

export const SEAT_SECTIONS = [
  {
    id: 'ALL',
    name: 'Full Stadium Bowl',
    tier: 'ALL',
    totalSeats: 5040,
    rowsDescription: 'All 34 Rows (A–Z & AA–AH)',
  },
  {
    id: 'VIP',
    name: 'Floor VIP',
    tier: 'VIP',
    rows: ['A', 'B', 'C', 'D'],
    seatsPerRow: 60,
    totalSeats: 240,
    seatIdRange: [1, 240],
    priceCents: 15000,
    priceFormatted: '₹ 150.00',
    color: '#E8472B',
  },
  {
    id: 'PREMIUM',
    name: 'Lower Bowl',
    tier: 'PREMIUM',
    rows: ['E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'],
    seatsPerRow: 100,
    totalSeats: 1200,
    seatIdRange: [241, 1440],
    priceCents: 7500,
    priceFormatted: '₹ 75.00',
    color: '#C8962A',
  },
  {
    id: 'STANDARD',
    name: 'Upper Bowl',
    tier: 'STANDARD',
    rows: [
      'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
      'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH',
    ],
    seatsPerRow: 200,
    totalSeats: 3600,
    seatIdRange: [1441, 5040],
    priceCents: 3500,
    priceFormatted: '₹ 35.00',
    color: '#3F6B4F',
  },
];

/**
 * Deterministic Mock Generator for all 5,040 seats matching backend init_db.py exactly.
 * Used during development simulation or as explicitly requested fallback.
 */
export function generateAuthoritativeSeatMap(eventId = 1) {
  const seats = [];
  let seatId = 1;

  // 1. VIP (Rows A-D, 60 seats/row)
  const vipRows = ['A', 'B', 'C', 'D'];
  for (const row of vipRows) {
    for (let num = 1; num <= 60; num++) {
      let status = 'AVAILABLE';
      if ((row === 'A' && (num === 15 || num === 16)) || (row === 'B' && num === 30)) {
        status = 'SOLD';
      } else if (row === 'C' && (num === 20 || num === 21 || num === 22)) {
        status = 'HELD';
      }

      seats.push({
        id: seatId,
        seat_id: seatId,
        event_id: eventId,
        row,
        number: num,
        section: 'Floor VIP',
        tier: 'VIP',
        price_cents: 15000,
        is_accessible: num === 1 || num === 2,
        status,
      });
      seatId++;
    }
  }

  // 2. PREMIUM (Rows E-P, 100 seats/row)
  const premiumRows = ['E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'];
  for (const row of premiumRows) {
    for (let num = 1; num <= 100; num++) {
      let status = 'AVAILABLE';
      if ((row === 'E' && (num === 45 || num === 46)) || (row === 'G' && num >= 50 && num <= 53)) {
        status = 'SOLD';
      } else if (row === 'H' && (num === 12 || num === 13)) {
        status = 'HELD';
      }

      seats.push({
        id: seatId,
        seat_id: seatId,
        event_id: eventId,
        row,
        number: num,
        section: 'Lower Bowl',
        tier: 'PREMIUM',
        price_cents: 7500,
        is_accessible: num === 1 || num === 2,
        status,
      });
      seatId++;
    }
  }

  // 3. STANDARD (Rows Q-Z, AA-AH, 200 seats/row)
  const standardRows = [
    'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH',
  ];
  for (const row of standardRows) {
    for (let num = 1; num <= 200; num++) {
      let status = 'AVAILABLE';
      if ((row === 'Q' && num >= 100 && num <= 104) || (row === 'Z' && num === 50)) {
        status = 'SOLD';
      } else if (row === 'AA' && num >= 80 && num <= 82) {
        status = 'HELD';
      }

      seats.push({
        id: seatId,
        seat_id: seatId,
        event_id: eventId,
        row,
        number: num,
        section: 'Upper Bowl',
        tier: 'STANDARD',
        price_cents: 3500,
        is_accessible: num === 1 || num === 2,
        status,
      });
      seatId++;
    }
  }

  return seats;
}

/**
 * Fetch seat map from real backend or fallback per configured mode.
 * Mode options:
 * - 'real': Strict real mode. Throws error if backend is unavailable.
 * - 'mock': Local simulation only.
 * - 'auto': Attempts live backend first; if unavailable, loads local layout with isLive: false.
 */
export async function loadSeatMap(eventId = 1, { mode = 'auto' } = {}) {
  if (mode === 'mock') {
    return {
      seats: generateAuthoritativeSeatMap(eventId),
      isLive: false,
      isMock: true,
      sequenceNumber: 1,
      totalSeats: 5040,
    };
  }

  try {
    const data = await fetchFullSeatMap(eventId);
    if (data && Array.isArray(data.seats) && data.seats.length > 0) {
      return {
        seats: data.seats,
        isLive: true,
        isMock: false,
        sequenceNumber: data.sequence_number || 1,
        totalSeats: data.total_seats || data.seats.length,
      };
    }
  } catch (err) {
    if (mode === 'real') {
      // In strict real mode, do not mask failures
      const error = new Error(`Live seat map fetch failed: ${err.message}`);
      error.cause = err;
      throw error;
    }

    console.info(`[SeatSurge] Backend at http://localhost:8000 not reachable (${err.message}). Loaded local 5,040 seat layout.`);
  }

  // Auto fallback with clear isLive: false flag
  const mockSeats = generateAuthoritativeSeatMap(eventId);
  return {
    seats: mockSeats,
    isLive: false,
    isMock: true,
    backendOffline: true,
    sequenceNumber: 1,
    totalSeats: 5040,
  };
}

/**
 * Validate Adjacent Group Selection (Up to 6 continuous seats in the same row)
 */
export function validateGroupAdjacency(selectedSeats) {
  if (!selectedSeats || selectedSeats.length === 0) {
    return { valid: true, error: null };
  }

  if (selectedSeats.length > 6) {
    return {
      valid: false,
      error: 'Maximum 6 seats per transaction exceeded.',
    };
  }

  if (selectedSeats.length === 1) {
    return { valid: true, error: null };
  }

  // All seats must belong to the exact same row
  const firstRow = selectedSeats[0].row;
  const sameRow = selectedSeats.every(s => s.row === firstRow);
  if (!sameRow) {
    return {
      valid: false,
      error: 'Group selection must belong to the exact same row.',
    };
  }

  // Sort numbers in ascending order
  const numbers = selectedSeats.map(s => s.number).sort((a, b) => a - b);
  for (let i = 0; i < numbers.length - 1; i++) {
    if (numbers[i + 1] !== numbers[i] + 1) {
      return {
        valid: false,
        error: `Seats in row ${firstRow} must be strictly adjacent (continuous numbers).`,
      };
    }
  }

  return { valid: true, error: null };
}

/**
 * Get contiguous adjacent seats starting from a given seat
 */
export function getContiguousSeats(allSeats, startSeat, count) {
  if (!startSeat || count <= 1) return [startSeat];

  const rowSeats = allSeats
    .filter(s => s.row === startSeat.row && s.section === startSeat.section)
    .sort((a, b) => a.number - b.number);

  const startIndex = rowSeats.findIndex(s => (s.id ?? s.seat_id) === (startSeat.id ?? startSeat.seat_id));
  if (startIndex === -1) return [startSeat];

  const candidateSeats = [];
  for (let i = startIndex; i < rowSeats.length && candidateSeats.length < count; i++) {
    const seat = rowSeats[i];
    if (seat.status !== 'AVAILABLE') break; // Must be available
    candidateSeats.push(seat);
  }

  return candidateSeats;
}
