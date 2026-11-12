import React, { useState } from 'react';
import { PRIMARY_EVENT } from '../services/eventService';
import EventHero from '../components/event/EventHero';
import VenueOverview from '../components/event/VenueOverview';
import TicketCategories from '../components/event/TicketCategories';
import EventDetails from '../components/event/EventDetails';
import EventDiscovery from '../components/event/EventDiscovery';
import { Info } from 'lucide-react';

export default function LandingPage({ onNavigate }) {
  const [activeEvent, setActiveEvent] = useState(PRIMARY_EVENT);

  return (
    <div className="space-y-0">
      {/* Notice Banner: Data Classification & Authoritative Backend Spec */}
      <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] px-4 py-2">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono text-[#4A453D]">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[#C8962A] flex-shrink-0" />
            <span>
              <strong>Phase F1 Event Experience:</strong> Authoritative allocation (5,040 seats: 240 VIP, 1,200 PREMIUM, 3,600 STANDARD) aligned with backend seed and <code className="bg-[#F4EFE6] px-1 py-0.5 rounded border border-[#C5BCAD]">docs/api-contract.md</code>.
            </span>
          </div>
          <span className="text-[#706A61] text-[11px]">
            API GATEWAY TARGET: http://localhost:8000/api/v1
          </span>
        </div>
      </div>

      {/* 1. Event Hero Section */}
      <EventHero event={activeEvent} onNavigate={onNavigate} />

      {/* 2. Venue Overview & 3D Interactive Bowl */}
      <VenueOverview event={activeEvent} onNavigate={onNavigate} />

      {/* 3. Authoritative Ticket Categories & Pricing Tiers */}
      <TicketCategories tiers={activeEvent.tiers} onNavigate={onNavigate} />

      {/* 4. Programme Timeline & Venue Security Policies */}
      <EventDetails event={activeEvent} />

      {/* 5. Engineering Architecture Foundation */}
      <section className="py-12 border-b border-[#D8CEBF] bg-[#EAE3D6]/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div>
            <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
              ENGINEERING FOUNDATION
            </span>
            <h2 className="font-editorial text-3xl font-bold text-[#15130F] mt-1">
              Built to withstand the 60-second flash rush
            </h2>
            <p className="text-sm text-[#4A453D] mt-1 max-w-xl">
              Stateless multi-instance architecture engineered with Redis in-memory concurrency controls and durable PostgreSQL storage.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                01
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Redis Distributed Locking
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Atomic multi-key acquisition for adjacent seats (up to 6). Eliminates race conditions with an all-or-nothing hold guarantee.
              </p>
            </div>

            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                02
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Fair Virtual Queue
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Shared in-memory FIFO queue position synchronized across all application nodes to regulate burst seat map traffic.
              </p>
            </div>

            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                03
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Sub-Second Fan-Out
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                WebSocket event fan-out keeps connected clients synchronized within 1 second upon every seat hold, purchase, or TTL release.
              </p>
            </div>

            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                04
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Biometric Bot Defense
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Real-time behavioural entropy and pointer velocity scoring (F1 ≥ 0.80) to challenge scalper automation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Event Discovery Catalogue */}
      <EventDiscovery onSelectEvent={setActiveEvent} onNavigate={onNavigate} />
    </div>
  );
}
