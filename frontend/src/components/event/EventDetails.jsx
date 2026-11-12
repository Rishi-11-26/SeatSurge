import React from 'react';
import { Clock, Shield, Sparkles, AlertCircle, FileText, CheckCircle } from 'lucide-react';

export default function EventDetails({ event }) {
  return (
    <section className="py-12 border-b border-[#D8CEBF] bg-[#F4EFE6]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        
        {/* Section Header */}
        <div>
          <span className="text-xs font-mono uppercase tracking-widest text-[#E8472B] font-semibold">
            PROGRAMME & TIMETABLE
          </span>
          <h2 className="font-editorial text-3xl sm:text-4xl font-bold text-[#15130F] mt-1">
            Evening Schedule & Venue Policies
          </h2>
          <p className="text-sm text-[#4A453D] mt-1 max-w-xl">
            Everything you need to know about show timings, arena security protocols, and booking mechanics.
          </p>
        </div>

        {/* 2-Column Layout: Schedule & Arena Policies */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Schedule Timeline */}
          <div className="lg:col-span-6 bg-[#EAE3D6] p-6 rounded-lg border border-[#D8CEBF] space-y-4">
            <h3 className="font-editorial text-2xl font-bold text-[#15130F] flex items-center gap-2">
              <Clock className="w-5 h-5 text-[#E8472B]" /> Show Timetable (IST)
            </h3>
            <p className="text-xs text-[#706A61] font-mono">
              Times are strictly adhered to. Arrive early to complete security screening.
            </p>

            <div className="space-y-3 pt-2">
              {event.lineup.map((item, idx) => (
                <div 
                  key={idx}
                  className="bg-[#F4EFE6] p-3.5 rounded border border-[#D8CEBF] flex items-center gap-4 text-xs font-mono"
                >
                  <span className="w-16 font-bold text-sm text-[#E8472B] flex-shrink-0">
                    {item.time}
                  </span>
                  <div className="flex-grow">
                    <span className="font-bold text-[#15130F] block text-xs">
                      {item.act}
                    </span>
                    <span className="text-[11px] text-[#706A61] block">
                      {item.stage}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Arena Rules & Concurrency Policies */}
          <div className="lg:col-span-6 bg-[#EAE3D6] p-6 rounded-lg border border-[#D8CEBF] space-y-4">
            <h3 className="font-editorial text-2xl font-bold text-[#15130F] flex items-center gap-2">
              <Shield className="w-5 h-5 text-[#3F6B4F]" /> Ticketing & Entry Protocols
            </h3>
            <p className="text-xs text-[#706A61] font-mono">
              Engineered for fair access and smooth high-volume ingress.
            </p>

            <div className="space-y-3 pt-2">
              {event.policies.map((p, idx) => (
                <div 
                  key={idx}
                  className="bg-[#F4EFE6] p-3.5 rounded border border-[#D8CEBF] space-y-1"
                >
                  <div className="flex items-center gap-2 font-mono text-xs font-bold text-[#15130F]">
                    <CheckCircle className="w-3.5 h-3.5 text-[#3F6B4F] flex-shrink-0" />
                    <span>{p.title}</span>
                  </div>
                  <p className="text-xs text-[#4A453D] pl-5 leading-relaxed">
                    {p.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
