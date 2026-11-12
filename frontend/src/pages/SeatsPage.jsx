import React, { useState, useEffect, useCallback, useMemo } from 'react';
import SeatMapHeader from '../components/seats/SeatMapHeader';
import SectionGrid from '../components/seats/SectionGrid';
import SelectedSeatsSummary from '../components/seats/SelectedSeatsSummary';
import GroupSelectModal from '../components/seats/GroupSelectModal';
import { loadSeatMap, validateGroupAdjacency } from '../services/seatService';
import { createSeatHold } from '../services/api';
import { AlertCircle, CheckCircle, RefreshCw, AlertTriangle, ShieldCheck } from 'lucide-react';

export default function SeatsPage({ onNavigate }) {
  const [seats, setSeats] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [activeSection, setActiveSection] = useState('VIP'); // Fast initial section view
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [selectedSeatIds, setSelectedSeatIds] = useState([]);
  
  // Group selection modal state
  const [groupModalSeat, setGroupModalSeat] = useState(null);
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);

  // Notifications and Simulation State
  const [notification, setNotification] = useState(null);
  const [isHolding, setIsHolding] = useState(false);
  const [simulateRaceCondition, setSimulateRaceCondition] = useState(false);

  // Fast seat map lookup map by ID
  const seatLookup = useMemo(() => {
    const map = new Map();
    for (const seat of seats) {
      map.set(seat.id, seat);
    }
    return map;
  }, [seats]);

  // Load seats
  const fetchSeats = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await loadSeatMap(1);
      setSeats(result.seats);
      setIsLive(result.isLive);
    } catch (err) {
      console.error('Failed to load seat map', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSeats();
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

  // Hold & Checkout Flow (Demonstrates Optimistic Contention & Rollback Handling)
  const handleProceedToHold = async () => {
    const selected = selectedSeatIds.map(id => seatLookup.get(id)).filter(Boolean);
    if (selected.length === 0) return;

    setIsHolding(true);
    setNotification(null);

    try {
      // 1. If contention simulation is enabled, simulate another customer claiming the seat
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

      // 2. Real Backend Hold Call (or development fallback)
      let holdData = null;
      try {
        const admissionToken = localStorage.getItem('seatsurge_admission_token');
        holdData = await createSeatHold({
          eventId: 1,
          seatIds: selected.map(s => s.id),
          admissionToken,
        });
      } catch (err) {
        // Fallback for pre-integration phase
        holdData = {
          hold_id: 'hld_sim_' + Math.random().toString(36).substring(2, 10),
          event_id: 1,
          seat_ids: selected.map(s => s.id),
          time_remaining_seconds: 120,
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
      setNotification({
        type: 'error',
        message: err.message || 'Failed to secure hold. Please reselect available seats.',
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

      {/* Development / Demo Race Condition Simulation Bar */}
      <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] px-4 py-1.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-[#4A453D]">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={simulateRaceCondition}
              onChange={(e) => setSimulateRaceCondition(e.target.checked)}
              className="accent-[#E8472B] rounded"
            />
            <span>
              <strong>[DEV SIMULATION]:</strong> Simulate Hold Contention / Rollback ("Seat already taken by another user")
            </span>
          </label>
          <span className="text-[#706A61]">
            AUTHORITATIVE CAPACITY: 5,040 SEATS (VIP: 240 · PREMIUM: 1,200 · STANDARD: 3,600)
          </span>
        </div>
      </div>

      {/* Interactive Stadium Grid */}
      {isLoading ? (
        <div className="flex-grow flex flex-col items-center justify-center p-12 space-y-3 font-mono text-xs text-[#706A61]">
          <RefreshCw className="w-6 h-6 animate-spin text-[#E8472B]" />
          <span>Generating authoritative 5,040 stadium seat map...</span>
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
