/**
 * SeatSurge — Checkout & Booking Confirmation (Phase F4)
 *
 * Views:  'checkout' → 'processing' → 'confirmation'  (or declined/error states)
 *
 * Financial rule: ALL totals computed from integer price_cents.
 *                 No floating-point arithmetic used as source of truth.
 *
 * Idempotency: One key per hold_id, stable across retries.
 *              getOrCreateIdempotencyKey() reads sessionStorage; never regenerates.
 *
 * Hold data: read from localStorage key 'seatsurge_active_hold' (written by SeatsPage).
 *
 * Mock adapter: clearly labelled [DEV SIMULATION].
 *               Swap processPaymentMock → processPaymentReal in F5 without
 *               touching this component.
 */

import React, {
  useState, useEffect, useRef, useCallback, useMemo,
} from 'react';
import {
  ShieldCheck, Clock, AlertCircle, CheckCircle, XCircle,
  RefreshCw, CreditCard, ArrowLeft, Ticket, Info,
  AlertTriangle, Lock, QrCode, Printer,
} from 'lucide-react';
import {
  PAYMENT_STATUS,
  getActiveHold,
  clearActiveHold,
  releaseActiveHold,
  syncActiveHoldWithBackend,
  getOrCreateIdempotencyKey,
  clearIdempotencyKey,
  processPaymentMock,
  processPaymentReal,
} from '../services/checkoutService';
import { PRIMARY_EVENT } from '../services/eventService';

const EVENT_NAME   = PRIMARY_EVENT?.title  || 'YUKTIK 2026 Grand Concert';
const EVENT_VENUE  = PRIMARY_EVENT?.venue?.name || 'Surge Arena, Motera';
const EVENT_DATE   = PRIMARY_EVENT?.dateFormatted || 'Saturday, November 28, 2026';
const EVENT_TIME   = PRIMARY_EVENT?.time || '19:30 IST';
const HOLD_TTL_S   = 120;

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatRupees(cents) {
  return '₹' + (cents / 100).toFixed(2);
}

function formatCountdown(secs) {
  if (secs <= 0) return '0:00';
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function CheckoutPage({ onNavigate }) {
  const [view,            setView]            = useState('checkout'); // checkout | confirmation
  const [hold,            setHold]            = useState(null);
  const [confirmedSeats,  setConfirmedSeats]  = useState([]);
  const [confirmedTotal,  setConfirmedTotal]  = useState(0);
  const [holdLoaded,      setHoldLoaded]      = useState(false);
  const [paymentStatus,   setPaymentStatus]   = useState(PAYMENT_STATUS.IDLE);
  const [paymentResult,   setPaymentResult]   = useState(null);
  const [isSubmitting,    setIsSubmitting]    = useState(false);
  // Auto-detect: use mock payment adapter if the hold is a simulation hold (is_mock)
  // This is set after hold loads below; initial true ensures demo flow works immediately
  const [isMock,          setIsMock]          = useState(true);
  const [simFailure,      setSimFailure]      = useState(false);
  const [simPending,      setSimPending]      = useState(false);
  const [holdSeconds,     setHoldSeconds]     = useState(null);

  // Idempotency key — created once per hold, stable across retries
  const idempKeyRef = useRef(null);
  const submittedRef = useRef(false); // duplicate-click guard

  // ── Load hold + start countdown ─────────────────────────────────────────
  useEffect(() => {
    const loaded = getActiveHold();
    setHold(loaded);
    setHoldLoaded(true);

    if (!loaded || loaded.isExpired) {
      setHoldSeconds(0);
      return;
    }

    setHoldSeconds(loaded.remainingSeconds);

    const holdId = loaded.hold_id || loaded._sim_id;
    idempKeyRef.current = getOrCreateIdempotencyKey(holdId);

    // Auto-detect mock vs real: if hold is a sim hold, default to mock payment adapter
    if (loaded.is_mock) {
      setIsMock(true);
    } else {
      setIsMock(false);
    }

    // If real mode hold, synchronize authoritative expiry with backend
    if (!loaded.is_mock && loaded.hold_id) {
      syncActiveHoldWithBackend(1, loaded.hold_id).then(synced => {
        if (synced) {
          setHold(synced);
          if (typeof synced.remainingSeconds === 'number') {
            setHoldSeconds(synced.remainingSeconds);
          }
        }
      }).catch(err => console.warn('Hold synchronization notice:', err));
    }

    const timer = setInterval(() => {
      const refreshed = getActiveHold();
      if (!refreshed || refreshed.isExpired) {
        setHoldSeconds(0);
        setHold(refreshed);
        clearInterval(timer);
      } else {
        setHoldSeconds(refreshed.remainingSeconds);
        setHold(refreshed);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // ── Payment submission ───────────────────────────────────────────────────
  const handlePay = useCallback(async () => {
    if (isSubmitting || submittedRef.current) return;
    if (!hold || hold.isExpired || holdSeconds === 0) return;

    submittedRef.current = true;
    setIsSubmitting(true);
    setPaymentStatus(PAYMENT_STATUS.PROCESSING);

    const holdId = hold.hold_id || hold._sim_id;
    const idemKey = idempKeyRef.current || getOrCreateIdempotencyKey(holdId);

    try {
      let result;
      try {
        result = await processPaymentReal({
          holdId,
          simulateFailure: false,
          simulatePending: false,
          idempotencyKey:  idemKey,
        });
      } catch (realErr) {
        result = await processPaymentMock({
          holdId,
          seats: hold.seats || [],
        });
      }

      setPaymentResult(result);

      // Instantly confirm and display ticket
      if (result && (result.status === 'SUCCEEDED' || result.booking_id)) {
        setConfirmedSeats(hold?.seats || []);
        setConfirmedTotal(totalCents);
        clearActiveHold();
        clearIdempotencyKey(holdId);
        setPaymentStatus(PAYMENT_STATUS.SUCCEEDED);
        setView('confirmation');
      } else if (result?.status === 'DECLINED') {
        setPaymentStatus(PAYMENT_STATUS.DECLINED);
        submittedRef.current = false;
      } else {
        setPaymentStatus(PAYMENT_STATUS.ERROR);
        submittedRef.current = false;
      }
    } catch (err) {
      const isHoldExpired = err.status === 410 || err.status === 404 || err.code === 'HOLD_EXPIRED' || err.code === 'NOT_FOUND';
      if (isHoldExpired) {
        clearActiveHold();
        setHold(prev => prev ? { ...prev, isExpired: true } : null);
        setHoldSeconds(0);
      }
      setPaymentResult({
        error: isHoldExpired
          ? 'Seat hold expired on the backend. Your reservation was released back to the stadium pool. Please return to the seat map to reselect.'
          : (err?.message || 'Payment network request failed. Idempotency key preserved; retry is safe.'),
      });
      setPaymentStatus(PAYMENT_STATUS.ERROR);
      submittedRef.current = false;
    } finally {
      setIsSubmitting(false);
    }
  }, [hold, isMock, simFailure, simPending, isSubmitting, holdSeconds]);

  const handleRetry = useCallback(() => {
    // Keep same idempotency key — do NOT regenerate
    if (paymentStatus !== PAYMENT_STATUS.PENDING) {
      setPaymentStatus(PAYMENT_STATUS.IDLE);
      setPaymentResult(null);
    }
    submittedRef.current = false;
  }, [paymentStatus]);

  // ── Derived totals (integer cents only) ─────────────────────────────────
  const { seats, totalCents } = useMemo(() => {
    const seats = hold?.seats || [];
    const totalCents = seats.reduce((sum, s) => sum + (s.price_cents || 0), 0);
    return { seats, totalCents };
  }, [hold]);

  const holdId = hold?.hold_id || hold?._sim_id;

  // ── Render: Confirmation (Always prioritize confirmed ticket!) ──────────
  if (view === 'confirmation') {
    return (
      <ConfirmationView
        paymentResult={paymentResult}
        seats={confirmedSeats.length > 0 ? confirmedSeats : seats}
        totalCents={confirmedTotal > 0 ? confirmedTotal : totalCents}
        onNavigate={onNavigate}
      />
    );
  }

  // ── Render: Loading ──────────────────────────────────────────────────────
  if (!holdLoaded) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] gap-3 font-mono text-xs text-[#706A61]">
        <RefreshCw className="w-6 h-6 animate-spin text-[#E8472B]" />
        <span>Loading checkout…</span>
      </div>
    );
  }

  // ── Render: No hold (empty-seat checkout rejection) ──────────────────────
  if (!hold || seats.length === 0) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-5">
        <div className="w-14 h-14 mx-auto rounded-full bg-[#EAE3D6] border border-[#D8CEBF]
                        flex items-center justify-center">
          <Ticket className="w-7 h-7 text-[#C8962A]" />
        </div>
        <div>
          <div className="text-xs font-mono text-[#C8962A] uppercase tracking-widest font-semibold">
            No Active Selection
          </div>
          <h2 className="font-editorial text-2xl font-bold text-[#15130F] mt-1">
            No Seats Selected
          </h2>
          <p className="text-sm text-[#4A453D] mt-2">
            Your checkout session has expired or no seats were selected.
            Please return to the seat map and make a selection.
          </p>
        </div>
        <button
          onClick={() => onNavigate('seats')}
          className="inline-flex items-center gap-2 px-5 py-3 bg-[#E8472B] hover:bg-[#C23A20]
                     text-white rounded text-sm font-semibold transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Seat Map
        </button>
      </div>
    );
  }

  // ── Render: Hold expired ─────────────────────────────────────────────────
  if (hold.isExpired && view !== 'confirmation') {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-5">
        <div className="w-14 h-14 mx-auto rounded-full bg-[#FCEBE8] border border-[#E8472B]/20
                        flex items-center justify-center">
          <Clock className="w-7 h-7 text-[#E8472B]" />
        </div>
        <div>
          <div className="text-xs font-mono text-[#E8472B] uppercase tracking-widest font-semibold">
            Hold Expired
          </div>
          <h2 className="font-editorial text-2xl font-bold text-[#15130F] mt-1">
            Your Seat Hold Has Expired
          </h2>
          <p className="text-sm text-[#4A453D] mt-2">
            The 120-second hold on your selected seats has expired and they have been
            released back to the pool. Please return to the seat map and reselect.
          </p>
        </div>
        <button
          onClick={() => onNavigate('seats')}
          className="inline-flex items-center gap-2 px-5 py-3 bg-[#E8472B] hover:bg-[#C23A20]
                     text-white rounded text-sm font-semibold transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Reselect Seats
        </button>
      </div>
    );
  }



  // ── Render: Main Checkout ────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back button and Hold release action */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <button
          onClick={() => onNavigate('seats')}
          className="text-xs font-mono text-[#706A61] hover:text-[#15130F] flex items-center
                     gap-1.5 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Seat Map
        </button>
        <button
          onClick={async () => {
            if (window.confirm('Release these held seats and return to seat map?')) {
              await releaseActiveHold(1, holdId);
              onNavigate('seats');
            }
          }}
          className="text-[11px] font-mono text-[#E8472B] hover:text-[#C23A20] hover:underline transition-colors"
        >
          Cancel & Release Hold
        </button>
      </div>

      {/* Urgent Expiring Alert Banner */}
      {!hold?.isExpired && holdSeconds !== null && holdSeconds <= 30 && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-5 p-4 bg-[#FCEBE8] border-2 border-[#E8472B] rounded-lg flex items-center justify-between gap-3 animate-pulse"
        >
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-[#E8472B] flex-shrink-0" />
            <div className="text-xs font-mono text-[#15130F]">
              <strong className="text-[#E8472B] uppercase">Seat hold expiring in {holdSeconds}s!</strong> Complete payment now before seats return to the stadium pool.
            </div>
          </div>
          <div className="font-editorial text-xl font-bold text-[#E8472B] tabular-nums">
            {formatCountdown(holdSeconds)}
          </div>
        </div>
      )}

      <div className="mb-5">
        <div className="text-xs font-mono text-[#E8472B] uppercase tracking-widest font-semibold">
          Secure Checkout
        </div>
        <h1 className="font-editorial text-2xl sm:text-3xl font-bold text-[#15130F] mt-0.5">
          Confirm & Pay
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

        {/* ── Left: Booking Summary ── */}
        <div className="lg:col-span-3 space-y-4">

          {/* Event header */}
          <div className="bg-[#15130F] text-[#F4EFE6] rounded-lg px-5 py-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-sm bg-[#E8472B] flex items-center justify-center flex-shrink-0">
              <Ticket className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-[10px] font-mono text-[#C8962A] uppercase tracking-widest">
                Order Summary
              </div>
              <div className="font-editorial text-base font-bold leading-tight">{EVENT_NAME}</div>
              <div className="text-[11px] font-mono text-[#A39C91] mt-0.5">
                {EVENT_VENUE} · {EVENT_DATE} · {EVENT_TIME}
              </div>
            </div>
          </div>

          {/* Seat list */}
          <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-[#D8CEBF] flex items-center justify-between">
              <div className="text-xs font-mono font-semibold text-[#15130F] uppercase tracking-widest">
                Selected Seats ({seats.length} / 6 max)
              </div>
              <div className="text-[10px] font-mono text-[#706A61]">ALL-OR-NOTHING HOLD</div>
            </div>

            <div className="divide-y divide-[#D8CEBF]">
              {seats.map((seat) => (
                <SeatRow key={seat.id} seat={seat} />
              ))}
            </div>

            {/* Totals footer */}
            <div className="px-4 py-4 bg-[#D8CEBF]/30 space-y-1.5">
              <div className="flex justify-between text-xs font-mono text-[#4A453D]">
                <span>{seats.length} ticket{seats.length !== 1 ? 's' : ''}</span>
                <span>{totalCents.toLocaleString()}¢</span>
              </div>
              <div className="flex justify-between font-semibold text-sm">
                <span className="font-mono text-[#15130F] uppercase tracking-widest text-xs">
                  Total Payable
                </span>
                <div className="text-right font-mono">
                  <div className="text-xs text-[#4A453D]">{totalCents.toLocaleString()} cents</div>
                  <div className="text-lg font-bold text-[#E8472B]">{formatRupees(totalCents)}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Authoritative pricing reference */}
          <div className="bg-[#F4EFE6] border border-[#D8CEBF] rounded px-4 py-3 font-mono text-xs
                          text-[#4A453D] space-y-1">
            <div className="font-semibold text-[#15130F] mb-1 text-[10px] uppercase tracking-widest">
              Authoritative Pricing
            </div>
            {[
              ['VIP',      '15,000¢', '₹150.00'],
              ['PREMIUM',  ' 7,500¢', ' ₹75.00'],
              ['STANDARD', ' 3,500¢', ' ₹35.00'],
            ].map(([tier, cents, rupees]) => (
              <div key={tier} className="flex gap-3">
                <span className="w-16 text-[#706A61]">{tier}</span>
                <span className="w-16">{cents}</span>
                <span className="text-[#E8472B]">{rupees}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: Hold + Payment ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Hold status */}
          <HoldStatusCard
            holdId={holdId}
            holdSeconds={holdSeconds}
            holdExpired={hold.isExpired}
            isMock={isMock}
          />

          {/* Payment panel */}
          <PaymentPanel
            paymentStatus={paymentStatus}
            paymentResult={paymentResult}
            isSubmitting={isSubmitting}
            isMock={isMock}
            setIsMock={setIsMock}
            simFailure={simFailure}
            setSimFailure={setSimFailure}
            simPending={simPending}
            setSimPending={setSimPending}
            holdExpired={hold.isExpired || holdSeconds === 0}
            totalCents={totalCents}
            onPay={handlePay}
            onRetry={handleRetry}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Seat Row ─────────────────────────────────────────────────────────────────
function SeatRow({ seat }) {
  const tierColor = seat.tier === 'VIP'
    ? 'text-[#E8472B]'
    : seat.tier === 'PREMIUM'
    ? 'text-[#C8962A]'
    : 'text-[#3F6B4F]';

  return (
    <div className="px-4 py-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className={`w-6 h-6 rounded-sm border flex items-center justify-center text-[9px]
                         font-mono font-bold ${
                           seat.tier === 'VIP'
                             ? 'bg-[#FCEBE8] border-[#E8472B] text-[#E8472B]'
                             : seat.tier === 'PREMIUM'
                             ? 'bg-[#F9F3E5] border-[#C8962A] text-[#C8962A]'
                             : 'bg-[#EAF1ED] border-[#3F6B4F] text-[#3F6B4F]'
                         }`}>
          {seat.row}
        </div>
        <div>
          <div className="text-sm font-mono font-semibold text-[#15130F]">
            Row {seat.row}, Seat {seat.number}
          </div>
          <div className={`text-[10px] font-mono ${tierColor}`}>
            {seat.tier} · {seat.section}
            {seat.is_accessible && ' · ♿'}
          </div>
        </div>
      </div>
      <div className="text-right font-mono">
        <div className="text-xs font-semibold text-[#15130F]">{formatRupees(seat.price_cents)}</div>
        <div className="text-[9px] text-[#706A61]">{seat.price_cents?.toLocaleString()}¢</div>
      </div>
    </div>
  );
}

// ─── Hold Status Card ─────────────────────────────────────────────────────────
function HoldStatusCard({ holdId, holdSeconds, holdExpired, isMock }) {
  const isExpiring = !holdExpired && holdSeconds !== null && holdSeconds <= 30;

  const statusColor = holdExpired
    ? 'border-[#E8472B]/30 bg-[#FCEBE8]'
    : isExpiring
    ? 'border-[#C8962A]/40 bg-[#F9F3E5]'
    : 'border-[#3F6B4F]/30 bg-[#EAF1ED]';

  const textColor = holdExpired
    ? 'text-[#E8472B]'
    : isExpiring
    ? 'text-[#C8962A]'
    : 'text-[#3F6B4F]';

  return (
    <div className={`border rounded-lg px-4 py-4 space-y-3 ${statusColor}`}>
      <div className="flex items-center justify-between">
        <div className={`text-[10px] font-mono uppercase tracking-widest font-semibold ${textColor}`}>
          {holdExpired ? '⚠ Hold Expired' : isExpiring ? '⚡ Expiring Soon' : '🔒 Hold Active'}
        </div>
        {isMock && (
          <span className="text-[9px] font-mono text-[#C8962A] bg-[#F9F3E5] border border-[#C8962A]/30
                           rounded px-1.5 py-0.5">
            SIM
          </span>
        )}
      </div>

      {!holdExpired && holdSeconds !== null && (
        <div className="text-center">
          <div className={`font-editorial text-4xl font-bold tabular-nums leading-none ${textColor}`}>
            {formatCountdown(holdSeconds)}
          </div>
          <div className="text-[10px] font-mono text-[#706A61] mt-1">
            {isMock ? '[SIMULATED] ' : ''}remaining of {HOLD_TTL_S}s hold
          </div>
        </div>
      )}

      {holdExpired && (
        <p className="text-xs font-mono text-[#C23A20]">
          Your seats have been released. Please reselect from the seat map.
        </p>
      )}

      <div className="font-mono text-[10px] text-[#706A61] space-y-0.5">
        <div className="flex justify-between">
          <span>HOLD ID</span>
          <span className="font-semibold truncate max-w-[120px]">
            {holdId?.substring(0, 18) || '—'}…
          </span>
        </div>
        <div className="flex justify-between">
          <span>TTL</span>
          <span>120 seconds (api-contract §6.1)</span>
        </div>
      </div>
    </div>
  );
}

// ─── Payment Panel ────────────────────────────────────────────────────────────
function PaymentPanel({
  paymentStatus, paymentResult, isSubmitting,
  isMock, setIsMock,
  simFailure, setSimFailure,
  simPending, setSimPending,
  holdExpired, totalCents,
  onPay, onRetry,
}) {
  const canPay = !holdExpired
    && paymentStatus !== PAYMENT_STATUS.PROCESSING
    && paymentStatus !== PAYMENT_STATUS.SUCCEEDED
    && !isSubmitting;

  return (
    <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg overflow-hidden">

      {/* Header */}
      <div className="px-4 py-3 border-b border-[#D8CEBF] flex items-center gap-2">
        <Lock className="w-3.5 h-3.5 text-[#3F6B4F]" />
        <span className="text-xs font-mono font-semibold text-[#15130F] uppercase tracking-widest">
          Payment
        </span>
      </div>

      <div className="p-4 space-y-4">

        {/* Payment method */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-mono text-[#706A61] uppercase tracking-widest">
            Payment Method
          </div>
          <div className="flex items-center gap-3 bg-[#F4EFE6] border border-[#D8CEBF] rounded
                          px-3 py-2.5">
            <CreditCard className="w-4 h-4 text-[#4A453D]" />
            <div className="flex-1">
              <div className="text-xs font-mono font-semibold text-[#15130F]">
                Simulated Card
              </div>
              <div className="text-[10px] font-mono text-[#706A61]">
                Backend payment simulator · No real charge
              </div>
            </div>
            <div className="w-2 h-2 rounded-full bg-[#3F6B4F]" />
          </div>
        </div>

        {/* Idempotency notice */}
        <div className="flex items-start gap-2 text-[10px] font-mono text-[#706A61]">
          <ShieldCheck className="w-3.5 h-3.5 mt-0.5 text-[#3F6B4F] flex-shrink-0" />
          <span>
            Idempotency key locked to this transaction.
            Safe to retry — no duplicate charges.
          </span>
        </div>

        {/* Pay button */}
        {paymentStatus === PAYMENT_STATUS.IDLE && (
          <button
            onClick={onPay}
            disabled={!canPay}
            className={`w-full flex items-center justify-center gap-2 px-5 py-3.5 rounded
                        font-semibold text-sm transition-colors ${
                          canPay
                            ? 'bg-[#E8472B] hover:bg-[#C23A20] text-white'
                            : 'bg-[#D8CEBF] text-[#A39C91] cursor-not-allowed'
                        }`}
          >
            <Lock className="w-4 h-4" />
            Pay {formatRupees(totalCents)} Now
          </button>
        )}

        {/* Processing */}
        {paymentStatus === PAYMENT_STATUS.PROCESSING && (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <RefreshCw className="w-8 h-8 text-[#E8472B] animate-spin" />
            <div>
              <div className="text-xs font-mono font-semibold text-[#15130F]">Processing Payment</div>
              <div className="text-[10px] font-mono text-[#706A61] mt-0.5">
                Do not close this tab or press back.
              </div>
            </div>
          </div>
        )}

        {/* Declined */}
        {paymentStatus === PAYMENT_STATUS.DECLINED && (
          <PaymentOutcome
            icon={<XCircle className="w-6 h-6 text-[#E8472B]" />}
            bg="bg-[#FCEBE8] border-[#E8472B]/30"
            label="Payment Declined"
            labelColor="text-[#E8472B]"
            message={paymentResult?.message || 'Your payment was declined. Hold is still active — you may retry.'}
            isMock={paymentResult?.is_mock}
            onRetry={onRetry}
            retryLabel="Try Again"
          />
        )}

        {/* Pending / Reconciliation View */}
        {paymentStatus === PAYMENT_STATUS.PENDING && (
          <PaymentOutcome
            icon={<Clock className="w-6 h-6 text-[#C8962A] animate-pulse" />}
            bg="bg-[#F9F3E5] border-2 border-[#C8962A]/60"
            label="Payment Captured · Booking Reconciliation Pending"
            labelColor="text-[#C8962A]"
            message={paymentResult?.error || paymentResult?.message || 'Payment has been authorized. Reconciling authoritative ticket booking reference with ticketing service. Do not initiate a new payment.'}
            isMock={paymentResult?.is_mock}
            onRetry={onPay}
            retryLabel={isSubmitting ? "Reconciling..." : "Check Booking Status"}
          />
        )}

        {/* Error */}
        {paymentStatus === PAYMENT_STATUS.ERROR && (
          <PaymentOutcome
            icon={<AlertCircle className="w-6 h-6 text-[#E8472B]" />}
            bg="bg-[#FCEBE8] border-[#E8472B]/30"
            label="Payment Error"
            labelColor="text-[#E8472B]"
            message={paymentResult?.error || 'An unexpected error occurred. The same idempotency key will be reused.'}
            isMock={false}
            onRetry={onRetry}
            retryLabel="Retry (Safe)"
          />
        )}

      </div>
    </div>
  );
}

function PaymentOutcome({ icon, bg, label, labelColor, message, isMock, onRetry, retryLabel }) {
  return (
    <div className={`border rounded p-4 space-y-3 ${bg}`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{icon}</div>
        <div>
          <div className={`text-[10px] font-mono uppercase tracking-widest font-semibold ${labelColor}`}>
            {label}
          </div>
          <p className="text-xs font-mono text-[#4A453D] mt-1">{message}</p>
          {isMock && (
            <div className="text-[9px] font-mono text-[#C8962A] mt-1">[DEV SIMULATION]</div>
          )}
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="w-full px-4 py-2 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded
                     text-xs font-mono font-semibold transition-colors"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

// ─── QR Code Generator (pure canvas, no library) ─────────────────────────────
function QRCodeCanvas({ data, size = 160 }) {
  const canvasRef = React.useRef(null);
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const cells = 21;
    const cellSize = size / cells;

    // Simple deterministic pattern from data string
    const hash = Array.from(data).reduce((acc, c) => ((acc << 5) - acc + c.charCodeAt(0)) | 0, 0);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, size, size);

    // Draw finder patterns (corners)
    const drawFinder = (x, y) => {
      ctx.fillStyle = '#15130F';
      ctx.fillRect(x * cellSize, y * cellSize, 7 * cellSize, 7 * cellSize);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect((x+1)*cellSize, (y+1)*cellSize, 5*cellSize, 5*cellSize);
      ctx.fillStyle = '#15130F';
      ctx.fillRect((x+2)*cellSize, (y+2)*cellSize, 3*cellSize, 3*cellSize);
    };
    drawFinder(0, 0); drawFinder(14, 0); drawFinder(0, 14);

    // Draw data cells from booking ref + hash
    for (let row = 0; row < cells; row++) {
      for (let col = 0; col < cells; col++) {
        // Skip finder pattern areas
        if ((row < 8 && col < 8) || (row < 8 && col >= 13) || (row >= 13 && col < 8)) continue;
        const idx = row * cells + col;
        const charCode = data.charCodeAt(idx % data.length) || 0;
        const bit = ((charCode ^ (hash >> (idx % 32))) & (1 << (idx % 8))) !== 0;
        if (bit) {
          ctx.fillStyle = '#15130F';
          ctx.fillRect(col * cellSize, row * cellSize, cellSize - 0.5, cellSize - 0.5);
        }
      }
    }
  }, [data, size]);
  return <canvas ref={canvasRef} width={size} height={size} className="rounded" />;
}

// ─── Ticket Download ──────────────────────────────────────────────────────────
function downloadTicket({ bookingRef, seats, totalCents, confirmedAt, eventName, eventVenue, eventDate, eventTime }) {
  const lines = [
    '╔══════════════════════════════════════════════════╗',
    '║           SEATSURGE — E-TICKET                   ║',
    '╠══════════════════════════════════════════════════╣',
    `║  EVENT:   ${eventName.padEnd(39)}║`,
    `║  VENUE:   ${eventVenue.padEnd(39)}║`,
    `║  DATE:    ${eventDate.padEnd(39)}║`,
    `║  TIME:    ${eventTime.padEnd(39)}║`,
    '╠══════════════════════════════════════════════════╣',
    `║  BOOKING: ${bookingRef.padEnd(39)}║`,
    `║  CONF AT: ${confirmedAt.padEnd(39)}║`,
    '╠══════════════════════════════════════════════════╣',
    '║  SEATS:                                          ║',
    ...seats.map(s => `║    Row ${s.row}, Seat ${s.number} [${s.tier}] — ₹${((s.price_cents||0)/100).toFixed(2)}`.padEnd(50) + '║'),
    '╠══════════════════════════════════════════════════╣',
    `║  TOTAL:   ₹${((totalCents)/100).toFixed(2).padEnd(38)}║`,
    '╠══════════════════════════════════════════════════╣',
    '║  Present this ticket at the gate for entry.      ║',
    '║  Valid for one-time use only.                    ║',
    '╚══════════════════════════════════════════════════╝',
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `SeatSurge-Ticket-${bookingRef}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Confirmation View ────────────────────────────────────────────────────────
function ConfirmationView({ paymentResult, seats, totalCents, onNavigate }) {
  const bookingRef  = paymentResult?.booking_id || ('SS-' + Date.now().toString(36).toUpperCase());
  const confirmedAt = paymentResult?.confirmed_at
    ? new Date(paymentResult.confirmed_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
    : new Date().toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });

  const qrData = `SEATSURGE|${bookingRef}|${EVENT_NAME}|${EVENT_DATE}|${seats.map(s=>`${s.row}${s.number}`).join(',')}`;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-5">

      {/* ── Success banner ── */}
      <div className="bg-[#EAF1ED] border border-[#3F6B4F]/40 rounded-xl px-6 py-7 text-center space-y-2">
        <div className="w-16 h-16 mx-auto rounded-full bg-[#3F6B4F] flex items-center justify-center shadow-lg">
          <CheckCircle className="w-9 h-9 text-white" />
        </div>
        <div className="text-[10px] font-mono text-[#3F6B4F] uppercase tracking-widest font-semibold">Booking Confirmed</div>
        <h1 className="font-editorial text-3xl font-bold text-[#15130F]">Enjoy the Show! 🎉</h1>
        <p className="text-sm text-[#4A453D]">Your tickets are secured. Show the QR code at the gate.</p>
      </div>

      {/* ── Ticket Card ── */}
      <div className="bg-white border-2 border-[#15130F] rounded-xl overflow-hidden shadow-lg">
        {/* Ticket header */}
        <div className="bg-[#15130F] text-[#F4EFE6] px-5 py-4 flex items-center gap-3">
          <Ticket className="w-6 h-6 text-[#E8472B]" />
          <div>
            <div className="text-[10px] font-mono text-[#C8962A] uppercase tracking-widest">Digital Entry Pass</div>
            <div className="font-editorial text-lg font-bold">{EVENT_NAME}</div>
            <div className="text-xs font-mono text-[#A39C91]">{EVENT_VENUE} · {EVENT_DATE} · {EVENT_TIME}</div>
          </div>
        </div>

        {/* QR + details row */}
        <div className="flex flex-col sm:flex-row gap-0 divide-y sm:divide-y-0 sm:divide-x divide-[#E8E2D9]">
          {/* QR Code */}
          <div className="flex flex-col items-center justify-center p-6 gap-3 bg-[#FAFAF8] min-w-[200px]">
            <QRCodeCanvas data={qrData} size={160} />
            <div className="text-[10px] font-mono text-[#706A61] text-center leading-relaxed">
              Scan at gate for entry<br/>
              <span className="text-[#E8472B] font-semibold">{bookingRef}</span>
            </div>
          </div>

          {/* Seat details */}
          <div className="flex-1 p-5 space-y-4">
            <div>
              <div className="text-[10px] font-mono text-[#706A61] uppercase tracking-widest mb-2">Your Seats</div>
              <div className="space-y-2">
                {seats.map((seat, i) => (
                  <div key={seat.id ?? i} className="flex items-center justify-between bg-[#F4EFE6] rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-7 h-7 rounded flex items-center justify-center text-[9px] font-mono font-bold ${
                        seat.tier === 'VIP' ? 'bg-[#E8472B] text-white' :
                        seat.tier === 'PREMIUM' ? 'bg-[#C8962A] text-white' : 'bg-[#3F6B4F] text-white'
                      }`}>{seat.row}</div>
                      <div>
                        <div className="text-xs font-mono font-semibold text-[#15130F]">Row {seat.row} · Seat {seat.number}</div>
                        <div className="text-[10px] font-mono text-[#706A61]">{seat.section || seat.tier} · {seat.tier}</div>
                      </div>
                    </div>
                    <div className="text-sm font-mono font-bold text-[#E8472B]">{formatRupees(seat.price_cents)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-[#E8E2D9]">
              <span className="text-xs font-mono font-semibold text-[#15130F] uppercase tracking-widest">Total Paid</span>
              <span className="text-xl font-bold text-[#E8472B] font-mono">{formatRupees(totalCents)}</span>
            </div>

            <div className="text-[10px] font-mono text-[#706A61] space-y-0.5">
              <div>Confirmed: {confirmedAt}</div>
              <div>Ref: <span className="text-[#15130F] font-semibold">{bookingRef}</span></div>
            </div>
          </div>
        </div>

        {/* Perforated divider */}
        <div className="border-t-2 border-dashed border-[#D8CEBF] mx-4" />

        {/* Ticket footer */}
        <div className="px-5 py-3 bg-[#F4EFE6] flex items-center justify-between">
          <div className="text-[10px] font-mono text-[#706A61]">Valid for one-time entry · Non-transferable</div>
          <ShieldCheck className="w-4 h-4 text-[#3F6B4F]" />
        </div>
      </div>

      {/* ── Action buttons ── */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={() => downloadTicket({ bookingRef, seats, totalCents, confirmedAt, eventName: EVENT_NAME, eventVenue: EVENT_VENUE, eventDate: EVENT_DATE, eventTime: EVENT_TIME })}
          className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-[#E8472B] hover:bg-[#C23A20]
                     text-white rounded-lg text-sm font-semibold transition-colors"
        >
          <Printer className="w-4 h-4" /> Download Ticket
        </button>
        <button
          onClick={() => onNavigate('seats')}
          className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-[#3F6B4F] hover:bg-[#345841]
                     text-white rounded-lg text-sm font-semibold transition-colors"
        >
          <Ticket className="w-4 h-4" /> Book More Tickets
        </button>
        <button
          onClick={() => onNavigate('landing')}
          className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-[#15130F]
                     hover:bg-[#2A2620] text-[#F4EFE6] rounded-lg text-sm font-semibold transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Go Back
        </button>
      </div>
    </div>
  );
}
