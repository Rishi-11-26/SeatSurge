import React from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Check, 
  Clock, 
  X, 
  Accessibility, 
  Layers, 
  Info,
  Activity
} from 'lucide-react';
import { SEAT_SECTIONS } from '../../services/seatService';

export default function SeatMapHeader({
  activeSection,
  onSectionChange,
  zoomLevel,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  selectedCount,
  isLive,
}) {
  return (
    <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] p-4 sm:p-5 space-y-4">
      {/* Top Bar: Section Tabs & Zoom Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        
        {/* Section Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0" role="tablist">
          {SEAT_SECTIONS.map((sec) => (
            <button
              key={sec.id}
              role="tab"
              aria-selected={activeSection === sec.id}
              onClick={() => onSectionChange(sec.id)}
              className={`px-3 py-1.5 rounded text-xs font-mono whitespace-nowrap transition-all border ${
                activeSection === sec.id
                  ? 'bg-[#15130F] text-[#F4EFE6] border-[#15130F] font-bold shadow-sm'
                  : 'bg-[#F4EFE6] text-[#4A453D] border-[#D8CEBF] hover:border-[#15130F] hover:text-[#15130F]'
              }`}
            >
              <span>{sec.name}</span>
              <span className="ml-1.5 opacity-80 text-[10px]">
                ({sec.totalSeats.toLocaleString()})
              </span>
            </button>
          ))}
        </div>

        {/* Zoom Controls & Mode Indicator */}
        <div className="flex items-center gap-3">
          {/* Backend Mode Indicator */}
          <div className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded bg-[#F4EFE6] border border-[#D8CEBF]">
            <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-[#3F6B4F] animate-pulse' : 'bg-[#C8962A]'}`} />
            <span className="text-[#4A453D]">
              {isLive ? 'BACKEND LIVE' : '5,040 SEAT ENGINE'}
            </span>
          </div>

          {/* Zoom Buttons */}
          <div className="flex items-center bg-[#F4EFE6] rounded border border-[#D8CEBF] p-0.5">
            <button
              onClick={onZoomOut}
              disabled={zoomLevel <= 0.75}
              title="Zoom Out"
              aria-label="Zoom Out"
              className="p-1.5 hover:bg-[#EAE3D6] rounded text-[#4A453D] disabled:opacity-40 transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="px-2 font-mono text-xs text-[#15130F] font-semibold min-w-[50px] text-center">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={onZoomIn}
              disabled={zoomLevel >= 2.0}
              title="Zoom In"
              aria-label="Zoom In"
              className="p-1.5 hover:bg-[#EAE3D6] rounded text-[#4A453D] disabled:opacity-40 transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={onResetZoom}
              title="Reset Zoom to 100%"
              aria-label="Reset Zoom"
              className="p-1.5 hover:bg-[#EAE3D6] rounded text-[#706A61] border-l border-[#D8CEBF] transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* State & Shape Legend (Multi-dimensional visual cues beyond color) */}
      <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#4A453D]">
          <span className="font-bold text-[#15130F] text-xs">SEAT LEGEND:</span>
          
          {/* Available VIP */}
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-4 rounded-full bg-[#FCEBE8] border border-[#E8472B] inline-block" />
            <span>VIP (15,000¢)</span>
          </div>

          {/* Available PREMIUM */}
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-4 rounded-md bg-[#F9F3E5] border border-[#C8962A] inline-block" />
            <span>PREMIUM (7,500¢)</span>
          </div>

          {/* Available STANDARD */}
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-4 rounded-sm bg-[#EAF1ED] border border-[#3F6B4F] inline-block" />
            <span>STANDARD (3,500¢)</span>
          </div>

          {/* Selected */}
          <div className="flex items-center gap-1.5 font-bold text-[#E8472B]">
            <span className="w-4 h-4 rounded-sm bg-[#E8472B] text-white flex items-center justify-center">
              <Check className="w-2.5 h-2.5 stroke-[3]" />
            </span>
            <span>Selected</span>
          </div>

          {/* Held */}
          <div className="flex items-center gap-1.5 text-[#C8962A]">
            <span className="w-4 h-4 rounded-md bg-[#F9F3E5] border border-dashed border-[#C8962A] flex items-center justify-center">
              <Clock className="w-2.5 h-2.5" />
            </span>
            <span>Held (120s TTL)</span>
          </div>

          {/* Sold */}
          <div className="flex items-center gap-1.5 text-[#706A61]">
            <span className="w-4 h-4 bg-[#15130F] text-[#706A61] flex items-center justify-center">
              <X className="w-2.5 h-2.5" />
            </span>
            <span>Sold</span>
          </div>

          {/* Accessible */}
          <div className="flex items-center gap-1.5">
            <Accessibility className="w-4 h-4 text-[#3F6B4F]" />
            <span>Accessible (Seats 1-2)</span>
          </div>
        </div>

        {/* Selection Hint */}
        <div className="text-[11px] text-[#706A61] italic">
          Max 6 continuous seats · Shift+Click to group select
        </div>
      </div>
    </div>
  );
}
