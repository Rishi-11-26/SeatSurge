import React from 'react';
import { Activity, ArrowLeft, Info, Grid } from 'lucide-react';

export default function SeatsPlaceholder({ onNavigate }) {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-6">
      <div className="w-16 h-16 mx-auto rounded-full bg-[#EAE3D6] border border-[#D8CEBF] flex items-center justify-center text-[#3F6B4F]">
        <Activity className="w-8 h-8" />
      </div>
      <div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-[#EAE3D6] border border-[#D8CEBF] text-xs font-mono text-[#706A61] mb-2">
          <Info className="w-3.5 h-3.5 text-[#C8962A]" />
          <span>PHASE F2 TARGET · SCAFFOLD VIEW</span>
        </div>
        <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F]">
          Interactive 5,040-Seat Stadium Map
        </h2>
        <p className="text-sm text-[#4A453D] max-w-md mx-auto mt-2">
          The high-performance interactive canvas/SVG seat selection engine will be developed in Phase F2 and connected to WebSocket streams in Phase F5.
        </p>
      </div>

      <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 max-w-md mx-auto text-left space-y-2.5 font-mono text-xs">
        <div className="text-[10px] text-[#706A61] uppercase tracking-wider font-bold border-b border-[#D8CEBF] pb-1">
          AUTHORITATIVE BACKEND SEAT ALLOCATION:
        </div>
        <div className="flex justify-between py-1 border-b border-[#D8CEBF]/60">
          <span className="text-[#E8472B] font-bold">VIP:</span>
          <span>Rows A–D (4 rows) · 240 seats (IDs 1–240)</span>
        </div>
        <div className="flex justify-between py-1 border-b border-[#D8CEBF]/60">
          <span className="text-[#C8962A] font-bold">PREMIUM:</span>
          <span>Rows E–P (12 rows) · 1,200 seats (IDs 241–1440)</span>
        </div>
        <div className="flex justify-between py-1 border-b border-[#D8CEBF]/60">
          <span className="text-[#3F6B4F] font-bold">STANDARD:</span>
          <span>Rows Q–Z & AA–AH (18 rows) · 3,600 seats (IDs 1441–5040)</span>
        </div>
        <div className="flex justify-between pt-1 font-bold text-[#15130F]">
          <span>TOTAL CAPACITY:</span>
          <span>5,040 SEATS (EXACT)</span>
        </div>
      </div>

      <div className="pt-4 flex justify-center gap-4">
        <button
          onClick={() => onNavigate('landing')}
          className="px-5 py-2.5 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded text-xs font-mono font-medium flex items-center gap-2 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Event Overview
        </button>
      </div>
    </div>
  );
}
