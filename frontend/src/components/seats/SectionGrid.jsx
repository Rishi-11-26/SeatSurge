import React, { useMemo } from 'react';
import SeatCell from './SeatCell';

export default function SectionGrid({
  seats,
  activeSection,
  selectedSeatIds,
  onSelectSeat,
  onOpenGroupSelect,
  zoomLevel,
}) {
  // Group seats by row
  const rowsMap = useMemo(() => {
    // Filter by section if not ALL
    let filteredSeats = seats;
    if (activeSection === 'VIP') {
      filteredSeats = seats.filter(s => s.tier === 'VIP');
    } else if (activeSection === 'PREMIUM') {
      filteredSeats = seats.filter(s => s.tier === 'PREMIUM');
    } else if (activeSection === 'STANDARD') {
      filteredSeats = seats.filter(s => s.tier === 'STANDARD');
    }

    const map = new Map();
    for (const seat of filteredSeats) {
      if (!map.has(seat.row)) {
        map.set(seat.row, []);
      }
      map.get(seat.row).push(seat);
    }
    return map;
  }, [seats, activeSection]);

  const selectedSet = useMemo(() => new Set(selectedSeatIds), [selectedSeatIds]);

  return (
    <div className="flex-grow overflow-auto p-6 bg-[#F4EFE6] select-none min-h-[500px]">
      <div 
        style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top center' }}
        className="transition-transform duration-150 inline-block min-w-full text-center space-y-6 pb-28"
      >
        {/* Stage & Runway Visual */}
        <div className="max-w-xl mx-auto space-y-1">
          <div className="w-full py-2.5 bg-[#15130F] text-[#F4EFE6] rounded-sm font-mono text-xs font-bold tracking-widest shadow-md uppercase border border-[#2A2620]">
            STAGE · CATWALK RUNWAY
          </div>
          <div className="w-16 h-8 mx-auto bg-[#E8472B] rounded-b-sm flex items-center justify-center text-white text-[9px] font-mono font-bold shadow-sm">
            STAGE B
          </div>
          <div className="text-[10px] font-mono text-[#706A61] italic">
            ▲ AUDIENCE SIGHTLINE TOWARDS STAGE ▲
          </div>
        </div>

        {/* Rows Container */}
        <div className="space-y-3 pt-4">
          {Array.from(rowsMap.entries()).map(([rowLetter, rowSeats]) => {
            const rowTier = rowSeats[0]?.tier;
            const tierColor = rowTier === 'VIP' ? 'text-[#E8472B]' : rowTier === 'PREMIUM' ? 'text-[#C8962A]' : 'text-[#3F6B4F]';

            return (
              <div 
                key={rowLetter} 
                className="flex items-center justify-center gap-2 group/row hover:bg-[#EAE3D6]/40 py-0.5 px-2 rounded"
              >
                {/* Left Row Indicator */}
                <div className={`w-8 text-right font-mono text-xs font-bold ${tierColor} flex-shrink-0`}>
                  {rowLetter}
                </div>

                {/* Seat Cells in Row */}
                <div className="flex items-center gap-1.5 flex-wrap justify-center max-w-full">
                  {rowSeats.map((seat) => (
                    <SeatCell
                      key={seat.id}
                      seat={seat}
                      isSelected={selectedSet.has(seat.id)}
                      onSelect={onSelectSeat}
                      onOpenGroupSelect={onOpenGroupSelect}
                    />
                  ))}
                </div>

                {/* Right Row Indicator */}
                <div className={`w-8 text-left font-mono text-xs font-bold ${tierColor} flex-shrink-0`}>
                  {rowLetter}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
