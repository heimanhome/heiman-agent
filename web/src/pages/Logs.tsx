import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, RefreshCw, AlertTriangle, Info, XCircle, CheckCircle, Clock, Download } from 'lucide-react';
import { logApi } from '../api/client';

interface LogEntry {
  id: string;
  time: string;
  level: 'info' | 'warning' | 'error' | 'success';
  action: string;
  user: string;
  message: string;
}

const levelConfig: Record<string, { icon: typeof Info; color: string; bgColor: string; label: string }> = {
  info: { icon: Info, color: 'text-[#00d4ff]', bgColor: 'bg-[#00d4ff]/10', label: 'info' },
  warning: { icon: AlertTriangle, color: 'text-[#ffa502]', bgColor: 'bg-[#ffa502]/10', label: 'warning' },
  error: { icon: XCircle, color: 'text-[#ff4757]', bgColor: 'bg-[#ff4757]/10', label: 'error' },
  success: { icon: CheckCircle, color: 'text-[#00ff88]', bgColor: 'bg-[#00ff88]/10', label: 'success' },
};

export function Logs() {
  const { t } = useTranslation('app');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'operation' | 'error'>('operation');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, [activeTab]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      if (activeTab === 'error') {
        const response = await logApi.getErrorLogs();
        const rawData = response.data?.data || response.data || [];
        const data = Array.isArray(rawData) ? rawData : [];
        setLogs(data);
      } else {
        const response = await logApi.getAll();
        const rawData = response.data?.data || response.data || [];
        const data = Array.isArray(rawData) ? rawData : [];
        setLogs(data);
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => {
    const matchesSearch = log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.user.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesLevel = filterLevel === 'all' || log.level === filterLevel;
    const matchesTab = activeTab === 'operation' || log.level === 'error';
    return matchesSearch && matchesLevel && matchesTab;
  });

  const handleRefresh = () => {
    fetchLogs();
  };

  return (
    <div className="max-w-[1200px] w-full mx-auto px-4 md:px-8 pt-5 pb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">{t('logSystem')}</h1>
          <p className="text-sm text-[#6b7a9a]">{t('operationLogs')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white hover:bg-white/10 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            <span>{t('refresh')}</span>
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-lg hover:opacity-90 transition-opacity">
            <Download className="w-4 h-4" />
            <span>{t('export')}</span>
          </button>
        </div>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-4 border border-white/5 mb-6">
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t('searchLogs')}
              className="w-full pl-12 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50"
            />
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]/50"
            >
              <option value="all">{t('allLevels')}</option>
              <option value="info">{t('info')}</option>
              <option value="warning">{t('warning')}</option>
              <option value="error">{t('error')}</option>
              <option value="success">{t('success')}</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('operation')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'operation'
              ? 'bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30'
              : 'bg-white/5 text-[#6b7a9a] border border-transparent hover:bg-white/10'
          }`}
        >
          {t('operationLogs')}
        </button>
        <button
          onClick={() => setActiveTab('error')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'error'
              ? 'bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30'
              : 'bg-white/5 text-[#6b7a9a] border border-transparent hover:bg-white/10'
          }`}
        >
          {t('errorLogs')}
        </button>
      </div>

      <div className="bg-[#0f2137] rounded-xl border border-white/5 overflow-hidden">
        <div className="grid grid-cols-12 gap-4 px-5 py-3 bg-white/5 text-sm font-medium text-[#6b7a9a]">
          <div className="col-span-3">{t('logTime')}</div>
          <div className="col-span-1">{t('logLevel')}</div>
          <div className="col-span-2">{t('logAction')}</div>
          <div className="col-span-2">{t('logUser')}</div>
          <div className="col-span-4">{t('logMessage')}</div>
        </div>
        <div className="divide-y divide-white/5">
          {loading ? (
            <div className="px-5 py-10 text-center">
              <span className="inline-block w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
              {t('loading')}
            </div>
          ) : filteredLogs.length > 0 ? (
            filteredLogs.map((log) => {
              const config = levelConfig[log.level];
              const Icon = config.icon;
              return (
                <div key={log.id} className="grid grid-cols-12 gap-4 px-5 py-3 hover:bg-white/5 transition-colors">
                  <div className="col-span-3 flex items-center gap-2 text-sm text-[#6b7a9a]">
                    <Clock className="w-4 h-4" />
                    <span>{log.time}</span>
                  </div>
                  <div className="col-span-1">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${config.bgColor} ${config.color}`}>
                      <Icon className="w-3 h-3" />
                      {t(config.label)}
                    </span>
                  </div>
                  <div className="col-span-2 text-sm text-white">{log.action}</div>
                  <div className="col-span-2 text-sm text-[#6b7a9a]">{log.user}</div>
                  <div className="col-span-4 text-sm text-white truncate">{log.message}</div>
                </div>
              );
            })
          ) : (
            <div className="px-5 py-10 text-center">
              <Info className="w-10 h-10 text-[#6b7a9a] mx-auto mb-3" />
              <p className="text-white text-sm mb-1">{t('noData')}</p>
              <p className="text-xs text-[#6b7a9a]">{t('adjustFilter')}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
