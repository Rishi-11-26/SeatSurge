import React, { useState, useEffect } from 'react';
import { Ticket, ShieldCheck, Activity, Users, Info, Radio, Database, Server } from 'lucide-react';
import { getHealthStatus } from '../../services/api';

export default function Navbar({ activeRoute, onNavigate }) {
  const [health, setHealth] = useState({
    checked: false,
    online: false,
    instanceId: null,
    dbStatus: 'UNAVAILABLE',
    redisStatus: 'UNAVAILABLE',
  });

  // Probe real backend health telemetry on mount and interval
  useEffect(() => {
    let isMounted = true;

    async function checkHealth() {
      try {
        const data = await getHealthStatus();
        if (!isMounted) return;

        if (data && typeof data === 'object') {
          // Backend replica instance ID (only when explicitly reported by backend)
          const instanceId = data.instance_id || 'UNKNOWN';

          // Extract database status strictly from response — never infer
          let dbStatus = 'UNKNOWN';
          if (data.services?.database?.status) {
            dbStatus = data.services.database.status === 'healthy' ? 'HEALTHY' : 'UNREACHABLE';
          } else if (typeof data.database === 'boolean') {
            dbStatus = data.database ? 'HEALTHY' : 'UNREACHABLE';
          }

          // Extract Redis status strictly from response — never infer from general backend
          let redisStatus = 'UNKNOWN';
          if (data.services?.redis?.status) {
            redisStatus = data.services.redis.status === 'healthy' ? 'HEALTHY' : 'UNREACHABLE';
          } else if (typeof data.redis === 'boolean') {
            redisStatus = data.redis ? 'HEALTHY' : 'UNREACHABLE';
          }

          setHealth({
            checked: true,
            online: data.status === 'ok' || data.status === 'degraded',
            instanceId,
            dbStatus,
            redisStatus,
          });
          return;
        }
      } catch {
        // Network gateway offline or unreachable
      }

      if (!isMounted) return;
      setHealth({
        checked: true,
        online: false,
        instanceId: null,
        dbStatus: 'UNAVAILABLE',
        redisStatus: 'UNAVAILABLE',
      });
    }

    checkHealth();
    const interval = setInterval(checkHealth, 20000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="border-b border-[#D8CEBF] bg-[#F4EFE6]/90 backdrop-blur-md sticky top-0 z-50">
      {/* Top micro-bar: Verified Backend Telemetry & Status */}
      <div className="bg-[#15130F] text-[#EAE3D6] px-4 py-1.5 text-xs font-mono flex flex-wrap items-center justify-between gap-2 border-b border-[#2A2620]">
        <div className="flex items-center space-x-3 text-[11px]">
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${health.online ? 'bg-[#3F6B4F] animate-pulse' : 'bg-[#C8962A]'}`}></span>
            {health.online ? (
              <span className="text-[#3F6B4F] font-bold">
                BACKEND: ONLINE ({health.instanceId})
              </span>
            ) : (
              <span className="text-[#A39C91]">
                BACKEND: UNAVAILABLE (GATEWAY :8000)
              </span>
            )}
          </span>

          <span className="hidden sm:inline text-[#706A61]">|</span>
          <span className="hidden sm:inline flex items-center gap-1 text-[11px]">
            <Database className="w-3 h-3 text-[#706A61]" />
            <span className="text-[#706A61]">DB:</span>
            <span className={health.dbStatus === 'HEALTHY' ? 'text-[#3F6B4F] font-bold' : health.dbStatus === 'UNREACHABLE' ? 'text-[#E8472B]' : 'text-[#A39C91]'}>
              {health.dbStatus}
            </span>
          </span>

          <span className="hidden md:inline text-[#706A61]">|</span>
          <span className="hidden md:inline flex items-center gap-1 text-[11px]">
            <Server className="w-3 h-3 text-[#706A61]" />
            <span className="text-[#706A61]">REDIS:</span>
            <span className={health.redisStatus === 'HEALTHY' ? 'text-[#3F6B4F] font-bold' : health.redisStatus === 'UNREACHABLE' ? 'text-[#E8472B]' : 'text-[#A39C91]'}>
              {health.redisStatus}
            </span>
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[11px]">
          <span className="text-[#C8962A] flex items-center gap-1">
            <Info className="w-3 h-3 text-[#C8962A]" />
            <span>{health.online ? 'VERIFIED TELEMETRY' : 'INTEGRATION MODE: DUAL (REAL + DEV)'}</span>
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
