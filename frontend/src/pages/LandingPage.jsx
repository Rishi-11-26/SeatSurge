import React, { useState, useEffect } from 'react';
import { PRIMARY_EVENT, fetchAuthoritativeEvent } from '../services/eventService';
import EventHero from '../components/event/EventHero';
import VenueOverview from '../components/event/VenueOverview';
import TicketCategories from '../components/event/TicketCategories';
import EventDetails from '../components/event/EventDetails';
import EventDiscovery from '../components/event/EventDiscovery';
import { Info, Wifi } from 'lucide-react';

export default function LandingPage({ onNavigate }) {
  const [activeEvent, setActiveEvent] = useState(PRIMARY_EVENT);

  // Probe live event from backend API (GET /api/v1/events/1)
  useEffect(() => {
    let isMounted = true;
    fetchAuthoritativeEvent(1).then(liveEvent => {
      if (isMounted && liveEvent) {
        setActiveEvent(liveEvent);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-0">
      {/* Notice Banner: Data Classification & Authoritative Backend Spec */}
      <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] px-4 py-2">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono text-[#4A453D]">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[#C8962A] flex-shrink-0" />
            <span>
              <strong>Phase F5 Real Integration:</strong> Authoritative 5,040 seats (240 VIP · 1,200 PREMIUM · 3,600 STANDARD). REST client + RFC 6455 WebSocket connected.
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-[#706A61]">
            <span className="flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${activeEvent.isLive ? 'bg-[#3F6B4F] animate-pulse' : 'bg-[#C8962A]'}`} />
              {activeEvent.isLive ? 'LIVE EVENT METADATA' : 'STANDBY MODE'}
            </span>
            <span>·</span>
            <span>GATEWAY: :8000</span>
          </div>
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
                WebSocket Live Fan-Out
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Sequence-numbered state broadcasts with automatic gap detection and snapshot resynchronization.
              </p>
            </div>

            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                03
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                FIFO Virtual Queue
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Fair token-gated admission via Redis Sorted Sets. Protects seat map APIs from sudden traffic spikes.
              </p>
            </div>

            <div className="bg-[#F4EFE6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                04
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Idempotent Checkout
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Client unique UUID headers guard every transaction to guarantee zero double charges on network retries.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Discover More Events Catalog */}
      <EventDiscovery onNavigate={onNavigate} />
    </div>
  );
}
