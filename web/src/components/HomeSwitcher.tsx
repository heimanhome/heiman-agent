import { useState, useRef, useEffect } from 'react';
import { Home, ChevronDown, Loader2 } from 'lucide-react';
import { useAppStore } from '../store';
import type { HomeData } from '../api/client';

export function HomeSwitcher() {
  const { homes, currentHomeId, fetchHomes, switchHome, loading } = useAppStore();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentHome = homes.find((h) => h.id === currentHomeId) || homes[0];

  useEffect(() => {
    if (homes.length === 0) {
      fetchHomes();
    }
  }, [fetchHomes, homes.length]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSwitch = async (home: HomeData) => {
    setOpen(false);
    if (home.id !== currentHomeId) {
      await switchHome(home.id);
    }
  };

  if (loading.homes && homes.length === 0) {
    return (
      <div className="flex items-center gap-2 text-[#6b7a9a]">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Loading...</span>
      </div>
    );
  }

  if (homes.length === 0) {
    return null;
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors text-white min-w-0 max-w-[240px]"
      >
        <Home className="w-4 h-4 shrink-0 text-[#00d4ff]" />
        <span className="text-sm font-medium truncate">
          {currentHome?.name || 'Select Home'}
        </span>
        <ChevronDown className={`w-4 h-4 shrink-0 text-[#6b7a9a] transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-[#0f2137] border border-[#1e3a5f] rounded-xl shadow-xl z-50 overflow-hidden">
          <div className="p-2 max-h-80 overflow-y-auto">
            {homes.map((home) => (
              <button
                key={home.id}
                onClick={() => handleSwitch(home)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                  home.id === currentHomeId
                    ? 'bg-[#00d4ff]/10 text-[#00d4ff]'
                    : 'text-white hover:bg-white/10'
                }`}
              >
                <Home className="w-4 h-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{home.name}</div>
                  <div className="text-xs text-[#6b7a9a] truncate">{home.address}</div>
                </div>
                {home.id === currentHomeId && (
                  <div className="w-2 h-2 rounded-full bg-[#00d4ff]" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
