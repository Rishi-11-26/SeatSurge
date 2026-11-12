import React from 'react';
import { Ticket, ShieldCheck, Activity, Users, Info } from 'lucide-react';

export default function Navbar({ activeRoute, onNavigate }) {
  return (
    <header className="border-b border-[#D8CEBF] bg-[#F4EFE6]/90 backdrop-blur-md sticky top-0 z-50">
      {/* Top micro-bar: Architecture spec & status placeholders */}
      <div className="bg-[#15130F] text-[#EAE3D6] px-4 py-1.5 text-xs font-mono flex flex-wrap items-center justify-between gap-2 border-b border-[#2A2620]">
        <div className="flex items-center space-x-3 text-[11px]">
          <span className="flex items-center gap-1.5 text-[#A39C91]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#C8962A]"></span>
            SYSTEM SPEC (TARGET: 2 NODES · STANDBY)
          </span>
          <span className="hidden sm:inline text-[#706A61]">|</span>
          <span className="hidden md:inline text-[#A39C91]">
            DISTRIBUTED LOCKS: SPEC DEFINED
          </span>
        </div>
        <div className="flex items-center space-x-3 text-[11px]">
          <span className="text-[#C8962A] flex items-center gap-1">
            <Info className="w-3 h-3 text-[#C8962A]" />
            <span>UI PREVIEW · REAL TELEMETRY CONNECTS IN F5</span>
          </span>
          <span className="bg-[#26221C] px-2 py-0.5 rounded text-[#E8472B] border border-[#3E372E]">
            YUKTIK 2026
          </span>
        </div>
      </div>

      {/* Main navigation header */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div 
          onClick={() => onNavigate('landing')}
          className="cursor-pointer flex items-center gap-3 group"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter') onNavigate('landing'); }}
        >
          <div className="w-10 h-10 rounded-sm bg-[#E8472B] flex items-center justify-center text-white shadow-md group-hover:bg-[#C23A20] transition-colors">
            <Ticket className="w-5 h-5 transform -rotate-12" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-editorial text-2xl font-bold tracking-tight text-[#15130F]">
                Seat<span className="text-[#E8472B] italic font-normal">Surge</span>
              </span>
              <span className="text-[10px] font-mono tracking-widest uppercase bg-[#EAE3D6] text-[#4A453D] px-1.5 py-0.5 rounded border border-[#D8CEBF]">
                BOX OFFICE
              </span>
            </div>
            <p className="text-[11px] text-[#4A453D] tracking-wide font-sans">
              High-Concurrency Real-Time Ticketing Engine
            </p>
          </div>
        </div>

        {/* View / Navigation Switcher with URL hash integration */}
        <nav className="flex items-center gap-1 bg-[#EAE3D6] p-1 rounded-lg border border-[#D8CEBF]" aria-label="Main Navigation">
          <button
            onClick={() => onNavigate('landing')}
            className={`px-3.5 py-1.5 rounded text-xs font-medium transition-all ${
              activeRoute === 'landing'
                ? 'bg-[#15130F] text-[#F4EFE6] shadow-sm'
                : 'text-[#4A453D] hover:text-[#15130F] hover:bg-[#F4EFE6]/60'
            }`}
          >
            Event Details
          </button>
          <button
            onClick={() => onNavigate('queue')}
            className={`px-3.5 py-1.5 rounded text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeRoute === 'queue'
                ? 'bg-[#15130F] text-[#F4EFE6] shadow-sm'
                : 'text-[#4A453D] hover:text-[#15130F] hover:bg-[#F4EFE6]/60'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            Waiting Room
          </button>
          <button
            onClick={() => onNavigate('seats')}
            className={`px-3.5 py-1.5 rounded text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeRoute === 'seats'
                ? 'bg-[#15130F] text-[#F4EFE6] shadow-sm'
                : 'text-[#4A453D] hover:text-[#15130F] hover:bg-[#F4EFE6]/60'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Live Seat Map
          </button>
          <button
            onClick={() => onNavigate('checkout')}
            className={`px-3.5 py-1.5 rounded text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeRoute === 'checkout'
                ? 'bg-[#15130F] text-[#F4EFE6] shadow-sm'
                : 'text-[#4A453D] hover:text-[#15130F] hover:bg-[#F4EFE6]/60'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Checkout
          </button>
        </nav>
      </div>
    </header>
  );
}
