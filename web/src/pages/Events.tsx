import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Filter, AlertTriangle, CheckCircle, CheckCheck, Square, CheckSquare, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, RefreshCw, XCircle } from 'lucide-react';
import { EventCard } from '../components/EventCard';
import { useAppStore } from '../store';
import type { EventType, EventLevel, SensorEvent } from '../types';
import { eventApi } from '../api/client';

const eventTypes: EventType[] = ['alarm', 'warning', 'info'];
const eventLevels: EventLevel[] = ['critical', 'high', 'medium', 'low', 'warning', 'info'];
const pageSizeOptions = [10, 20, 50, 100];

const Pagination = ({ current, pageSize, total, onChange, onPageSizeChange }: { current: number; pageSize: number; total: number; onChange: (page: number) => void; onPageSizeChange: (size: number) => void }) => {
  const totalPages = Math.ceil(total / pageSize);
  const startIndex = (current - 1) * pageSize + 1;
  const endIndex = Math.min(current * pageSize, total);

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      if (current <= 3) {
        pages.push(1, 2, 3, 4, '...', totalPages);
      } else if (current >= totalPages - 2) {
        pages.push(1, '...', totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
      } else {
        pages.push(1, '...', current - 1, current, current + 1, '...', totalPages);
      }
    }
    return pages;
  };

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-5 py-4 bg-white/5">
      <div className="text-sm text-gray-500 dark:text-[#6b7a9a]">
        共 <span className="text-gray-900 dark:text-white font-medium">{total}</span> 条记录，
        显示第 <span className="text-gray-900 dark:text-white font-medium">{startIndex}</span> - <span className="text-gray-900 dark:text-white font-medium">{endIndex}</span> 条
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">每页</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50"
          >
            {pageSizeOptions.map(size => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
          <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">条</span>
        </div>
        <div className="flex items-center gap-1 ml-4">
          <button
            onClick={() => onChange(1)}
            disabled={current === 1}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronsLeft className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          <button
            onClick={() => onChange(current - 1)}
            disabled={current === 1}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          {getPageNumbers().map((page, index) => (
            typeof page === 'number' ? (
              <button
                key={index}
                onClick={() => onChange(page)}
                className={`w-8 h-8 rounded text-sm font-medium transition-colors ${
                  page === current
                    ? 'bg-[#00d4ff] text-[#0a1628]'
                    : 'text-gray-500 dark:text-[#6b7a9a] hover:bg-white/10'
                }`}
              >
                {page}
              </button>
            ) : (
              <span key={index} className="px-2 text-gray-500 dark:text-[#6b7a9a]">...</span>
            )
          ))}
          <button
            onClick={() => onChange(current + 1)}
            disabled={current === totalPages}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          <button
            onClick={() => onChange(totalPages)}
            disabled={current === totalPages}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronsRight className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
        </div>
      </div>
    </div>
  );
};

export function Events() {
  const { t } = useTranslation('app');
  const { currentHomeId, acknowledgeEvent, batchAcknowledgeEvents } = useAppStore();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<EventType | 'all'>('all');
  const [filterLevel, setFilterLevel] = useState<EventLevel | 'all'>('all');
  const [filterAcknowledged, setFilterAcknowledged] = useState<'all' | 'yes' | 'no'>('all');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [events, setEvents] = useState<SensorEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchEvents();
  }, [currentHomeId, page, pageSize, filterType, filterLevel, filterAcknowledged]);

  const fetchEvents = async () => {
    if (!currentHomeId) return;
    
    setLoading(true);
    setError('');
    try {
      const response = await eventApi.getAll({
        home_id: currentHomeId,
        event_type: filterType === 'all' ? undefined : filterType,
        level: filterLevel === 'all' ? undefined : filterLevel,
        acknowledged: filterAcknowledged === 'all' ? undefined : filterAcknowledged === 'yes',
        page,
        page_size: pageSize,
      });
      
      const data = response.data;
      if (data.success) {
        setEvents(data.data || []);
        setTotal(data.total || 0);
      } else {
        setError(data.message || '获取事件失败');
        setEvents([]);
        setTotal(0);
      }
    } catch (error: any) {
      console.error('Failed to fetch events:', error);
      setError(error.message || '网络错误，无法获取事件');
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const filteredEvents = events.filter((event) => {
    const matchesSearch = (event.message || '').toLowerCase().includes(search.toLowerCase()) ||
      (event.did || '').toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
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
    await batchAcknowledgeEvents(unackSelectedIds);
    setSelectedIds(new Set());
    await fetchEvents();
  };

  const handleRefresh = () => {
    setPage(1);
    fetchEvents();
  };

  const handleSearch = () => {
    setPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  const allUnackSelected = filteredEvents.filter((e) => !e.acknowledged).length > 0 &&
    filteredEvents.filter((e) => !e.acknowledged).every((e) => selectedIds.has(e.event_id));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('events')}</h1>
          <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('manageEvents')}</p>
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
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-gray-900 dark:text-white hover:bg-white/10 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            {t('refresh')}
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#0f2137] rounded-xl p-4 border border-gray-200 dark:border-white/5">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
            <input
              type="text"
              placeholder={t('searchEvent')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-900 dark:text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
            />
          </div>
          <div className="flex flex-wrap gap-4">
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
              <select
                value={filterType}
                onChange={(e) => {
                  setFilterType(e.target.value as EventType | 'all');
                  setPage(1);
                }}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allTypes')}</option>
                {eventTypes.map((type) => (
                  <option key={type} value={type}>{t(`eventTypeLabels.${type}`)}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
              <select
                value={filterLevel}
                onChange={(e) => {
                  setFilterLevel(e.target.value as EventLevel | 'all');
                  setPage(1);
                }}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allLevels')}</option>
                {eventLevels.map((level) => (
                  <option key={level} value={level}>{t(`eventLevelLabels.${level}`)}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
              <select
                value={filterAcknowledged}
                onChange={(e) => {
                  setFilterAcknowledged(e.target.value as 'all' | 'yes' | 'no');
                  setPage(1);
                }}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('all')}</option>
                <option value="no">{t('pending')}</option>
                <option value="yes">{t('acknowledged')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-[#0f2137] rounded-xl border border-gray-200 dark:border-white/5 overflow-hidden">
        {loading ? (
          <div className="space-y-3 p-6">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-white/5 dark:bg-white/5 rounded-xl p-4 animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <XCircle className="w-12 h-12 text-[#ff4757] mx-auto mb-4" />
            <p className="text-[#ff4757] mb-2">{error}</p>
            <button
              onClick={handleRefresh}
              className="mt-3 px-4 py-2 bg-[#00d4ff]/10 text-[#00d4ff] rounded-lg text-sm hover:bg-[#00d4ff]/20 transition-colors"
            >
              重试
            </button>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle className="w-12 h-12 text-[#00ff88] mx-auto mb-4" />
            <p className="text-gray-900 dark:text-white mb-2">{t('noEventRecords')}</p>
            <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('systemNormal')}</p>
          </div>
        ) : (
          <>
            <div className="space-y-3 p-3">
              <div className="flex items-center gap-3 px-2">
                <button
                  onClick={toggleSelectAll}
                  className="flex items-center gap-2 text-sm text-gray-500 dark:text-[#6b7a9a] hover:text-gray-900 dark:text-white transition-colors"
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
                        <Square className="w-5 h-5 text-gray-500 dark:text-[#6b7a9a] hover:text-gray-900 dark:text-white" />
                      )}
                    </button>
                  )}
                  <div className="flex-1">
                    <EventCard
                      event={event}
                      onAcknowledge={() => {
                        acknowledgeEvent(event.event_id);
                        fetchEvents();
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              onChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </>
        )}
      </div>
    </div>
  );
}