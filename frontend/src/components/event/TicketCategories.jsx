import React from 'react';
import { Check, ArrowRight, Zap, Users } from 'lucide-react';

export default function TicketCategories({ tiers, onNavigate }) {
  return (
    <section className="py-12 border-b border-[#D8CEBF] bg-[#EAE3D6]/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
              AUTHORITATIVE CONTRACT TIERS
            </span>
            <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F] mt-1">
              Ticket Categories & Section Pricing
            </h2>
            <p className="text-sm text-[#4A453D] mt-1 max-w-xl">
              All 3 tiers match backend PostgreSQL schema and seed allocations (VIP, PREMIUM, STANDARD) totaling exactly 5,040 seats.
            </p>
          </div>
          <div className="bg-[#F4EFE6] px-3.5 py-2 rounded border border-[#D8CEBF] text-xs font-mono text-[#4A453D] flex items-center gap-2">
            <Users className="w-4 h-4 text-[#C8962A]" />
            <span>MAX 6 ADJACENT SEATS PER TRANSACTION</span>
          </div>
        </div>

        {/* Categories Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier) => (
            <div 
              key={tier.id}
              className="bg-[#F4EFE6] border-2 border-[#D8CEBF] hover:border-[#15130F] transition-all rounded-lg p-6 flex flex-col justify-between shadow-sm relative group"
            >
              {/* Top Accent Strip */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold border ${tier.bgBadge}`}>
                    {tier.tier} TIER
                  </span>
                  <span className="text-xs font-mono text-[#706A61]">
                    {tier.seatsCount.toLocaleString()} SEATS
                  </span>
                </div>

                <div>
                  <h3 className="font-editorial text-2xl font-bold text-[#15130F] group-hover:text-[#E8472B] transition-colors">
                    {tier.name}
                  </h3>
                  <p className="text-xs font-mono text-[#706A61] mt-0.5">
                    {tier.rows} · Surge Arena
                  </p>
                </div>

                <p className="text-xs text-[#4A453D] leading-relaxed">
                  {tier.description}
                </p>

                {/* Price Display */}
                <div className="pt-2 pb-3 border-y border-[#D8CEBF] space-y-1">
                  <span className="text-[10px] font-mono uppercase text-[#706A61] block">
                    AUTHORITATIVE PRICE (CENTS & RUPEES)
                  </span>
                  <div className="flex items-baseline justify-between font-mono">
                    <span className="text-2xl sm:text-3xl font-black text-[#15130F]">
                      {tier.priceCents.toLocaleString()}¢
                    </span>
                    <span className="text-sm font-bold text-[#E8472B]">
                      {tier.priceFormatted}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-[#706A61] block">
                    Integer cents sent to API · Formatted: {tier.priceFormatted}
                  </span>
                </div>

                {/* Row & Seat ID Details */}
                <div className="bg-[#EAE3D6] p-2.5 rounded border border-[#D8CEBF] font-mono text-xs space-y-1">
                  <div className="flex justify-between text-[#4A453D]">
                    <span className="text-[#706A61]">Seat IDs:</span>
                    <span className="font-semibold text-[#15130F]">#{tier.seatIdRange[0]} – #{tier.seatIdRange[1]}</span>
                  </div>
                  <div className="flex justify-between text-[#4A453D]">
                    <span className="text-[#706A61]">Row Layout:</span>
                    <span className="font-semibold text-[#15130F]">{tier.seatsPerRow} seats/row</span>
                  </div>
                </div>

                {/* Perks Checklist */}
                <div className="space-y-2 pt-1">
                  <span className="text-[11px] font-mono uppercase text-[#706A61] font-semibold block">
                    Included Benefits:
                  </span>
                  <ul className="space-y-2 text-xs text-[#4A453D]">
                    {tier.perks.map((perk, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Check className="w-3.5 h-3.5 text-[#3F6B4F] mt-0.5 flex-shrink-0" />
                        <span className="leading-tight">{perk}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Bottom CTA */}
              <div className="pt-6 mt-6 border-t border-[#D8CEBF]">
                <button
                  onClick={() => onNavigate('seats')}
                  className="w-full py-3 bg-[#15130F] hover:bg-[#E8472B] text-[#F4EFE6] rounded font-mono text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 group-hover:shadow-md"
                >
                  <span>Select in {tier.tier}</span>
                  <ArrowRight className="w-4 h-4 text-[#C8962A] group-hover:text-white group-hover:translate-x-1 transition-all" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Concurrency Policy Callout */}
        <div className="bg-[#EAE3D6] p-4 rounded-lg border border-[#D8CEBF] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-[#4A453D]">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#C8962A] flex-shrink-0" />
            <span>
              <strong>Atomic Multi-Seat Lock:</strong> Selecting up to 6 continuous seats executes an atomic lock in Redis: all seats are reserved together or none.
            </span>
          </div>
          <button
            onClick={() => onNavigate('queue')}
            className="text-[#E8472B] hover:underline font-bold whitespace-nowrap"
          >
            Check Waiting Room Status →
          </button>
        </div>
      </div>
    </section>
  );
}
