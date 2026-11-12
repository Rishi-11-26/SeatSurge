import React, { useState } from 'react';
import { Search, Calendar, MapPin, ArrowRight } from 'lucide-react';
import { DISCOVERY_EVENTS } from '../../services/eventService';

export default function EventDiscovery({ onSelectEvent, onNavigate }) {
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  const categories = ['All', 'Concert', 'Sports', 'Theatre'];

  const filteredEvents = DISCOVERY_EVENTS.filter(evt => {
    const matchesCategory = selectedCategory === 'All' || evt.category.toLowerCase() === selectedCategory.toLowerCase();
    const matchesQuery = evt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         evt.headline?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         evt.venue.city.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesQuery;
  });

  return (
    <section className="py-12 bg-[#F4EFE6]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Header & Controls */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-[#D8CEBF] pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
                EVENT DISCOVERY & SHOWCASE CATALOGUE
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#EAE3D6] text-[#706A61] border border-[#D8CEBF]">
                EVENT #1 AUTHORITATIVE · OTHERS ARE DEV MOCKS
              </span>
            </div>
            <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F] mt-1">
              Upcoming Stadium & Arena Shows
            </h2>
            <p className="text-sm text-[#4A453D] mt-1">
              Explore the primary flash-sale event alongside developmental mock events for discovery prototyping.
            </p>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 text-[#706A61] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search event, artist, city..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-2 bg-[#EAE3D6] border border-[#D8CEBF] rounded text-xs text-[#15130F] placeholder-[#706A61] focus:outline-none focus:border-[#15130F] font-sans w-full sm:w-64"
              />
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1 bg-[#EAE3D6] p-1 rounded border border-[#D8CEBF]">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded text-xs font-mono transition-all ${
                    selectedCategory === cat
                      ? 'bg-[#15130F] text-[#F4EFE6] font-semibold'
                      : 'text-[#4A453D] hover:text-[#15130F]'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Events Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEvents.map((event) => {
            const isLive = event.id === 1;
            return (
              <div
                key={event.id}
                className={`bg-[#EAE3D6] border-2 rounded-lg p-5 flex flex-col justify-between transition-all shadow-sm ${
                  isLive 
                    ? 'border-[#E8472B] shadow-ticket' 
                    : 'border-[#D8CEBF] hover:border-[#15130F]'
                }`}
              >
                <div className="space-y-4">
                  {/* Status Strip */}
                  <div className="flex items-center justify-between">
                    {isLive ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#E8472B] text-white text-[11px] font-mono font-bold tracking-wider">
                        <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping"></span>
                        AUTHORITATIVE SALE (EVENT #1)
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-[#D8CEBF] text-[#4A453D] text-[10px] font-mono font-bold">
                        DEV MOCK · {event.status}
                      </span>
                    )}

                    <span className="text-[11px] font-mono text-[#706A61]">
                      {event.category}
                    </span>
                  </div>

                  <div>
                    <h3 className="font-editorial text-xl font-bold text-[#15130F] leading-tight">
                      {event.title}
                    </h3>
                    <p className="text-xs text-[#4A453D] mt-1 font-serif italic">
                      {event.headline}
                    </p>
                  </div>

                  {/* Metadata */}
                  <div className="space-y-1.5 text-xs font-mono text-[#4A453D] pt-2 border-t border-[#D8CEBF]">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-[#C8962A]" />
                      <span>{event.dateFormatted} · {event.time}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-[#E8472B]" />
                      <span>{event.venue.name}, {event.venue.city}</span>
                    </div>
                    <div className="flex items-center justify-between pt-1 text-[11px] text-[#706A61]">
                      <span>CAPACITY: {event.totalSeats?.toLocaleString()} SEATS</span>
                      <span className="font-bold text-[#15130F]">{event.priceRange || '3,500¢ – 15,000¢'}</span>
                    </div>
                  </div>
                </div>

                {/* Bottom Action */}
                <div className="pt-5 mt-4 border-t border-[#D8CEBF]">
                  {isLive ? (
                    <button
                      onClick={() => onNavigate('queue')}
                      className="w-full py-2.5 bg-[#E8472B] hover:bg-[#C23A20] text-white rounded font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-sm"
                    >
                      <span>Enter Waiting Room</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      onClick={() => onNavigate('landing')}
                      className="w-full py-2.5 bg-[#F4EFE6] hover:bg-[#EAE3D6] text-[#4A453D] border border-[#C5BCAD] rounded font-mono text-xs font-medium uppercase tracking-wider flex items-center justify-center gap-2 transition-all"
                    >
                      <span>Dev Mock Preview Only</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
