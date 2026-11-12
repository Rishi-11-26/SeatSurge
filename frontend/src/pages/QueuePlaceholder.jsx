import React from 'react';
import { Users, Clock, ArrowLeft, Info, ShieldCheck } from 'lucide-react';

export default function QueuePlaceholder({ onNavigate }) {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-6">
      <div className="w-16 h-16 mx-auto rounded-full bg-[#EAE3D6] border border-[#D8CEBF] flex items-center justify-center text-[#E8472B]">
        <Users className="w-8 h-8" />
      </div>
      <div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-[#EAE3D6] border border-[#D8CEBF] text-xs font-mono text-[#706A61] mb-2">
          <Info className="w-3.5 h-3.5 text-[#C8962A]" />
          <span>PHASE F3 SCAFFOLD · INTEGRATION PENDING</span>
        </div>
        <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F]">
          Virtual Waiting Room
        </h2>
        <p className="text-sm text-[#4A453D] max-w-md mx-auto mt-2">
          This feature will be fully built in Phase F3 and connected to the backend Redis FIFO queue in Phase F5. No live admission tokens are active in this preview.
        </p>
      </div>

      <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 max-w-md mx-auto text-left space-y-3 font-mono text-xs">
        <div className="flex justify-between border-b border-[#D8CEBF] pb-2">
          <span className="text-[#706A61]">AUTHORITATIVE ENDPOINT:</span>
          <span className="font-bold text-[#15130F]">POST /api/v1/queue/enter</span>
        </div>
        <div className="flex justify-between border-b border-[#D8CEBF] pb-2">
          <span className="text-[#706A61]">QUEUE ALGORITHM:</span>
          <span>Redis Sorted Set (FIFO)</span>
        </div>
        <div className="flex justify-between border-b border-[#D8CEBF] pb-2">
          <span className="text-[#706A61]">SESSION RETENTION:</span>
          <span>Stable Session UUID in localStorage</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[#706A61]">FRONTEND STATUS:</span>
          <span className="text-[#C8962A] font-bold">Scaffold Only (F1 Stage)</span>
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
