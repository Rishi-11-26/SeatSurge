import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import SeatMapHeader from '../components/seats/SeatMapHeader';
import SectionGrid from '../components/seats/SectionGrid';
import SelectedSeatsSummary from '../components/seats/SelectedSeatsSummary';
import GroupSelectModal from '../components/seats/GroupSelectModal';
import { loadSeatMap, validateGroupAdjacency } from '../services/seatService';
import { createSeatHold } from '../services/api';
import { getAdmissionToken } from '../services/queueService';
import { websocketService, WS_STATUS } from '../services/websocketService';
import { AlertCircle, CheckCircle, RefreshCw, AlertTriangle, ShieldCheck, Wifi, WifiOff } from 'lucide-react';

export default function SeatsPage({ onNavigate }) {
  const [seats, setSeats] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [wsStatus, setWsStatus] = useState(WS_STATUS.DISCONNECTED);
  const [activeSection, setActiveSection] = useState('VIP'); // Fast initial section view
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [selectedSeatIds, setSelectedSeatIds] = useState([]);
  
  // Group selection modal state
  const [groupModalSeat, setGroupModalSeat] = useState(null);
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);

  // Notifications and Simulation State
  const [notification, setNotification] = useState(null);
  const [isHolding, setIsHolding] = useState(false);
  const [useSimulationFallback, setUseSimulationFallback] = useState(false);
  const [simulateRaceCondition, setSimulateRaceCondition] = useState(false);

  // Fast seat map lookup map by ID
  const seatLookup = useMemo(() => {
    const map = new Map();
    for (const seat of seats) {
      map.set(seat.id, seat);
    }
    return map;
  }, [seats]);

  // Load seats from REST endpoint
  const fetchSeats = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await loadSeatMap(1, { mode: useSimulationFallback ? 'mock' : 'auto' });
      setSeats(result.seats);
      setIsLive(result.isLive);

      if (typeof result.sequenceNumber === 'number') {
        websocketService.resetSeq(result.sequenceNumber);
      }

      if (result.backendOffline) {
        setNotification({
          type: 'warning',
          message: 'Backend API offline at http://localhost:8000. Loaded authoritative local 5,040 stadium layout.',
        });
      }
    } catch (err) {
      console.error('Failed to load seat map', err);
      setNotification({
        type: 'error',
        message: `Failed to load live seat map: ${err.message}`,
      });
    } finally {
      setIsLoading(false);
    }
  }, [useSimulationFallback]);

  // Initial load and WebSocket setup
  useEffect(() => {
    fetchSeats();

    // Connect to Real-Time WebSocket fanout per api-contract.md §8
    websocketService.connect(1);

    const unsubStatus = websocketService.onStatusChange(status => {
      setWsStatus(status);
    });

    // Handle incoming incremental seat state changes
    const unsubUpdates = websocketService.subscribe(({ updates }) => {
      if (!updates || updates.length === 0) return;

      const updateMap = new Map();
      for (const u of updates) {
        updateMap.set(u.seat_id, u.status);
      }

      // Immutable state update: preserves identical object references for unchanged seats
      // React.memo on SeatCell skips rendering all 5,039 unaffected seats!
      setSeats(prev => {
        let hasChanges = false;
        const nextSeats = prev.map(seat => {
          const nextStatus = updateMap.get(seat.id);
          if (nextStatus && nextStatus !== seat.status) {
            hasChanges = true;
            return { ...seat, status: nextStatus };
          }
          return seat; // Exact reference preserved
        });

        // If duplicate event or no status actually changed, bail out of re-render
        return hasChanges ? nextSeats : prev;
      });

      // Deselect any selected seat that is now claimed (HELD / SOLD) by another user
      setSelectedSeatIds(prevSelected => {
        const remaining = prevSelected.filter(id => {
          const status = updateMap.get(id);
          return !status || status === 'AVAILABLE';
        });

        if (remaining.length < prevSelected.length) {
          setNotification({
            type: 'warning',
            message: 'A seat in your selection was just claimed by another user.',
          });
        }
        return remaining;
      });
    });

    // Handle full snapshot message received over WebSocket
    const unsubSnapshot = websocketService.onSnapshot((data) => {
      if (data && Array.isArray(data.seats)) {
        const normalized = data.seats.map(s => ({
          ...s,
          id: s.seat_id ?? s.id,
          seat_id: s.seat_id ?? s.id,
        }));
        setSeats(normalized);
        setNotification({
          type: 'success',
          message: `Seat map resynchronized via real-time WebSocket snapshot (seq ${data.seq || 0}).`,
        });
      }
    });

    // Handle sequence gap: trigger full snapshot fetch
    const unsubGap = websocketService.onGap((lastSeq, newSeq) => {
      setNotification({
        type: 'warning',
        message: `WebSocket gap detected (${lastSeq} → ${newSeq}). Refreshing seat map snapshot...`,
      });
      fetchSeats();
    });

    return () => {
      unsubStatus();
      unsubUpdates();
      unsubSnapshot();
      unsubGap();
      websocketService.disconnect();
    };
  }, [fetchSeats]);

  // Memoized seat selection handler to prevent unnecessary full-map re-renders
  const handleSelectSeat = useCallback((seat) => {
    setSelectedSeatIds(prev => {
      // 1. If already selected, deselect it
      if (prev.includes(seat.id)) {
        const next = prev.filter(id => id !== seat.id);
        setNotification(null);
        return next;
      }

      // 2. Reject if already at the 6-seat cap
      if (prev.length >= 6) {
        setNotification({
          type: 'error',
          message: 'Maximum 6 seats allowed per booking. Remove a seat before adding another.',
        });
        return prev;
      }

      // 3. Check adjacency
      const currentSelectedSeats = prev.map(id => seatLookup.get(id)).filter(Boolean);
      const candidateSeats = [...currentSelectedSeats, seat];
      const adjacency = validateGroupAdjacency(candidateSeats);

      if (!adjacency.valid && candidateSeats.length > 1) {
        setNotification({
          type: 'warning',
          message: adjacency.error,
        });
      } else {
        setNotification(null);
      }

      return [...prev, seat.id];
    });
  }, [seatLookup]);

  // Open group select modal
  const handleOpenGroupSelect = useCallback((seat) => {
    setGroupModalSeat(seat);
    setIsGroupModalOpen(true);
  }, []);

  // Apply group selection
  const handleApplyGroup = useCallback((contiguousSeats) => {
    if (!contiguousSeats || contiguousSeats.length === 0) return;
    const newIds = contiguousSeats.map(s => s.id);
    setSelectedSeatIds(newIds);
    setNotification({
      type: 'success',
      message: `Selected ${contiguousSeats.length} continuous adjacent seats in Row ${contiguousSeats[0].row}.`,
    });
  }, []);

  const handleRemoveSeat = useCallback((seatId) => {
    setSelectedSeatIds(prev => prev.filter(id => id !== seatId));
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedSeatIds([]);
    setNotification(null);
  }, []);

  // Hold & Checkout Flow (Real Backend POST /api/v1/events/1/holds with dev simulation fallback)
  const handleProceedToHold = async () => {
    const selected = selectedSeatIds.map(id => seatLookup.get(id)).filter(Boolean);
    if (selected.length === 0) return;

    setIsHolding(true);
    setNotification(null);

    // 1. If simulated race condition is explicitly checked
    if (simulateRaceCondition) {
      await new Promise(r => setTimeout(r, 600)); // simulated latency
      const conflictSeat = selected[0];
      
      // Optimistic rollback: mark conflicting seat as HELD and deselect
      setSeats(prev => prev.map(s => s.id === conflictSeat.id ? { ...s, status: 'HELD' } : s));
      setSelectedSeatIds([]);
      
      setNotification({
        type: 'error',
        message: `Hold Rejected (Development Simulation): Seat Row ${conflictSeat.row}-${conflictSeat.number} was claimed by another session. Selection rolled back.`,
      });
      setIsHolding(false);
      return;
    }

    try {
      const admissionToken = getAdmissionToken(); // sessionStorage via queueService
      let holdData = null;

      if (!useSimulationFallback) {
        // Strict Real Backend Mode: Call POST /api/v1/events/1/holds
        try {
          holdData = await createSeatHold({
            eventId: 1,
            seatIds: selected.map(s => s.id),
            admissionToken,
          });
        } catch (apiErr) {
          // Check for 409 Conflict (Seats already taken by another user)
          if (apiErr.status === 409 || apiErr.code === 'CONFLICT' || apiErr.code === 'SEATS_UNAVAILABLE') {
            const conflictSeatIds = apiErr.details?.conflicting_seats || [selected[0].id];
            setSeats(prev => prev.map(s => conflictSeatIds.includes(s.id) ? { ...s, status: 'HELD' } : s));
            setSelectedSeatIds(prev => prev.filter(id => !conflictSeatIds.includes(id)));
            setNotification({
              type: 'error',
              message: `Hold Conflict (409): One or more selected seats were already claimed by another session. Refreshed seat status.`,
            });
            setIsHolding(false);
            return;
          }

          // Backend hold endpoint not available or returned 404 (Phase 2 pending)
          throw apiErr;
        }
      } else {
        // Explicit Development Simulation Mode
        await new Promise(r => setTimeout(r, 400));
        holdData = {
          hold_id: 'hld_sim_' + Math.random().toString(36).substring(2, 10),
          event_id: 1,
          seat_ids: selected.map(s => s.id),
          time_remaining_seconds: 120,
          expires_at: new Date(Date.now() + 120000).toISOString(),
          is_mock: true,
        };
      }

      // Store hold in localStorage for checkout
      localStorage.setItem('seatsurge_active_hold', JSON.stringify({
        ...holdData,
        seats: selected,
        heldAt: Date.now(),
      }));

      // Optimistically update map to HELD for these seats
      setSeats(prev => prev.map(s => selectedSeatIds.includes(s.id) ? { ...s, status: 'HELD' } : s));

      // Transition to Checkout
      onNavigate('checkout');
    } catch (err) {
      console.warn('Real hold attempt failed:', err);
      setNotification({
        type: 'error',
        message: err.code === 'NETWORK_GATEWAY_UNAVAILABLE'
          ? 'Backend gateway offline at http://localhost:8000. Start backend instances or toggle "Enable Dev Simulation" below to proceed.'
          : err.status === 404
          ? 'Hold API (POST /api/v1/events/1/holds) returned 404. Backend Phase 2 is pending. Toggle "Enable Dev Simulation" to test downstream checkout.'
          : (err.message || 'Failed to secure seat hold. Please reselect.'),
      });
    } finally {
      setIsHolding(false);
    }
  };

  const selectedSeats = useMemo(() => {
    return selectedSeatIds.map(id => seatLookup.get(id)).filter(Boolean);
  }, [selectedSeatIds, seatLookup]);

  return (
    <div className="flex flex-col min-h-[calc(100vh-140px)] relative">
      {/* Seat Map Controls Header */}
      <SeatMapHeader
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        zoomLevel={zoomLevel}
        onZoomIn={() => setZoomLevel(prev => Math.min(2.0, prev + 0.25))}
        onZoomOut={() => setZoomLevel(prev => Math.max(0.75, prev - 0.25))}
        onResetZoom={() => setZoomLevel(1.0)}
        selectedCount={selectedSeatIds.length}
        isLive={isLive}
        wsStatus={wsStatus}
      />

      {/* Notification Toast Banner */}
      {notification && (
        <div className={`px-4 py-2.5 text-xs font-mono flex items-center justify-between border-b ${
          notification.type === 'error'
            ? 'bg-[#FCEBE8] text-[#C23A20] border-[#E8472B]/30'
            : notification.type === 'warning'
            ? 'bg-[#F9F3E5] text-[#9E741B] border-[#C8962A]/30'
            : 'bg-[#EAF1ED] text-[#2F503B] border-[#3F6B4F]/30'
        }`}>
          <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
            {notification.type === 'error' ? (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            ) : notification.type === 'warning' ? (
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            ) : (
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs font-bold px-2 py-0.5 hover:opacity-80"
          >
            ✕
          </button>
        </div>
      )}

      {/* Development / Simulation & Integration Controls Bar */}
      <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] px-4 py-1.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-[#4A453D]">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useSimulationFallback}
                onChange={(e) => setUseSimulationFallback(e.target.checked)}
                className="accent-[#E8472B] rounded"
              />
              <span>
                <strong>[DEV SIMULATION]:</strong> Enable Mock Hold Fallback (When backend Phase 2 is pending)
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={simulateRaceCondition}
                onChange={(e) => setSimulateRaceCondition(e.target.checked)}
                className="accent-[#E8472B] rounded"
              />
              <span>Simulate Hold Contention / Rollback</span>
            </label>
          </div>
          <span className="text-[#706A61]">
            AUTHORITATIVE CAPACITY: 5,040 SEATS (VIP: 240 · PREMIUM: 1,200 · STANDARD: 3,600)
          </span>
        </div>
      </div>

      {/* Interactive Stadium Grid */}
      {isLoading ? (
        <div className="flex-grow flex flex-col items-center justify-center p-12 space-y-3 font-mono text-xs text-[#706A61]">
          <RefreshCw className="w-6 h-6 animate-spin text-[#E8472B]" />
          <span>Loading authoritative 5,040 stadium seat map...</span>
        </div>
      ) : (
        <SectionGrid
          seats={seats}
          activeSection={activeSection}
          selectedSeatIds={selectedSeatIds}
          onSelectSeat={handleSelectSeat}
          onOpenGroupSelect={handleOpenGroupSelect}
          zoomLevel={zoomLevel}
        />
      )}

      {/* Floating Selected Seats Ticket Drawer */}
      <SelectedSeatsSummary
        selectedSeats={selectedSeats}
        onRemoveSeat={handleRemoveSeat}
        onClearSelection={handleClearSelection}
        onProceedToHold={handleProceedToHold}
        isHolding={isHolding}
      />

      {/* Group Selection Modal */}
      <GroupSelectModal
        startSeat={groupModalSeat}
        allSeats={seats}
        isOpen={isGroupModalOpen}
        onClose={() => setIsGroupModalOpen(false)}
        onApplyGroup={handleApplyGroup}
      />
    </div>
  );
}
