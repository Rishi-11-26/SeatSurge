import React, { memo } from 'react';
import { Check, Clock, X, Accessibility, Lock } from 'lucide-react';

const SeatCell = memo(function SeatCell({
  seat,
  isSelected,
  onSelect,
  onOpenGroupSelect,
}) {
  const isAvailable = seat.status === 'AVAILABLE';
  const isHeld = seat.status === 'HELD';
  const isSold = seat.status === 'SOLD';

  const handleClick = (e) => {
    if (e.shiftKey && isAvailable) {
      onOpenGroupSelect(seat);
    } else if (isAvailable || isSelected) {
      onSelect(seat);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      if (isAvailable || isSelected) {
        onSelect(seat);
      }
    }
  };

  // Determine shape, pattern, and icon based on state (distinguishable beyond color)
  let stateClasses = '';
  let icon = null;
  let statusText = 'Available';

  if (isSelected) {
    statusText = 'Selected';
    stateClasses = 'bg-[#E8472B] text-white border-[#C23A20] ring-2 ring-[#E8472B]/50 rounded-sm scale-110 z-10 shadow-sm';
    icon = <Check className="w-2.5 h-2.5 stroke-[3]" />;
  } else if (isSold) {
    statusText = 'Sold';
    stateClasses = 'bg-[#15130F] text-[#706A61] border-[#2A2620] cursor-not-allowed rounded-none opacity-80';
    icon = <X className="w-2.5 h-2.5 stroke-[2.5]" />;
  } else if (isHeld) {
    statusText = 'Held (120s TTL)';
    stateClasses = 'bg-[#F9F3E5] text-[#C8962A] border-dashed border-[#C8962A] cursor-not-allowed rounded-md';
    icon = <Clock className="w-2 h-2" />;
  } else {
    // AVAILABLE: Distinct styling per tier
    if (seat.tier === 'VIP') {
      stateClasses = 'bg-[#FCEBE8] text-[#E8472B] border-[#E8472B] hover:bg-[#E8472B] hover:text-white rounded-full';
    } else if (seat.tier === 'PREMIUM') {
      stateClasses = 'bg-[#F9F3E5] text-[#C8962A] border-[#C8962A] hover:bg-[#C8962A] hover:text-white rounded-lg';
    } else {
      stateClasses = 'bg-[#EAF1ED] text-[#3F6B4F] border-[#3F6B4F] hover:bg-[#3F6B4F] hover:text-white rounded-sm';
    }
  }

  const tooltipText = `Seat ${seat.row}-${seat.number} · ${seat.section} (${seat.tier}) · ${seat.price_cents?.toLocaleString()}¢ (₹${(seat.price_cents / 100).toFixed(2)}) · [${statusText}]${seat.is_accessible ? ' · Accessible' : ''}`;

  return (
    <div className="relative group/seat flex items-center justify-center">
      <button
        type="button"
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        disabled={isSold || isHeld}
        tabIndex={isAvailable || isSelected ? 0 : -1}
        title={tooltipText}
        aria-label={tooltipText}
        className={`w-6 h-6 flex items-center justify-center text-[10px] font-mono border transition-all duration-100 relative focus:outline-none focus:ring-2 focus:ring-[#15130F] ${stateClasses}`}
      >
        {icon ? (
          icon
        ) : seat.is_accessible ? (
          <Accessibility className="w-2.5 h-2.5 opacity-80" />
        ) : (
          <span className="text-[9px] font-semibold leading-none">{seat.number}</span>
        )}

        {/* Small accessibility marker dot if accessible and not selected */}
        {seat.is_accessible && !isSelected && (
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-[#3F6B4F] rounded-full border border-white" />
        )}
      </button>

      {/* Accessible rich tooltip on hover */}
      <div className="absolute bottom-full mb-1.5 hidden group-hover/seat:flex flex-col items-center z-40 pointer-events-none">
        <div className="bg-[#15130F] text-[#F4EFE6] px-2.5 py-1.5 rounded shadow-lg text-[10px] font-mono whitespace-nowrap space-y-0.5 border border-[#3E372E]">
          <div className="font-bold flex items-center gap-1.5">
            <span>Row {seat.row}, Seat {seat.number}</span>
            <span className="text-[#C8962A]">({seat.tier})</span>
          </div>
          <div className="text-[#A39C91] text-[9px]">
            {seat.price_cents?.toLocaleString()}¢ · ₹{(seat.price_cents / 100).toFixed(2)}
          </div>
          <div className="text-[9px] font-semibold">
            Status: <span className={isAvailable ? 'text-[#3F6B4F]' : isSelected ? 'text-[#E8472B]' : 'text-[#C8962A]'}>{statusText}</span>
          </div>
          {isAvailable && (
            <div className="text-[8px] text-[#A39C91] italic pt-0.5">
              Click to select · Shift+Click for group
            </div>
          )}
        </div>
        <div className="w-2 h-1 bg-[#15130F] [clip-path:polygon(0_0,100%_0,50%_100%)]"></div>
      </div>
    </div>
  );
});

export default SeatCell;
