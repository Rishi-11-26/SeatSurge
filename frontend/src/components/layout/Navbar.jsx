import React, { useState } from 'react';
import { Ticket, ShieldCheck, Activity, Users, Menu, X } from 'lucide-react';

export default function Navbar({ activeRoute, onNavigate }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const navItems = [
    { id: 'landing',  label: 'Event Details', icon: null },
    { id: 'queue',    label: 'Waiting Room',  icon: Users },
    { id: 'seats',    label: 'Seat Map',      icon: Activity },
    { id: 'checkout', label: 'Checkout',      icon: ShieldCheck },
  ];

  return (
    <header className="border-b border-[#D8CEBF] bg-[#F4EFE6]/95 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between gap-4">

        {/* Brand */}
        <div
          onClick={() => onNavigate('landing')}
          className="cursor-pointer flex items-center gap-3 group flex-shrink-0"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter') onNavigate('landing'); }}
        >
          <div className="w-9 h-9 rounded-sm bg-[#E8472B] flex items-center justify-center text-white shadow-md group-hover:bg-[#C23A20] transition-colors">
            <Ticket className="w-5 h-5 transform -rotate-12" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-editorial text-xl sm:text-2xl font-bold tracking-tight text-[#15130F]">
                Seat<span className="text-[#E8472B] italic font-normal">Surge</span>
              </span>
              <span className="hidden sm:inline text-[10px] font-mono tracking-widest uppercase bg-[#EAE3D6] text-[#4A453D] px-1.5 py-0.5 rounded border border-[#D8CEBF]">
                BOX OFFICE
              </span>
            </div>
            <p className="hidden sm:block text-[11px] text-[#4A453D] tracking-wide font-sans">
              Real-Time Ticketing Platform
            </p>
          </div>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1 bg-[#EAE3D6] p-1 rounded-lg border border-[#D8CEBF]" aria-label="Main Navigation">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`px-3.5 py-1.5 rounded text-xs font-medium transition-all flex items-center gap-1.5 ${
                activeRoute === id
                  ? 'bg-[#15130F] text-[#F4EFE6] shadow-sm'
                  : 'text-[#4A453D] hover:text-[#15130F] hover:bg-[#F4EFE6]/60'
              }`}
            >
              {Icon && <Icon className="w-3.5 h-3.5" />}
              {label}
            </button>
          ))}
        </nav>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 rounded text-[#4A453D] hover:bg-[#EAE3D6] transition-colors"
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden border-t border-[#D8CEBF] bg-[#F4EFE6] px-4 pb-4 pt-2 flex flex-col gap-1">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { onNavigate(id); setMenuOpen(false); }}
              className={`w-full text-left px-4 py-3 rounded text-sm font-medium transition-all flex items-center gap-2.5 ${
                activeRoute === id
                  ? 'bg-[#15130F] text-[#F4EFE6]'
                  : 'text-[#4A453D] hover:bg-[#EAE3D6]'
              }`}
            >
              {Icon && <Icon className="w-4 h-4" />}
              {label}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}
