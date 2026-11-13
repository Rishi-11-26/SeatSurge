import React, { useState } from 'react';
import { MapPin, Navigation, Info, ArrowUpRight, CheckCircle2 } from 'lucide-react';

export default function VenueOverview({ event, onNavigate }) {
  const [selectedSection, setSelectedSection] = useState('VIP');

  const currentTier = event.tiers.find(t => t.id === selectedSection) || event.tiers[0];

  return (
    <section className="py-12 border-b border-[#D8CEBF] bg-[#F4EFE6]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Section Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
              VENUE ARCHITECTURE & CAPACITIES
            </span>
            <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F] mt-1">
              {event.venue.name} Layout
            </h2>
            <p className="text-sm text-[#4A453D] mt-1 max-w-xl">
              5,040 seats across 3 tiers — VIP, Premium, and Standard. Click a section to explore seating options.
            </p>
          </div>
          <div className="text-xs font-mono text-[#706A61] flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#3F6B4F]"></span>
            <span>Live Seating Available</span>
          </div>
        </div>

        {/* Stadium Diagram + Section Details Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left: Interactive Stadium SVG Visualizer */}
          <div className="lg:col-span-7 bg-[#EAE3D6] p-6 rounded-lg border border-[#D8CEBF] shadow-sm space-y-4">
            <div className="flex items-center justify-between text-xs font-mono border-b border-[#D8CEBF] pb-3">
              <span className="font-bold text-[#15130F] flex items-center gap-1.5">
                <Navigation className="w-3.5 h-3.5 text-[#E8472B]" /> 3D BOWL PERSPECTIVE
              </span>
              <span className="text-[#706A61]">NORTH STAGE ORIENTATION</span>
            </div>

            {/* Stadium Bowl SVG */}
            <div className="relative aspect-[16/10] bg-[#15130F] rounded-md overflow-hidden p-4 flex flex-col items-center justify-between">
              
              {/* Stage Visual */}
              <div className="w-2/3 h-10 bg-[#E8472B] rounded-sm flex items-center justify-center text-white font-mono text-xs font-bold shadow-md tracking-wider">
                MAIN STAGE & CATWALK RUNWAY
              </div>

              {/* Sections Representation */}
              <div className="w-full flex-grow flex flex-col items-center justify-center gap-2 my-3">
                {/* VIP Section */}
                <button
                  onClick={() => setSelectedSection('VIP')}
                  className={`w-3/4 py-3 rounded text-center transition-all font-mono text-xs font-bold border-2 ${
                    selectedSection === 'VIP'
                      ? 'bg-[#E8472B] text-white border-white scale-105 shadow-lift'
                      : 'bg-[#C23A20]/40 text-[#FCEBE8] border-[#E8472B]/60 hover:bg-[#E8472B]/60'
                  }`}
                >
                  <div className="flex items-center justify-between px-4">
                    <span>FLOOR VIP</span>
                    <span className="text-[10px] opacity-90">ROWS A–D · 240 SEATS (60/ROW)</span>
                    <span>15,000¢ (₹150)</span>
                  </div>
                </button>

                {/* PREMIUM Concourse */}
                <button
                  onClick={() => setSelectedSection('PREMIUM')}
                  className={`w-5/6 py-3.5 rounded text-center transition-all font-mono text-xs font-bold border-2 ${
                    selectedSection === 'PREMIUM'
                      ? 'bg-[#C8962A] text-[#15130F] border-white scale-105 shadow-lift'
                      : 'bg-[#9E741B]/40 text-[#F9F3E5] border-[#C8962A]/60 hover:bg-[#C8962A]/60'
                  }`}
                >
                  <div className="flex items-center justify-between px-4">
                    <span>LOWER BOWL PREMIUM</span>
                    <span className="text-[10px] opacity-90">ROWS E–P · 1,200 SEATS (100/ROW)</span>
                    <span>7,500¢ (₹75)</span>
                  </div>
                </button>

                {/* STANDARD Grandstand */}
                <button
                  onClick={() => setSelectedSection('STANDARD')}
                  className={`w-full py-4 rounded text-center transition-all font-mono text-xs font-bold border-2 ${
                    selectedSection === 'STANDARD'
                      ? 'bg-[#3F6B4F] text-white border-white scale-105 shadow-lift'
                      : 'bg-[#2F503B]/50 text-[#EAF1ED] border-[#3F6B4F]/60 hover:bg-[#3F6B4F]/60'
                  }`}
                >
                  <div className="flex items-center justify-between px-4">
                    <span>UPPER BOWL STANDARD</span>
                    <span className="text-[10px] opacity-90">ROWS Q–Z & AA–AH · 3,600 SEATS (200/ROW)</span>
                    <span>3,500¢ (₹35)</span>
                  </div>
                </button>
              </div>

              {/* Bottom Gates Bar */}
              <div className="w-full flex justify-between text-[10px] font-mono text-[#A39C91] pt-2 border-t border-[#2A2620]">
                <span>← GATE 1-4 (WEST)</span>
                <span>CENTRAL CONCOURSE ENTRY</span>
                <span>GATE 5-8 (EAST) →</span>
              </div>
            </div>

            {/* Micro Caption */}
            <p className="text-[11px] text-[#706A61] font-mono text-center">
              Click any section above to inspect backend row bounds, seat count, and authoritative pricing.
            </p>
          </div>

          {/* Right: Selected Section Deep-Dive Card */}
          <div className="lg:col-span-5 bg-[#EAE3D6] p-6 rounded-lg border border-[#D8CEBF] space-y-5">
            <div className="flex items-center justify-between border-b border-[#D8CEBF] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#706A61] block">
                  SELECTED SECTION
                </span>
                <h3 className="font-editorial text-2xl font-bold text-[#15130F]">
                  {currentTier.name}
                </h3>
              </div>
              <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold border ${currentTier.bgBadge}`}>
                {currentTier.tier} TIER
              </span>
            </div>

            <p className="text-xs text-[#4A453D] leading-relaxed">
              {currentTier.description}
            </p>

            {/* Authoritative Metrics Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF]">
                <span className="text-[#706A61] block text-[10px]">SECTION CAPACITY</span>
                <span className="font-bold text-[#15130F] text-sm">{currentTier.seatsCount.toLocaleString()} Seats</span>
              </div>
              <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF]">
                <span className="text-[#706A61] block text-[10px]">ROW ALLOCATION</span>
                <span className="font-bold text-[#15130F] text-sm">{currentTier.rows}</span>
              </div>
              <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF]">
                <span className="text-[#706A61] block text-[10px]">SEAT ID RANGE</span>
                <span className="font-bold text-[#15130F] text-sm">#{currentTier.seatIdRange[0]} – #{currentTier.seatIdRange[1]}</span>
              </div>
              <div className="bg-[#F4EFE6] p-3 rounded border border-[#D8CEBF]">
                <span className="text-[#706A61] block text-[10px]">PRICE (CENTS / RUPEES)</span>
                <span className="font-bold text-[#E8472B] text-sm">{currentTier.priceCents.toLocaleString()}¢ ({currentTier.priceFormatted})</span>
              </div>
            </div>

            {/* Section Perks */}
            <div className="space-y-2 pt-1">
              <span className="text-xs font-mono font-bold text-[#15130F] block">
                Section Amenities & Sightlines:
              </span>
              <ul className="space-y-1.5 text-xs text-[#4A453D]">
                {currentTier.perks.map((perk, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6B4F] flex-shrink-0" />
                    <span>{perk}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Action Button */}
            <div className="pt-2">
              <button
                onClick={() => onNavigate('seats')}
                className="w-full py-3 bg-[#15130F] hover:bg-[#2A2620] text-[#F4EFE6] rounded font-mono text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors"
              >
                <span>Select Seats in {currentTier.tier} Tier</span>
                <ArrowUpRight className="w-4 h-4 text-[#C8962A]" />
              </button>
            </div>
          </div>
        </div>

        {/* Venue Guidelines & Transit */}
        <div className="bg-[#EAE3D6] p-4 sm:p-5 rounded-lg border border-[#D8CEBF] grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono text-[#4A453D]">
          <div>
            <span className="font-bold text-[#15130F] block mb-1">STADIUM ADDRESS</span>
            <p className="text-[11px] leading-relaxed text-[#706A61]">{event.venue.address}</p>
          </div>
          <div>
            <span className="font-bold text-[#15130F] block mb-1">RAPID TRANSIT</span>
            <p className="text-[11px] leading-relaxed text-[#706A61]">{event.venue.transit}</p>
          </div>
          <div>
            <span className="font-bold text-[#15130F] block mb-1">PARKING & GATES</span>
            <p className="text-[11px] leading-relaxed text-[#706A61]">{event.venue.gates}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
