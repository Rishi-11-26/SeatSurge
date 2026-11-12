import React from 'react';
import { Ticket, X, ShieldCheck, ArrowRight, AlertTriangle, Trash2 } from 'lucide-react';
import { validateGroupAdjacency } from '../../services/seatService';

export default function SelectedSeatsSummary({
  selectedSeats,
  onRemoveSeat,
  onClearSelection,
  onProceedToHold,
  isHolding,
}) {
  if (!selectedSeats || selectedSeats.length === 0) {
    return (
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-[#15130F] text-[#F4EFE6] border-t-2 border-[#2A2620] py-3.5 px-4 sm:px-6 shadow-2xl">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Ticket className="w-4 h-4 text-[#C8962A]" />
            <span>Select up to 6 continuous seats to reserve. Click any available seat to begin.</span>
          </div>
          <span className="text-[#A39C91] text-[11px]">
            MAX 6 SEATS · 120s HOLD TTL · ATOMIC LOCK GUARANTEED
          </span>
        </div>
      </div>
    );
  }

  // Calculate totals
  const totalCents = selectedSeats.reduce((sum, s) => sum + (s.price_cents || 0), 0);
  const totalRupees = (totalCents / 100).toFixed(2);
  const adjacency = validateGroupAdjacency(selectedSeats);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-[#15130F] text-[#F4EFE6] border-t-2 border-[#E8472B] shadow-2xl py-4 px-4 sm:px-6 animate-slide-up">
      <div className="max-w-7xl mx-auto space-y-3">
        
        {/* Main Row: Selection Pills, Pricing, Actions */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          
          {/* Left: Selected Seat Badges */}
          <div className="space-y-1.5 flex-grow">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="font-bold text-[#E8472B]">
                {selectedSeats.length} of 6 SEATS SELECTED
              </span>
              <span className="text-[#706A61]">·</span>
              {adjacency.valid ? (
                <span className="text-[#3F6B4F] flex items-center gap-1 font-semibold text-[11px]">
                  <ShieldCheck className="w-3.5 h-3.5" /> VALID ADJACENT GROUP
                </span>
              ) : (
                <span className="text-[#E8472B] flex items-center gap-1 font-semibold text-[11px]">
                  <AlertTriangle className="w-3.5 h-3.5" /> {adjacency.error}
                </span>
              )}
            </div>

            {/* Badges list */}
            <div className="flex flex-wrap items-center gap-2 max-h-16 overflow-y-auto pr-2">
              {selectedSeats.map((seat) => (
                <span
                  key={seat.id}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#26221C] border border-[#3E372E] text-xs font-mono text-[#F4EFE6]"
                >
                  <span className="font-bold">Row {seat.row}-{seat.number}</span>
                  <span className="text-[10px] text-[#C8962A]">({seat.tier})</span>
                  <button
                    onClick={() => onRemoveSeat(seat.id)}
                    title="Remove seat"
                    aria-label={`Remove seat ${seat.row}-${seat.number}`}
                    className="p-0.5 hover:bg-[#3E372E] rounded text-[#A39C91] hover:text-white"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Right: Price Total & Action Button */}
          <div className="flex flex-wrap items-center gap-4 flex-shrink-0">
            {/* Total Display */}
            <div className="text-right font-mono">
              <div className="text-[10px] text-[#A39C91] uppercase">TOTAL ORDER VALUE</div>
              <div className="flex items-baseline gap-2 justify-end">
                <span className="text-xl sm:text-2xl font-bold text-white">
                  {totalCents.toLocaleString()}¢
                </span>
                <span className="text-sm font-semibold text-[#E8472B]">
                  (₹{totalRupees})
                </span>
              </div>
            </div>

            {/* Clear Button */}
            <button
              onClick={onClearSelection}
              title="Clear all selections"
              aria-label="Clear all selections"
              className="p-2.5 text-[#A39C91] hover:text-white hover:bg-[#26221C] rounded text-xs font-mono flex items-center gap-1 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span className="hidden sm:inline">Clear</span>
            </button>

            {/* Proceed to Hold Button */}
            <button
              onClick={onProceedToHold}
              disabled={!adjacency.valid || isHolding}
              className={`px-5 py-3 rounded font-sans font-semibold text-xs tracking-wider uppercase flex items-center gap-2 transition-all shadow-md ${
                adjacency.valid && !isHolding
                  ? 'bg-[#E8472B] hover:bg-[#C23A20] text-white'
                  : 'bg-[#3E372E] text-[#A39C91] cursor-not-allowed'
              }`}
            >
              <span>{isHolding ? 'Holding Seats...' : 'Hold Seats (120s TTL)'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
