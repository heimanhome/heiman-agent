import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Filter, AlertTriangle, CheckCircle, CheckCheck, Square, CheckSquare } from 'lucide-react';
import { EventCard } from '../components/EventCard';
import { useAppStore } from '../store';
import type { EventType, EventLevel } from '../types';

const eventTypes: EventType[] = ['alarm', 'warning', 'info'];
const eventLevels: EventLevel[] = ['critical', 'high', 'medium', 'low', 'warning', 'info'];

export function Events() {
  const { t } = useTranslation('app');
  const { events, loading, fetchEvents, fetchHomes, currentHomeId } = useAppStore();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<EventType | 'all'>('all');
  const [filterLevel, setFilterLevel] = useState<EventLevel | 'all'>('all');
  const [filterAcknowledged, setFilterAcknowledged] = useState<'all' | 'yes' | 'no'>('all');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchHomes();
  }, [fetchHomes]);

  useEffect(() => {
    if (currentHomeId) {
      fetchEvents();
    }
  }, [currentHomeId, fetchEvents]);

  const filteredEvents = events.filter((event) => {
    const matchesSearch = (event.message || '').toLowerCase().includes(search.toLowerCase()) ||
      (event.did || '').toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || event.event_type === filterType;
    const matchesLevel = filterLevel === 'all' || event.level === filterLevel;
    const matchesAcknowledged = filterAcknowledged === 'all' ||
      (filterAcknowledged === 'yes' && event.acknowledged) ||
      (filterAcknowledged === 'no' && !event.acknowledged);
    return matchesSearch && matchesType && matchesLevel && matchesAcknowledged;
  });

  const unacknowledgedCount = events.filter((e) => !e.acknowledged).length;
  const unackSelectedIds = filteredEvents
    .filter((e) => !e.acknowledged && selectedIds.has(e.event_id))
    .map((e) => e.event_id);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const unackIds = filteredEvents.filter((e) => !e.acknowledged).map((e) => e.event_id);
    if (unackIds.every((id) => selectedIds.has(id))) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        unackIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        unackIds.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const handleBatchAcknowledge = async () => {
    if (unackSelectedIds.length === 0) return;
    await useAppStore.getState().batchAcknowledgeEvents(unackSelectedIds);
    setSelectedIds(new Set());
  };

  const allUnackSelected = filteredEvents.filter((e) => !e.acknowledged).length > 0 &&
    filteredEvents.filter((e) => !e.acknowledged).every((e) => selectedIds.has(e.event_id));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{t('events')}</h1>
          <p className="text-sm text-[#6b7a9a]">{t('manageEvents')}</p>
        </div>
        <div className="flex items-center gap-3">
          {unackSelectedIds.length > 0 && (
            <button
              onClick={handleBatchAcknowledge}
              className="flex items-center gap-2 px-4 py-2 bg-[#00ff88] text-[#0a0e1a] rounded-xl text-sm font-medium hover:bg-[#00ff88]/80 transition-colors"
            >
              <CheckCheck className="w-4 h-4" />
              {t('batchAcknowledge')} ({unackSelectedIds.length})
            </button>
          )}
          {unacknowledgedCount > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 bg-[#ff4757]/10 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-[#ff4757]" />
              <span className="text-sm text-[#ff4757] font-medium">{t('unacknowledgedCount', { count: unacknowledgedCount })}</span>
            </div>
          )}
        </div>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-4 border border-white/5">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
            <input
              type="text"
              placeholder={t('searchEvent')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
            />
          </div>
          <div className="flex gap-4">
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as EventType | 'all')}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allTypes')}</option>
                {eventTypes.map((type) => (
                  <option key={type} value={type}>{t(`eventTypeLabels.${type}`)}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
              <select
                value={filterLevel}
                onChange={(e) => setFilterLevel(e.target.value as EventLevel | 'all')}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allLevels')}</option>
                {eventLevels.map((level) => (
                  <option key={level} value={level}>{t(`eventLevelLabels.${level}`)}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
              <select
                value={filterAcknowledged}
                onChange={(e) => setFilterAcknowledged(e.target.value as 'all' | 'yes' | 'no')}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('all')}</option>
                <option value="no">{t('pending')}</option>
                <option value="yes">{t('acknowledged')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {loading.events ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="bg-[#0f2137] rounded-xl p-4 border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="bg-[#0f2137] rounded-xl p-12 text-center border border-white/5">
          <CheckCircle className="w-12 h-12 text-[#00ff88] mx-auto mb-4" />
          <p className="text-white mb-2">{t('noEventRecords')}</p>
          <p className="text-sm text-[#6b7a9a]">{t('systemNormal')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3 px-2">
            <button
              onClick={toggleSelectAll}
              className="flex items-center gap-2 text-sm text-[#6b7a9a] hover:text-white transition-colors"
            >
              {allUnackSelected ? (
                <CheckSquare className="w-4 h-4 text-[#00d4ff]" />
              ) : (
                <Square className="w-4 h-4" />
              )}
              {t('selectAllPending')}
            </button>
          </div>
          {filteredEvents.map((event) => (
            <div key={event.event_id} className="flex items-start gap-3">
              {!event.acknowledged && (
                <button
                  onClick={() => toggleSelect(event.event_id)}
                  className="mt-4 flex-shrink-0"
                >
                  {selectedIds.has(event.event_id) ? (
                    <CheckSquare className="w-5 h-5 text-[#00d4ff]" />
                  ) : (
                    <Square className="w-5 h-5 text-[#6b7a9a] hover:text-white" />
                  )}
                </button>
              )}
              <div className="flex-1">
                <EventCard
                  event={event}
                  onAcknowledge={() => useAppStore.getState().acknowledgeEvent(event.event_id)}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
