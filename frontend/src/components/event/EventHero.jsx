import React from 'react';
import { Calendar, MapPin, Users, ArrowRight, ShieldCheck, Clock, Sparkles } from 'lucide-react';

export default function EventHero({ event, onNavigate }) {
  return (
    <section className="relative overflow-hidden pt-6 pb-8 border-b border-[#D8CEBF]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Main Info */}
          <div className="lg:col-span-8 space-y-5">
            {/* Top Live Badge */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E8472B]/10 border border-[#E8472B]/30 text-xs font-mono font-semibold text-[#E8472B]">
                <span className="w-2 h-2 rounded-full bg-[#E8472B] animate-ping"></span>
                ACTIVE FLASH SALE · EVENT #{event.id}
              </span>
              <span className="text-xs font-mono text-[#706A61] bg-[#EAE3D6] px-2.5 py-1 rounded border border-[#D8CEBF]">
                5,040 AUTHORITATIVE SEATS
              </span>
              <span className="text-xs font-mono text-[#3F6B4F] bg-[#3F6B4F]/10 px-2.5 py-1 rounded border border-[#3F6B4F]/30 font-semibold">
                REDIS MUTEX LOCK PROTECTED
              </span>
            </div>

            {/* Headline */}
            <div>
              <p className="text-xs font-mono uppercase tracking-widest text-[#706A61] mb-1">
                {event.category} · {event.genre}
              </p>
              <h1 className="font-editorial text-4xl sm:text-5xl lg:text-6xl font-black text-[#15130F] leading-[1.08] tracking-tight">
                {event.title}
              </h1>
              <p className="font-serif italic text-lg sm:text-xl text-[#4A453D] mt-2">
                {event.headline}
              </p>
            </div>

            {/* Event Key Facts */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-xs font-mono">
              <div className="bg-[#EAE3D6] p-3 rounded border border-[#D8CEBF] space-y-1">
                <span className="text-[#706A61] block flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-[#C8962A]" /> DATE & TIME
                </span>
                <span className="font-bold text-[#15130F] block">{event.dateFormatted}</span>
                <span className="text-[#4A453D] block">{event.time}</span>
              </div>
              <div className="bg-[#EAE3D6] p-3 rounded border border-[#D8CEBF] space-y-1">
                <span className="text-[#706A61] block flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-[#E8472B]" /> VENUE
                </span>
                <span className="font-bold text-[#15130F] block">{event.venue.name}</span>
                <span className="text-[#4A453D] block">{event.venue.city}</span>
              </div>
              <div className="bg-[#EAE3D6] p-3 rounded border border-[#D8CEBF] space-y-1">
                <span className="text-[#706A61] block flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-[#3F6B4F]" /> CAPACITY & RULES
                </span>
                <span className="font-bold text-[#15130F] block">{event.venue.totalSeats.toLocaleString()} Seats Total</span>
                <span className="text-[#4A453D] block">Max 6 Adjacent / TX</span>
              </div>
            </div>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4 pt-3">
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
                <span>View Live 5,040 Seat Map</span>
              </button>
            </div>
          </div>

          {/* Right Ticket Mockup Card */}
          <div className="lg:col-span-4">
            <div className="bg-[#EAE3D6] border-2 border-[#15130F] rounded-lg shadow-ticket overflow-hidden">
              <div className="bg-[#15130F] text-[#EAE3D6] px-4 py-2.5 flex items-center justify-between font-mono text-xs">
                <span className="flex items-center gap-1.5 text-[#C8962A]">
                  <Sparkles className="w-3.5 h-3.5" /> AUTHORITATIVE TIERS
                </span>
                <span className="text-[#E8472B] font-bold">EVENT #{event.id}</span>
              </div>
              <div className="p-5 space-y-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-[#706A61] tracking-wider block">
                    BACKEND SEED ALLOCATION & PRICING
                  </span>
                  <div className="mt-2 space-y-1.5 font-mono text-xs">
                    {/* VIP */}
                    <div className="flex justify-between items-center py-1.5 border-b border-[#D8CEBF]">
                      <div>
                        <span className="font-bold text-[#15130F] block">VIP (Rows A–D)</span>
                        <span className="text-[10px] text-[#706A61]">240 seats · Floor VIP</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-[#E8472B] block">15,000¢</span>
                        <span className="text-[10px] text-[#706A61]">₹150.00</span>
                      </div>
                    </div>
                    {/* PREMIUM */}
                    <div className="flex justify-between items-center py-1.5 border-b border-[#D8CEBF]">
                      <div>
                        <span className="font-bold text-[#15130F] block">PREMIUM (Rows E–P)</span>
                        <span className="text-[10px] text-[#706A61]">1,200 seats · Lower Bowl</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-[#C8962A] block">7,500¢</span>
                        <span className="text-[10px] text-[#706A61]">₹75.00</span>
                      </div>
                    </div>
                    {/* STANDARD */}
                    <div className="flex justify-between items-center py-1.5">
                      <div>
                        <span className="font-bold text-[#15130F] block">STANDARD (Q–Z, AA–AH)</span>
                        <span className="text-[10px] text-[#706A61]">3,600 seats · Upper Bowl</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-[#3F6B4F] block">3,500¢</span>
                        <span className="text-[10px] text-[#706A61]">₹35.00</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="ticket-divider my-2"></div>

                <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF] text-[11px] font-mono space-y-1 text-[#4A453D]">
                  <div className="flex items-center gap-1 text-[#3F6B4F] font-bold">
                    <ShieldCheck className="w-3.5 h-3.5" /> ZERO DOUBLE BOOKING LOCK
                  </div>
                  <p className="text-[10px] text-[#706A61] leading-tight">
                    Atomic Redis multi-key locks ensure zero double bookings across cluster instances.
                  </p>
                </div>

                <button
                  onClick={() => onNavigate('queue')}
                  className="w-full py-2.5 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded text-xs font-mono font-medium uppercase tracking-wider transition-colors flex items-center justify-center gap-2"
                >
                  <Clock className="w-3.5 h-3.5 text-[#C8962A]" /> Join Waiting Room
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
