import React from 'react';
import { 
  Calendar, 
  MapPin, 
  Users, 
  ShieldCheck, 
  Clock, 
  ArrowRight, 
  Sparkles, 
  CheckCircle2,
  Info
} from 'lucide-react';

export default function LandingPage({ onNavigate }) {
  return (
    <div className="space-y-12 pb-16">
      {/* Notice Banner: Pre-Integration Architecture Spec */}
      <div className="bg-[#EAE3D6] border-b border-[#D8CEBF] px-4 py-2">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs font-mono text-[#4A453D]">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[#C8962A] flex-shrink-0" />
            <span>
              <strong>Phase F0 Prototype:</strong> UI preview following authoritative contract in <code className="bg-[#F4EFE6] px-1 py-0.5 rounded border border-[#C5BCAD]">docs/api-contract.md</code>. Live telemetry integrates in Phase F5.
            </span>
          </div>
          <span className="hidden sm:inline text-[#706A61]">
            PORT 8000 GATEWAY TARGET
          </span>
        </div>
      </div>

      {/* Hero Section: Editorial Headline & Live Flash Sale Card */}
      <section className="relative overflow-hidden pt-6 md:pt-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left Column: Editorial Headline & Meta */}
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#EAE3D6] border border-[#D8CEBF] text-xs font-mono text-[#4A453D]">
              <span className="w-2 h-2 rounded-full bg-[#E8472B]"></span>
              <span className="font-semibold text-[#E8472B]">FLASH SALE SHOWCASE</span>
              <span>·</span>
              <span>5,000+ SEAT VENUE SPEC</span>
            </div>

            <h1 className="font-editorial text-4xl sm:text-5xl lg:text-6xl font-black text-[#15130F] leading-[1.08] tracking-tight">
              Fair, real-time seat booking that <span className="italic font-normal underline decoration-[#E8472B] decoration-wavy decoration-2">survives</span> the crowd.
            </h1>

            <p className="text-base sm:text-lg text-[#4A453D] leading-relaxed max-w-2xl">
              Engineered to eliminate double bookings under peak concurrent load. Designed with in-memory distributed locks, fair FIFO queue admission, and live sub-second seat map updates across horizontally scaled nodes.
            </p>

            {/* Quick Meta Pills */}
            <div className="flex flex-wrap gap-4 pt-2 text-xs font-mono text-[#4A453D]">
              <div className="flex items-center gap-1.5 bg-[#EAE3D6] px-3 py-1.5 rounded border border-[#D8CEBF]">
                <Calendar className="w-4 h-4 text-[#C8962A]" />
                <span>NOV 28, 2026 · 19:30 IST</span>
              </div>
              <div className="flex items-center gap-1.5 bg-[#EAE3D6] px-3 py-1.5 rounded border border-[#D8CEBF]">
                <MapPin className="w-4 h-4 text-[#E8472B]" />
                <span>SURGE ARENA, AHMEDABAD (5,000 CAPACITY)</span>
              </div>
              <div className="flex items-center gap-1.5 bg-[#EAE3D6] px-3 py-1.5 rounded border border-[#D8CEBF]">
                <Users className="w-4 h-4 text-[#3F6B4F]" />
                <span>MAX 6 SEATS / TX</span>
              </div>
            </div>

            {/* CTA Group */}
            <div className="pt-4 flex flex-wrap items-center gap-4">
              <button
                onClick={() => onNavigate('queue')}
                className="px-6 py-3.5 bg-[#E8472B] hover:bg-[#C23A20] text-white font-sans font-semibold rounded shadow-md flex items-center gap-2 group transition-all text-sm tracking-wide"
              >
                <span>Enter Virtual Waiting Room</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
              <button
                onClick={() => onNavigate('seats')}
                className="px-6 py-3.5 bg-[#EAE3D6] hover:bg-[#D8CEBF] text-[#15130F] font-sans font-semibold rounded border border-[#C5BCAD] flex items-center gap-2 text-sm transition-all"
              >
                <span>Explore Live Seat Map</span>
              </button>
            </div>

            {/* Architecture Target Badges */}
            <div className="pt-2 flex flex-wrap items-center gap-6 text-xs text-[#706A61] font-mono border-t border-[#D8CEBF]/60">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6B4F]" /> TARGET: ZERO DOUBLE BOOKINGS
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6B4F]" /> SPEC: 120s HOLD TTL
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6B4F]" /> SPEC: BOT RISK SCREENING
              </span>
            </div>
          </div>

          {/* Right Column: Physical Ticket Metaphor Card */}
          <div className="lg:col-span-5">
            <div className="bg-[#EAE3D6] border-2 border-[#15130F] rounded-lg shadow-ticket overflow-hidden relative">
              {/* Top Accent Strip */}
              <div className="bg-[#15130F] text-[#EAE3D6] px-5 py-3 flex items-center justify-between">
                <span className="font-mono text-xs uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#C8962A]" /> HEADLINE EVENT PASS
                </span>
                <span className="text-xs font-mono text-[#E8472B] font-bold">
                  SURGE-2026-LIVE
                </span>
              </div>

              {/* Event Details Inside Card */}
              <div className="p-6 space-y-4">
                <div>
                  <span className="text-[11px] font-mono uppercase text-[#706A61] tracking-wider block">
                    TOUR FINALE SHOW
                  </span>
                  <h3 className="font-editorial text-2xl font-bold text-[#15130F]">
                    Symphony of Lights & Bass
                  </h3>
                  <p className="text-xs text-[#4A453D] mt-1">
                    Grand Arena Stage Live Broadcast & Stadium Experience
                  </p>
                </div>

                {/* Perforated Divider */}
                <div className="ticket-divider my-4"></div>

                {/* Seat Capacity & Real-Time Stats Spec */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-[#F4EFE6] p-2.5 rounded border border-[#D8CEBF]">
                    <span className="text-[#706A61] font-mono block text-[10px]">TOTAL CAPACITY</span>
                    <span className="font-mono text-base font-bold text-[#15130F]">5,040 SEATS</span>
                  </div>
                  <div className="bg-[#F4EFE6] p-2.5 rounded border border-[#D8CEBF]">
                    <span className="text-[#706A61] font-mono block text-[10px]">HOLD WINDOW</span>
                    <span className="font-mono text-base font-bold text-[#E8472B]">120 SECONDS</span>
                  </div>
                  <div className="bg-[#F4EFE6] p-2.5 rounded border border-[#D8CEBF]">
                    <span className="text-[#706A61] font-mono block text-[10px]">SYNC SPEED TARGET</span>
                    <span className="font-mono text-base font-bold text-[#3F6B4F]">&lt; 1.0 SEC</span>
                  </div>
                  <div className="bg-[#F4EFE6] p-2.5 rounded border border-[#D8CEBF]">
                    <span className="text-[#706A61] font-mono block text-[10px]">TARGET INSTANCES</span>
                    <span className="font-mono text-base font-bold text-[#C8962A]">2 NODES</span>
                  </div>
                </div>

                {/* Call to action inside ticket */}
                <div className="pt-2">
                  <button
                    onClick={() => onNavigate('queue')}
                    className="w-full py-3 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded font-sans font-medium text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2"
                  >
                    <Clock className="w-4 h-4 text-[#C8962A]" />
                    Join Waiting Room
                  </button>
                  <p className="text-[10px] text-center text-[#706A61] mt-2 font-mono">
                    Fair queue order maintained across all instances
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights: 4 Architectural Pillars */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <div className="border-t border-[#D8CEBF] pt-10">
          <div className="mb-8">
            <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
              ENGINEERING FOUNDATION
            </span>
            <h2 className="font-editorial text-3xl font-bold text-[#15130F] mt-1">
              Built to withstand the 60-second flash rush
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Pillar 1: Zero Double Bookings */}
            <div className="bg-[#EAE3D6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                01
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Redis Distributed Locking
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Contention is resolved in-memory with atomic multi-key operations. Adjacent seats (up to 6) are locked atomically: all seats or none.
              </p>
            </div>

            {/* Pillar 2: Fair Virtual Waiting Room */}
            <div className="bg-[#EAE3D6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                02
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Fair Virtual Queue
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Single global FIFO queue order enforced across all app instances. Token-based admission protects the seat map from database collapse.
              </p>
            </div>

            {/* Pillar 3: Real-Time Fan-Out */}
            <div className="bg-[#EAE3D6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                03
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Sub-Second Fan-Out
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Redis Pub/Sub propagates every seat hold, purchase, and expiry to all connected WebSocket clients within 1 second.
              </p>
            </div>

            {/* Pillar 4: AI Bot Screening */}
            <div className="bg-[#EAE3D6] p-5 rounded-lg border border-[#D8CEBF] space-y-3">
              <div className="w-9 h-9 rounded bg-[#15130F] text-[#F4EFE6] flex items-center justify-center font-mono font-bold text-sm">
                04
              </div>
              <h3 className="font-editorial text-lg font-bold text-[#15130F]">
                Biometric Bot Screening
              </h3>
              <p className="text-xs text-[#4A453D] leading-relaxed">
                Classifier scoring (F1 ≥ 0.80) intercepts automated scalper bots based on telemetry, timing velocity, and interaction entropy.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Ticket Category Preview */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="text-xs font-mono uppercase tracking-widest text-[#706A61]">
                OFFICIAL CATEGORIES (SPEC PREVIEW)
              </span>
              <h2 className="font-editorial text-2xl font-bold text-[#15130F] mt-0.5">
                Surge Arena Seating Sections
              </h2>
            </div>
            <div className="text-xs font-mono text-[#4A453D]">
              CONTRACT TIER TARGETS
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Category 1 */}
            <div className="bg-[#F4EFE6] p-4 rounded border border-[#D8CEBF] space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-sm text-[#15130F]">VIP Tier (Rows A-F)</span>
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#3F6B4F]/10 text-[#3F6B4F]">
                  SPEC: ₹150.00
                </span>
              </div>
              <p className="text-xs text-[#706A61]">Prime center view, premium acoustic zoning, dedicated entry.</p>
              <div className="pt-2 flex justify-between items-baseline font-mono">
                <span className="text-xs text-[#706A61]">TIER: VIP</span>
                <span className="text-lg font-bold text-[#15130F]">15,000 cents</span>
              </div>
            </div>

            {/* Category 2 */}
            <div className="bg-[#F4EFE6] p-4 rounded border border-[#D8CEBF] space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-sm text-[#15130F]">Club Tier (Middle)</span>
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#C8962A]/10 text-[#C8962A]">
                  SPEC: ₹75.00
                </span>
              </div>
              <p className="text-xs text-[#706A61]">Elevated sightlines, padded comfort seating, rapid concessions.</p>
              <div className="pt-2 flex justify-between items-baseline font-mono">
                <span className="text-xs text-[#706A61]">TIER: CLUB</span>
                <span className="text-lg font-bold text-[#15130F]">7,500 cents</span>
              </div>
            </div>

            {/* Category 3 */}
            <div className="bg-[#F4EFE6] p-4 rounded border border-[#D8CEBF] space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-sm text-[#15130F]">General Tier (Upper Deck)</span>
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#3F6B4F]/10 text-[#3F6B4F]">
                  SPEC: ₹35.00
                </span>
              </div>
              <p className="text-xs text-[#706A61]">Panoramic stadium energy, unobstructed full stage visual.</p>
              <div className="pt-2 flex justify-between items-baseline font-mono">
                <span className="text-xs text-[#706A61]">TIER: GENERAL</span>
                <span className="text-lg font-bold text-[#15130F]">3,500 cents</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
