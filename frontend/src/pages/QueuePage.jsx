/**
 * SeatSurge — Virtual Waiting Room (Phase F3)
 *
 * Supports 7 UI states: NOT_JOINED · WAITING · ADMITTED · EXPIRED · CANCELLED · ERROR · RECONNECTING
 * Mock adapter is clearly labelled [DEV SIMULATION].
 * Design adapter: replace joinQueueMock/pollQueueMock with Real adapter in F5 without
 * changing this component.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Users, Clock, CheckCircle, AlertCircle, RefreshCw, XCircle,
  ArrowRight, Wifi, WifiOff, Info, Shield, Ticket, ChevronRight,
  Hourglass, AlertTriangle,
} from 'lucide-react';
import {
  QUEUE_STATUS,
  MOCK_POLL_INTERVAL_MS,
  getStoredQueueSession,
  clearQueueSession,
  joinQueueMock,
  pollQueueMock,
  joinQueueReal,
  pollQueueReal,
} from '../services/queueService';
import { PRIMARY_EVENT } from '../services/eventService';

// ─── Event display constants (match eventService.js PRIMARY_EVENT) ─────────────
const EVENT_NAME   = PRIMARY_EVENT?.title || 'YUKTIK 2026 Grand Concert';
const EVENT_VENUE  = PRIMARY_EVENT?.venue?.name || 'Surge Arena, Motera';
const EVENT_DATE   = PRIMARY_EVENT?.dateFormatted || 'Saturday, November 28, 2026';
const EVENT_TIME   = PRIMARY_EVENT?.time || '19:30 IST';
const EVENT_ID     = PRIMARY_EVENT?.id || 1;

// ─── Main Component ────────────────────────────────────────────────────────────
export default function QueuePage({ onNavigate }) {
  const [status,         setStatus]         = useState(QUEUE_STATUS.NOT_JOINED);
  const [session,        setSession]         = useState(null);
  const [isMock,         setIsMock]          = useState(true);
  const [isJoining,      setIsJoining]       = useState(false);
  const [error,          setError]           = useState(null);
  const [reconnectCount, setReconnectCount]  = useState(0);

  // Ref to latest session so polling closure never reads stale state
  const sessionRef   = useRef(null);
  const pollTimerRef = useRef(null);
  const isPollingRef = useRef(false);

  // ── Restore persisted session on mount ────────────────────────────────────
  useEffect(() => {
    const stored = getStoredQueueSession();
    if (stored) {
      sessionRef.current = stored;
      setSession(stored);
      setStatus(stored.status);
      setIsMock(stored.is_mock ?? true);

      if (stored.status === QUEUE_STATUS.WAITING) {
        startPolling(stored.is_mock ?? true);
      }
    }
    return () => stopPolling();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Polling ───────────────────────────────────────────────────────────────
  function stopPolling() {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    isPollingRef.current = false;
  }

  function startPolling(mockMode = true) {
    if (isPollingRef.current) return;
    isPollingRef.current = true;

    pollTimerRef.current = setInterval(async () => {
      if (!isPollingRef.current) return;

      try {
        const current = sessionRef.current;
        const result  = mockMode
          ? await pollQueueMock(current)
          : await pollQueueReal(EVENT_ID);

        sessionRef.current = result;
        setSession(result);
        setStatus(result.status);
        setReconnectCount(0);
        setError(null);

        if (
          result.status === QUEUE_STATUS.ADMITTED  ||
          result.status === QUEUE_STATUS.EXPIRED   ||
          result.status === QUEUE_STATUS.CANCELLED
        ) {
          stopPolling();
        }
      } catch (err) {
        setReconnectCount(prev => {
          const next = prev + 1;
          if (next >= 3) {
            setStatus(QUEUE_STATUS.ERROR);
            setError(err?.message || 'Connection lost after 3 attempts.');
            stopPolling();
          } else {
            setStatus(QUEUE_STATUS.RECONNECTING);
          }
          return next;
        });
      }
    }, MOCK_POLL_INTERVAL_MS);
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  const handleJoin = useCallback(async (useMock = true) => {
    setIsJoining(true);
    setError(null);
    try {
      const result = useMock
        ? await joinQueueMock(EVENT_ID)
        : await joinQueueReal(EVENT_ID);

      sessionRef.current = result;
      setSession(result);
      setStatus(result.status);
      setIsMock(result.is_mock ?? useMock);
      setReconnectCount(0);
      startPolling(result.is_mock ?? useMock);
    } catch (err) {
      setError(err?.message || 'Failed to join queue. Please try again.');
      setStatus(QUEUE_STATUS.ERROR);
    } finally {
      setIsJoining(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleLeave = useCallback(() => {
    stopPolling();
    clearQueueSession();
    sessionRef.current = null;
    setSession(null);
    setStatus(QUEUE_STATUS.CANCELLED);
    setError(null);
  }, []);

  const handleReconnect = useCallback(async () => {
    stopPolling();
    setStatus(QUEUE_STATUS.RECONNECTING);
    setReconnectCount(0);
    try {
      const result = isMock
        ? await joinQueueMock(EVENT_ID)
        : await joinQueueReal(EVENT_ID);
      sessionRef.current = result;
      setSession(result);
      setStatus(result.status);
      setError(null);
      startPolling(result.is_mock ?? isMock);
    } catch (err) {
      setError(err?.message || 'Reconnection failed.');
      setStatus(QUEUE_STATUS.ERROR);
    }
  }, [isMock]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRetryFresh = useCallback(() => {
    stopPolling();
    clearQueueSession();
    sessionRef.current = null;
    setSession(null);
    setStatus(QUEUE_STATUS.NOT_JOINED);
    setError(null);
    setReconnectCount(0);
  }, []);

  const handleProceedToSeats = useCallback(() => {
    onNavigate('seats');
  }, [onNavigate]);

  // ── Progress % ───────────────────────────────────────────────────────────
  const progressPercent = (() => {
    if (!session || status !== QUEUE_STATUS.WAITING) return 0;
    const initial = session.initial_position || session.queue_position;
    if (!initial || initial <= 0) return 0;
    const done = initial - session.queue_position;
    return Math.min(99, Math.max(0, Math.round((done / initial) * 100)));
  })();

  const fmtWait = (secs) => {
    if (!secs || secs <= 0) return 'Almost there…';
    if (secs < 60) return `~${secs}s`;
    return `~${Math.ceil(secs / 60)}m`;
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-5">

      {/* ── Event Identity Header ── */}
      <div className="bg-[#15130F] text-[#F4EFE6] rounded-lg px-5 py-5 flex items-start gap-4">
        <div className="flex-shrink-0 w-11 h-11 rounded-sm bg-[#E8472B] flex items-center justify-center">
          <Ticket className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono text-[#C8962A] uppercase tracking-widest mb-0.5">
            Flash Sale · YUKTIK 2026
          </div>
          <h1 className="font-editorial text-xl sm:text-2xl font-bold leading-tight truncate">
            {EVENT_NAME}
          </h1>
          <div className="text-[11px] font-mono text-[#A39C91] mt-1 space-y-0.5">
            <div>{EVENT_VENUE}</div>
            <div>{EVENT_DATE} · {EVENT_TIME}</div>
          </div>
        </div>
      </div>

      {/* ── Dev simulation notice ── */}
      {isMock && status !== QUEUE_STATUS.NOT_JOINED && (
        <div className="flex items-start gap-2 px-3 py-2 bg-[#F9F3E5] border border-[#C8962A]/40 rounded text-xs font-mono text-[#9E741B]">
          <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-[#C8962A]" />
          <span>
            <strong>[DEV SIMULATION]</strong> Queue position and admission are synthesised locally.
            No real FIFO ordering, Redis Sorted Set or backend admission control is active.
          </span>
        </div>
      )}

      {/* ── State Views ── */}
      {status === QUEUE_STATUS.NOT_JOINED && (
        <NotJoinedView onJoinMock={() => handleJoin(true)} onJoinReal={() => handleJoin(false)}
          isJoining={isJoining} error={error} />
      )}

      {status === QUEUE_STATUS.WAITING && session && (
        <WaitingView session={session} progressPercent={progressPercent}
          fmtWait={fmtWait} isMock={isMock} onLeave={handleLeave} />
      )}

      {status === QUEUE_STATUS.ADMITTED && (
        <AdmittedView session={session} isMock={isMock} onProceed={handleProceedToSeats} />
      )}

      {status === QUEUE_STATUS.EXPIRED && (
        <StatusMessageView
          icon={<Clock className="w-6 h-6 text-[#E8472B]" />}
          iconBg="bg-[#FCEBE8] border border-[#E8472B]/20"
          label="Session Expired"
          labelColor="text-[#E8472B]"
          heading="Queue Session Timed Out"
          body="Your waiting room session has expired. You will need to rejoin the queue."
          primary={{ label: 'Rejoin Queue', icon: <RefreshCw className="w-4 h-4" />, action: handleRetryFresh }}
          secondary={{ label: 'Back to Event', action: () => onNavigate('landing') }}
        />
      )}

      {status === QUEUE_STATUS.CANCELLED && (
        <StatusMessageView
          icon={<XCircle className="w-6 h-6 text-[#4A453D]" />}
          iconBg="bg-[#EAE3D6] border border-[#D8CEBF]"
          label="Left Queue"
          labelColor="text-[#706A61]"
          heading="You've Left the Queue"
          body="Your queue position has been released. You can rejoin at any time."
          primary={{ label: 'Rejoin Queue', icon: <Users className="w-4 h-4" />, action: handleRetryFresh }}
          secondary={{ label: 'Back to Event', action: () => onNavigate('landing') }}
        />
      )}

      {status === QUEUE_STATUS.RECONNECTING && (
        <div className="bg-[#F9F3E5] border border-[#C8962A]/40 rounded-lg p-7 text-center space-y-3">
          <RefreshCw className="w-8 h-8 mx-auto text-[#C8962A] animate-spin" />
          <div>
            <div className="text-xs font-mono text-[#C8962A] uppercase tracking-widest font-semibold">
              Reconnecting ({reconnectCount}/3)
            </div>
            <p className="text-sm text-[#4A453D] mt-1">
              Attempting to restore queue connection…
            </p>
          </div>
        </div>
      )}

      {status === QUEUE_STATUS.ERROR && (
        <ErrorView error={error} onReconnect={handleReconnect} onRetry={handleRetryFresh} />
      )}

      {/* ── API Contract Card (always shown at bottom) ── */}
      {status === QUEUE_STATUS.NOT_JOINED && <ApiContractCard />}

    </div>
  );
}

// ─── Sub-views ─────────────────────────────────────────────────────────────────

function NotJoinedView({ onJoinMock, onJoinReal, isJoining, error }) {
  return (
    <div className="space-y-4">
      <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-[#F4EFE6] border border-[#D8CEBF] flex items-center justify-center">
            <Users className="w-5 h-5 text-[#E8472B]" />
          </div>
          <div>
            <h2 className="font-editorial text-xl font-bold text-[#15130F]">Virtual Waiting Room</h2>
            <p className="text-[11px] font-mono text-[#706A61]">Fair queue · First-come, first-served</p>
          </div>
        </div>

        <p className="text-sm text-[#4A453D]">
          Due to high demand, all users enter a virtual waiting room before accessing the seat
          map. Your position is preserved even if you switch tabs.
        </p>

        <ul className="space-y-1.5">
          {[
            'Your position is permanent — do not refresh.',
            'Once admitted, you have 10 minutes to complete your booking.',
            'Each browser session holds exactly one queue position.',
            'Scalper-bot requests are blocked before queue entry.',
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-xs font-mono text-[#4A453D]">
              <ChevronRight className="w-3.5 h-3.5 mt-0.5 text-[#E8472B] flex-shrink-0" />
              {item}
            </li>
          ))}
        </ul>

        <div className="flex flex-col sm:flex-row gap-3 pt-1">
          <button
            onClick={onJoinMock}
            disabled={isJoining}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-[#E8472B] hover:bg-[#C23A20]
                       disabled:opacity-60 disabled:cursor-not-allowed text-white rounded text-sm
                       font-semibold transition-colors"
          >
            {isJoining
              ? <><RefreshCw className="w-4 h-4 animate-spin" /> Joining Queue…</>
              : <><Users className="w-4 h-4" /> Join Waiting Room</>
            }
          </button>
          <button
            onClick={onJoinReal}
            disabled={isJoining}
            title="Requires backend NGINX + instances running"
            className="flex items-center justify-center gap-2 px-4 py-3 bg-[#15130F] hover:bg-[#2A2620]
                       disabled:opacity-60 text-[#F4EFE6] rounded text-xs font-mono transition-colors"
          >
            <Wifi className="w-3.5 h-3.5" /> Try Live Backend
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-3 py-2.5 bg-[#FCEBE8] border border-[#E8472B]/30
                        rounded text-xs font-mono text-[#C23A20]">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}

function WaitingView({ session, progressPercent, fmtWait, isMock, onLeave }) {
  return (
    <div className="space-y-4">

      {/* Position + wait card */}
      <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono text-[#706A61] uppercase tracking-widest">Your Position</div>
            <div className="font-editorial text-5xl font-bold text-[#E8472B] leading-none mt-1">
              #{session.queue_position}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-mono text-[#706A61] uppercase tracking-widest">Est. Wait</div>
            <div className="font-editorial text-2xl font-bold text-[#15130F] mt-1">
              {fmtWait(session.estimated_wait_seconds)}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-mono text-[#706A61]">
            <span>QUEUE PROGRESS</span>
            <span>{progressPercent}% AHEAD</span>
          </div>
          <div className="h-2 bg-[#C8B89A] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#E8472B] rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Live pulse */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#4A453D]">
          <span className="flex gap-1">
            {[0, 150, 300].map(delay => (
              <span
                key={delay}
                className="w-1.5 h-1.5 rounded-full bg-[#E8472B] animate-pulse"
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
          </span>
          <span>Monitoring queue</span>
          {isMock && <span className="text-[#C8962A] font-semibold">(simulated)</span>}
        </div>
      </div>

      {/* Hold-your-spot notice */}
      <div className="bg-[#EAF1ED] border border-[#3F6B4F]/30 rounded px-4 py-3 flex items-start gap-2.5">
        <Shield className="w-4 h-4 text-[#3F6B4F] flex-shrink-0 mt-0.5" />
        <div className="text-xs font-mono text-[#2F503B]">
          <span className="font-semibold">Your spot is safe.</span>{' '}
          Position is saved to this browser — switching tabs or minimising will not reset it.
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'USERS AHEAD',   value: session.queue_position.toLocaleString() },
          { label: 'TOTAL SEATS',   value: '5,040' },
          { label: 'SESSION',       value: (session.session_id || '').substring(0, 6) + '…' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-[#EAE3D6] border border-[#D8CEBF] rounded px-3 py-2.5 text-center">
            <div className="text-[9px] font-mono text-[#706A61] uppercase tracking-widest leading-none">{label}</div>
            <div className="text-sm font-bold text-[#15130F] mt-1 font-mono">{value}</div>
          </div>
        ))}
      </div>

      <button
        onClick={onLeave}
        className="text-xs font-mono text-[#706A61] hover:text-[#E8472B] flex items-center
                   gap-1.5 transition-colors pt-1"
      >
        <XCircle className="w-3.5 h-3.5" />
        Leave queue and return to event details
      </button>
    </div>
  );
}

function AdmittedView({ session, isMock, onProceed }) {
  return (
    <div className="bg-[#EAF1ED] border border-[#3F6B4F]/40 rounded-lg p-7 space-y-5">
      <div className="text-center space-y-3">
        <div className="w-16 h-16 mx-auto rounded-full bg-[#3F6B4F] flex items-center justify-center shadow-md">
          <CheckCircle className="w-8 h-8 text-white" />
        </div>
        <div>
          <div className="text-[10px] font-mono text-[#3F6B4F] uppercase tracking-widest font-semibold">
            Admission Granted
          </div>
          <h2 className="font-editorial text-2xl font-bold text-[#15130F] mt-1">You're In!</h2>
          <p className="text-sm text-[#4A453D] mt-1">
            Your virtual admission is confirmed. Proceed to the seat map now to select your seats.
          </p>
        </div>
      </div>

      {isMock && (
        <div className="text-[10px] font-mono text-[#9E741B] bg-[#F9F3E5] border border-[#C8962A]/30
                        rounded px-3 py-1.5 text-center">
          [DEV SIMULATION] · Admission token generated locally · No real backend queue cleared
        </div>
      )}

      <div className="bg-[#F4EFE6] border border-[#D8CEBF] rounded px-4 py-3 space-y-2 font-mono text-xs text-[#4A453D]">
        {[
          ['SESSION',          (session?.session_id || '').substring(0, 8) + '…'],
          ['ADMISSION TOKEN',  <span className="text-[#3F6B4F] font-semibold">ISSUED (SECURE)</span>],
          ['TOKEN SCOPE',      'Seat hold API · Single-use'],
          ['EXPIRES',          '10 minutes from admission'],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4">
            <span className="text-[#706A61]">{k}</span>
            <span>{v}</span>
          </div>
        ))}
      </div>

      <button
        onClick={onProceed}
        className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-[#E8472B]
                   hover:bg-[#C23A20] text-white rounded text-sm font-semibold transition-colors"
      >
        Select Your Seats <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}

function StatusMessageView({ icon, iconBg, label, labelColor, heading, body, primary, secondary }) {
  return (
    <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-7 text-center space-y-5">
      <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center ${iconBg}`}>
        {icon}
      </div>
      <div>
        <div className={`text-[10px] font-mono uppercase tracking-widest font-semibold ${labelColor}`}>
          {label}
        </div>
        <h2 className="font-editorial text-xl font-bold text-[#15130F] mt-1">{heading}</h2>
        <p className="text-sm text-[#4A453D] mt-1 max-w-sm mx-auto">{body}</p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <button
          onClick={primary.action}
          className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[#E8472B] hover:bg-[#C23A20]
                     text-white rounded text-sm font-semibold transition-colors"
        >
          {primary.icon} {primary.label}
        </button>
        {secondary && (
          <button
            onClick={secondary.action}
            className="px-5 py-2.5 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded
                       text-xs font-mono transition-colors"
          >
            {secondary.label}
          </button>
        )}
      </div>
    </div>
  );
}

function ErrorView({ error, onReconnect, onRetry }) {
  return (
    <div className="bg-[#FCEBE8] border border-[#E8472B]/30 rounded-lg p-6 space-y-4">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-[#E8472B]/10 border border-[#E8472B]/20
                        flex items-center justify-center flex-shrink-0">
          <WifiOff className="w-5 h-5 text-[#E8472B]" />
        </div>
        <div className="min-w-0">
          <div className="text-[10px] font-mono text-[#E8472B] uppercase tracking-widest font-semibold">
            Connection Error
          </div>
          <h2 className="font-editorial text-lg font-bold text-[#15130F] mt-0.5">
            Queue Connection Failed
          </h2>
          {error && (
            <p className="text-xs font-mono text-[#C23A20] mt-1 break-words">{error}</p>
          )}
        </div>
      </div>
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={onReconnect}
          className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[#E8472B] hover:bg-[#C23A20]
                     text-white rounded text-sm font-semibold transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Reconnect
        </button>
        <button
          onClick={onRetry}
          className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[#15130F] hover:bg-[#2A2620]
                     text-[#F4EFE6] rounded text-xs font-mono transition-colors"
        >
          Start Fresh
        </button>
      </div>
    </div>
  );
}

function ApiContractCard() {
  return (
    <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-4 font-mono text-xs space-y-2.5">
      <div className="text-[#706A61] uppercase tracking-widest font-semibold text-[10px]">
        Backend Integration Target — Phase F5
      </div>
      <div className="space-y-1.5 text-[#4A453D]">
        {[
          ['ENDPOINT',         'POST /api/v1/queue/enter'],
          ['ALGORITHM',        'Redis Sorted Set (FIFO)'],
          ['SESSION HEADER',   'X-Session-ID: <uuid>'],
          ['ADMISSION TOKEN',  'sessionStorage only — never rendered'],
          ['BOT SCREENING',    'AI-based detection (server-side)'],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 border-b border-[#D8CEBF]/60 pb-1 last:border-0 last:pb-0">
            <span className="text-[#706A61] flex-shrink-0">{k}</span>
            <span className="font-semibold text-right">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
