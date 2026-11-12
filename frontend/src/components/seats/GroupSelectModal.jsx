import React from 'react';
import { Users, X, Check, AlertCircle } from 'lucide-react';
import { getContiguousSeats } from '../../services/seatService';

export default function GroupSelectModal({
  startSeat,
  allSeats,
  isOpen,
  onClose,
  onApplyGroup,
}) {
  if (!isOpen || !startSeat) return null;

  const groupOptions = [2, 3, 4, 5, 6];

  const handleSelectCount = (count) => {
    const contiguous = getContiguousSeats(allSeats, startSeat, count);
    onApplyGroup(contiguous);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#F4EFE6] border-2 border-[#15130F] rounded-lg max-w-sm w-full p-5 shadow-2xl space-y-4">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#D8CEBF] pb-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-[#E8472B]" />
            <h3 className="font-editorial text-lg font-bold text-[#15130F]">
              Quick Group Selection
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-[#706A61] hover:text-[#15130F] hover:bg-[#EAE3D6]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Selected Starting Seat Info */}
        <div className="bg-[#EAE3D6] p-3 rounded border border-[#D8CEBF] text-xs font-mono space-y-1">
          <div className="flex justify-between font-bold text-[#15130F]">
            <span>Starting Seat:</span>
            <span>Row {startSeat.row}, Seat {startSeat.number}</span>
          </div>
          <div className="flex justify-between text-[#706A61]">
            <span>Section / Tier:</span>
            <span>{startSeat.section} ({startSeat.tier})</span>
          </div>
          <div className="flex justify-between text-[#706A61]">
            <span>Per Seat Price:</span>
            <span>{startSeat.price_cents?.toLocaleString()}¢ (₹{(startSeat.price_cents / 100).toFixed(2)})</span>
          </div>
        </div>

        {/* Group Size Buttons */}
        <div className="space-y-2">
          <span className="text-[11px] font-mono uppercase text-[#706A61] font-semibold block">
            Choose Number of Continuous Adjacent Seats:
          </span>
          <div className="grid grid-cols-5 gap-2">
            {groupOptions.map((count) => {
              const previewSeats = getContiguousSeats(allSeats, startSeat, count);
              const isAvailable = previewSeats.length === count;

              return (
                <button
                  key={count}
                  disabled={!isAvailable}
                  onClick={() => handleSelectCount(count)}
                  className={`py-3 rounded font-mono text-xs font-bold border transition-all flex flex-col items-center justify-center gap-1 ${
                    isAvailable
                      ? 'bg-[#EAE3D6] border-[#D8CEBF] text-[#15130F] hover:bg-[#E8472B] hover:text-white hover:border-[#E8472B] shadow-sm'
                      : 'bg-[#15130F]/5 border-[#D8CEBF]/40 text-[#A39C91] cursor-not-allowed opacity-50'
                  }`}
                >
                  <span className="text-base leading-none">{count}</span>
                  <span className="text-[9px] uppercase font-normal">Seats</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Notice */}
        <div className="text-[10px] font-mono text-[#706A61] flex items-center gap-1.5 pt-1">
          <AlertCircle className="w-3.5 h-3.5 text-[#C8962A] flex-shrink-0" />
          <span>Seats must be consecutive in the same row. Max 6 seats.</span>
        </div>
      </div>
    </div>
  );
}
