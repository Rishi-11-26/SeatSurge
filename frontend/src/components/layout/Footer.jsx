import React from 'react';
import { ShieldCheck, Cpu, Database, Info } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-[#D8CEBF] bg-[#EAE3D6] mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 text-sm">
          {/* Col 1: Platform Overview */}
          <div className="space-y-2">
            <h4 className="font-editorial text-lg font-bold text-[#15130F]">SeatSurge Platform</h4>
            <p className="text-xs text-[#4A453D] leading-relaxed">
              Designed for extreme flash-sale spikes. Eliminates race conditions with Redis single-threaded atomic primitives and real-time WebSocket state synchronization.
            </p>
            <div className="text-[11px] font-mono text-[#706A61] pt-1">
              Architecture Baseline v1.0 · YUKTIK 2026
            </div>
          </div>

          {/* Col 2: High Concurrency Design Targets */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-[#15130F] flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-[#C8962A]" /> Concurrency Targets
            </h4>
            <ul className="text-xs text-[#4A453D] space-y-1">
              <li>• Target: Zero double bookings under concurrent load</li>
              <li>• Spec: Atomic adjacent group holds (up to 6)</li>
              <li>• Spec: 120-second hold TTL with auto-release</li>
              <li>• Target: &lt; 1-second seat state broadcast</li>
            </ul>
          </div>

          {/* Col 3: Distributed Architecture */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-[#15130F] flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-[#C8962A]" /> Architecture Spec
            </h4>
            <ul className="text-xs text-[#4A453D] space-y-1">
              <li>• NGINX Gateway (Round-Robin Port 8000)</li>
              <li>• 2 Stateless FastAPI / Python Workers</li>
              <li>• Redis Cluster: Mutex Locks & Pub/Sub</li>
              <li>• PostgreSQL Durable Storage</li>
            </ul>
          </div>

          {/* Col 4: AI & Bot Screening */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-[#15130F] flex items-center gap-1.5">
              <Database className="w-4 h-4 text-[#E8472B]" /> Bot Screening Pipeline
            </h4>
            <p className="text-xs text-[#4A453D] leading-relaxed">
              Real-time behavioural biometric risk scoring evaluating mouse jitter, keystroke intervals, and request velocity. Target F1 score ≥ 0.80 with rule-based fallback.
            </p>
          </div>
        </div>

        <div className="mt-8 pt-4 border-t border-[#D8CEBF] flex flex-col sm:flex-row items-center justify-between text-xs text-[#706A61] font-mono gap-2">
          <div>
            SEATSURGE ENGINE © 2026 · ALL RIGHTS RESERVED
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1 text-[#C8962A]">
              <Info className="w-3.5 h-3.5" />
              STATUS: PRE-INTEGRATION UI PREVIEW (PHASE F0)
            </span>
            <span className="hidden sm:inline">P95 LATENCY TARGET: &lt; 200ms</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
