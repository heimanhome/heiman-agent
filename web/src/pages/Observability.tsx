import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Activity, Cpu, MemoryStick, HardDrive, Loader2, RefreshCw, Clock, Zap, Eye, AlertCircle, CheckCircle, Brain, CreditCard, TrendingUp, Home, Leaf, Shield, X } from 'lucide-react';
import { observabilityApi, aiApi, type ObservabilityOverview, type TraceRecord, type AgentRun, type AIAnalysisResult, type AlertAnalysisResult, type TokenQuotaStatus, type TokenDailyData, type SmartHomeAssistantResponse, type EnergyStats, type EnergyReport, type EnergyOptimization, type PrivacyStatus, type TraceDevice, type PaginatedData } from '../api/client';

const ALERT_TYPE_LABELS: Record<string, string> = {
  smoke: 'Smoke / 烟雾',
  co: 'CO / 一氧化碳',
  water_leak: 'Water Leak / 漏水',
  tamper: 'Tamper / 拆动',
  temperature_high: 'High Temp / 高温',
  device_offline: 'Device Offline / 设备离线',
  door_sensor: 'Door Sensor / 门磁',
  motion: 'Motion / 移动',
  general: 'General / 通用',
};

export function Observability() {
  const { t } = useTranslation('app');
  const [overview, setOverview] = useState<ObservabilityOverview | null>(null);
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'traces' | 'agentRuns' | 'aiAnalysis' | 'tokenUsage' | 'energyManagement' | 'aiAssistant' | 'alertAnalysis'>('overview');
  const [aiAnalysisResults, setAiAnalysisResults] = useState<AIAnalysisResult[]>([]);
  const [tokenQuota, setTokenQuota] = useState<TokenQuotaStatus | null>(null);
  const [tokenDailyData, setTokenDailyData] = useState<TokenDailyData[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [assistantData, setAssistantData] = useState<SmartHomeAssistantResponse | null>(null);
  const [energyStats, setEnergyStats] = useState<EnergyStats | null>(null);
  const [energyReport, setEnergyReport] = useState<EnergyReport | null>(null);
  const [energyOptimization, setEnergyOptimization] = useState<EnergyOptimization | null>(null);
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<{ cycle: TraceRecord; devices: TraceDevice[] } | null>(null);
  const [traceDetailLoading, setTraceDetailLoading] = useState(false);
  const [expandedAiResults, setExpandedAiResults] = useState<Set<string>>(new Set());
  // 分页状态
  const [tracesPage, setTracesPage] = useState(1);
  const [tracesTotalPages, setTracesTotalPages] = useState(1);
  const [aiAnalysisPage, setAiAnalysisPage] = useState(1);
  const [aiAnalysisTotalPages, setAiAnalysisTotalPages] = useState(1);
  const [totalAiAnalyses, setTotalAiAnalyses] = useState(0);
  const [assistantActionsPage, setAssistantActionsPage] = useState(1);
  const [assistantActionsTotalPages, setAssistantActionsTotalPages] = useState(1);
  const [assistantActionsTotal, setAssistantActionsTotal] = useState(0);
  // 告警分析状态
  const [alertAnalyses, setAlertAnalyses] = useState<AlertAnalysisResult[]>([]);
  const [alertAnalysesPage, setAlertAnalysesPage] = useState(1);
  const [alertAnalysesTotalPages, setAlertAnalysesTotalPages] = useState(1);
  const [alertAnalysesTotal, setAlertAnalysesTotal] = useState(0);
  const [alertAnalysesLoading, setAlertAnalysesLoading] = useState(false);
  const [alertFilter, setAlertFilter] = useState<{ alert_type?: string; urgency_level?: string }>({});
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
  const [selectedAlertDetail, setSelectedAlertDetail] = useState<AlertAnalysisResult | null>(null);
  const [alertDetailLoading, setAlertDetailLoading] = useState(false);
  const alertPageSize = 15;
  const PAGE_SIZE = 20;
  const ASSISTANT_PAGE_SIZE = 10;

  const toggleAiResult = (analysisId: string) => {
    setExpandedAiResults(prev => {
      const next = new Set(prev);
      if (next.has(analysisId)) next.delete(analysisId);
      else next.add(analysisId);
      return next;
    });
  };

  const loadTraceDetail = async (traceId: string) => {
    setSelectedTraceId(traceId);
    setTraceDetailLoading(true);
    try {
      const r = await observabilityApi.getTrace(traceId);
      setTraceDetail(r.data.data || null);
    } catch (e) {
      console.error('Failed to load trace detail:', e);
      setTraceDetail(null);
    } finally {
      setTraceDetailLoading(false);
    }
  };

  const closeTraceDetail = () => {
    setSelectedTraceId(null);
    setTraceDetail(null);
  };

  const loadOverview = async () => {
    try {
      const r = await observabilityApi.getOverview();
      setOverview(r.data.data || null);
    } catch (e) {
      console.error('Failed to load overview:', e);
    }
  };

  const loadTraces = async (page: number = 1) => {
    try {
      const r = await observabilityApi.getTraces({ page, page_size: PAGE_SIZE });
      const data = r.data.data;
      if (data && typeof data === 'object' && 'items' in data) {
        setTraces(data.items || []);
        setTracesPage(data.page || 1);
        setTracesTotalPages(data.total_pages || 1);
      } else {
        setTraces(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Failed to load traces:', e);
    }
  };

  const loadAgentRuns = async () => {
    try {
      const r = await observabilityApi.getAgentRuns({ limit: 20 });
      setAgentRuns(Array.isArray(r.data.data) ? r.data.data : []);
    } catch (e) {
      console.error('Failed to load agent runs:', e);
    }
  };

  const loadAiAnalysis = async (page: number = 1) => {
    try {
      const r = await aiApi.getAnalysisResults({ page, page_size: PAGE_SIZE });
      const data = r.data.data;
      if (data && typeof data === 'object' && 'items' in data) {
        const paginated = data as PaginatedData<AIAnalysisResult>;
        setAiAnalysisResults(paginated.items || []);
        setAiAnalysisPage(paginated.page || 1);
        setAiAnalysisTotalPages(paginated.total_pages || 1);
        setTotalAiAnalyses(paginated.total || 0);
      } else if (data && typeof data === 'object' && 'results' in data) {
        // 兼容旧格式
        const legacy = data as Record<string, any>;
        setAiAnalysisResults(legacy.results || []);
        setTotalAiAnalyses(legacy.count || 0);
      }
    } catch (e) {
      console.error('Failed to load AI analysis results:', e);
    }
  };


  const loadTokenData = async () => {
    try {
      const quotaRes = await aiApi.getTokenQuota();
      setTokenQuota(quotaRes.data.data || null);

      const dailyRes = await aiApi.getTokenDailyUsage();
      setTokenDailyData(dailyRes.data.data?.daily_data || []);
    } catch (e) {
      console.error('Failed to load token data:', e);
    }
  };

  const loadAssistantData = async (page: number = 1) => {
    try {
      const r = await aiApi.getSmartHomeAssistant({ page, page_size: ASSISTANT_PAGE_SIZE });
      setAssistantData(r.data.data || null);
      if (r.data.data) {
        setAssistantActionsPage(r.data.data.proactive_actions_page || 1);
        setAssistantActionsTotalPages(r.data.data.proactive_actions_total_pages || 1);
        setAssistantActionsTotal(r.data.data.proactive_actions_total || 0);
      }
    } catch (e) {
      console.error('Failed to load assistant data:', e);
    }
  };

  const loadEnergyData = async () => {
    try {
      const statsRes = await aiApi.getEnergyStats(7);
      setEnergyStats(statsRes.data.data || null);

      const reportRes = await aiApi.getEnergyReport(30);
      setEnergyReport(reportRes.data.data || null);

      const optRes = await aiApi.getEnergyOptimization();
      setEnergyOptimization(optRes.data.data || null);
    } catch (e) {
      console.error('Failed to load energy data:', e);
    }
  };

  const loadPrivacyStatus = async () => {
    try {
      const r = await aiApi.getPrivacyStatus();
      setPrivacyStatus(r.data.data || null);
    } catch (e) {
      console.error('Failed to load privacy status:', e);
    }
  };

  const load = async () => {
    setLoading(true);
    await loadOverview();
    await loadTraces();
    await loadAgentRuns();
    await loadAiAnalysis();
    await loadAlertAnalyses();
    await loadTokenData();
    await loadAssistantData();
    await loadEnergyData();
    await loadPrivacyStatus();
    setLoading(false);
  };

  const loadAlertAnalyses = async (page: number = 1) => {
    try {
      setAlertAnalysesLoading(true);
      const params: Record<string, any> = { page, page_size: alertPageSize };
      if (alertFilter.alert_type) params.alert_type = alertFilter.alert_type;
      if (alertFilter.urgency_level) params.urgency_level = alertFilter.urgency_level;
      const r = await aiApi.getAlertAnalyses(params);
      const data = r.data.data;
      if (data && typeof data === 'object' && 'items' in data) {
        const paginated = data as PaginatedData<AlertAnalysisResult>;
        setAlertAnalyses(paginated.items || []);
        setAlertAnalysesPage(paginated.page || 1);
        setAlertAnalysesTotalPages(paginated.total_pages || 1);
        setAlertAnalysesTotal(paginated.total || 0);
      }
    } catch (e) {
      console.error('Failed to load alert analyses:', e);
    } finally {
      setAlertAnalysesLoading(false);
    }
  };

  const openAlertDetail = async (analysisId: string) => {
    if (expandedAlert === analysisId) {
      setExpandedAlert(null);
      setSelectedAlertDetail(null);
      return;
    }
    setExpandedAlert(analysisId);
    setAlertDetailLoading(true);
    try {
      const r = await aiApi.getAlertAnalysis(analysisId);
      setSelectedAlertDetail(r.data.data || null);
    } catch (e) {
      console.error('Failed to load alert detail:', e);
    } finally {
      setAlertDetailLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  const formatTimestamp = (ts: number) => {
    const date = new Date(ts);
    return date.toLocaleString('zh-CN');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-[#00d4ff]" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6" />
            {t('observability')}
          </h1>
          <p className="text-sm text-[#6b7a9a]">{t('observabilityDescription')}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-2 rounded text-sm ${
              autoRefresh
                ? 'bg-[#00ff88] text-[#0a0e1a]'
                : 'bg-[#2a3142] text-white hover:bg-[#3a4152]'
            }`}
          >
            <RefreshCw className={`w-4 h-4 inline mr-1 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? t('autoRefresh') : t('paused')}
          </button>
          <button
            onClick={load}
            className="px-3 py-2 bg-[#2a3142] text-white rounded text-sm hover:bg-[#3a4152]"
          >
            {t('refresh')}
          </button>
        </div>
      </div>

      <div className="flex gap-2 border-b border-[#2a3142]">
        <TabButton active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>
          <Eye className="w-4 h-4" />
          {t('observability.tabs.overview')}
        </TabButton>
        <TabButton active={activeTab === 'traces'} onClick={() => setActiveTab('traces')}>
          <Zap className="w-4 h-4" />
          {t('observability.tabs.traces')}
        </TabButton>
        <TabButton active={activeTab === 'agentRuns'} onClick={() => setActiveTab('agentRuns')}>
          <Clock className="w-4 h-4" />
          {t('observability.tabs.agentRuns')}
        </TabButton>
        <TabButton active={activeTab === 'aiAnalysis'} onClick={() => setActiveTab('aiAnalysis')}>
          <Brain className="w-4 h-4" />
          {t('observability.tabs.aiAnalysis')}
        </TabButton>
        <TabButton active={activeTab === 'tokenUsage'} onClick={() => setActiveTab('tokenUsage')}>
          <CreditCard className="w-4 h-4" />
          {t('observability.tabs.tokenUsage')}
        </TabButton>
        <TabButton active={activeTab === 'energyManagement'} onClick={() => setActiveTab('energyManagement')}>
          <Leaf className="w-4 h-4" />
          {t('observability.tabs.energy')}
        </TabButton>
        <TabButton active={activeTab === 'aiAssistant'} onClick={() => setActiveTab('aiAssistant')}>
          <Home className="w-4 h-4" />
          {t('observability.tabs.aiAssistant')}
        </TabButton>
        <TabButton active={activeTab === 'alertAnalysis'} onClick={() => { setActiveTab('alertAnalysis'); loadAlertAnalyses(); }}>
          <AlertCircle className="w-4 h-4" />
          {t('observability.tabs.alertAnalysis')}
        </TabButton>
      </div>

      {activeTab === 'overview' && overview && (
        <>
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">{t('systemMetrics')}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                icon={Cpu}
                title={t('cpu')}
                value={`${(overview.system.cpu_percent ?? 0).toFixed(1)}%`}
                pct={overview.system.cpu_percent ?? 0}
                color="blue"
              />
              <MetricCard
                icon={MemoryStick}
                title={t('memory')}
                value={`${(overview.system.memory_percent ?? 0).toFixed(1)}%`}
                sub={`${(overview.system.memory_used_mb ?? 0).toFixed(0)} / ${(overview.system.memory_total_mb ?? 0).toFixed(0)} MB`}
                pct={overview.system.memory_percent ?? 0}
                color="purple"
              />
              <MetricCard
                icon={HardDrive}
                title={t('disk')}
                value={`${(overview.system.disk_percent ?? 0).toFixed(1)}%`}
                sub={`${(overview.system.disk_used_gb ?? 0).toFixed(1)} / ${(overview.system.disk_total_gb ?? 0).toFixed(1)} GB`}
                pct={overview.system.disk_percent ?? 0}
                color="green"
              />
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                <p className="text-xs text-[#6b7a9a] uppercase">{t('uptime')}</p>
                <p className="text-2xl font-bold text-white mt-2">
                  {formatUptime(overview.system.uptime_seconds)}
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">{t('dataMetrics')}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title={t('totalSensors')}
                value={overview.sensor.total_sensors}
                sub={t('dataPointsToday', { count: overview.sensor.data_points_today })}
              />
              <StatCard
                title={t('totalRules')}
                value={overview.rule.total_rules}
                sub={t('enabledCount', { count: overview.rule.enabled_rules })}
              />
              <StatCard
                title={t('totalEvents')}
                value={overview.event.total_events}
                sub={t('unacknowledged', { count: overview.event.unacknowledged })}
              />
              <StatCard
                title={t('databaseSize')}
                value={`${(overview.database.db_size_mb ?? 0).toFixed(1)} MB`}
                sub={t('tableCount', { count: overview.database.table_count })}
              />
            </div>
          </section>

          {Object.keys(overview.sensor.by_type).length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-white mb-3">{t('sensorDistribution')}</h2>
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                {Object.entries(overview.sensor.by_type).map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between py-1.5">
                    <span className="text-sm text-[#6b7a9a]">{t(`sensorLabels.${type}`) || type}</span>
                    <span className="text-sm text-white font-mono">{count}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {activeTab === 'traces' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{t('observability.tabs.traces')}</h2>
          <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0f1419]">
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.traceId')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.time')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.devices')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.cycleMs')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.pipelineMs')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.heimanCalls')}</th>
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[#6b7a9a]">
                      {t('observability.noTraces')}
                    </td>
                  </tr>
                ) : (
                  traces.map((trace) => {
                    const cycleMs = trace.cycle_total_ms ?? 0;
                    const pipelineMs = trace.pipeline_total_ms ?? 0;
                    const heimanCalls = trace.heiman_call_count ?? 0;
                    const heimanErrors = trace.heiman_error_count ?? 0;
                    return (
                      <tr
                        key={trace.trace_id}
                        className="border-t border-[#2a3142] hover:bg-[#2a3142] cursor-pointer"
                        onClick={() => loadTraceDetail(trace.trace_id)}
                      >
                        <td className="px-4 py-3">
                          <code className="text-xs text-[#00d4ff]">{(trace.trace_id || '').slice(0, 16)}...</code>
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{formatTimestamp(trace.timestamp)}</td>
                        <td className="px-4 py-3 text-sm text-white">{trace.device_count ?? 0}</td>
                        <td className="px-4 py-3 text-sm text-white">{(cycleMs ?? 0).toFixed(1)}</td>
                        <td className="px-4 py-3 text-sm text-white">{(pipelineMs ?? 0).toFixed(1)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={heimanErrors > 0 ? 'text-red-400' : 'text-green-400'}>
                            {heimanCalls}
                            {heimanErrors > 0 && ` (${heimanErrors} ${t('observability.errors')})`}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          {/* 追踪分页 */}
          {tracesTotalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => { const p = tracesPage - 1; if (p >= 1) { loadTraces(p); } }}
                disabled={tracesPage <= 1}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.prev')}
              </button>
              <span className="text-sm text-[#6b7a9a] px-3">
                {tracesPage} / {tracesTotalPages}
              </span>
              <button
                onClick={() => { const p = tracesPage + 1; if (p <= tracesTotalPages) { loadTraces(p); } }}
                disabled={tracesPage >= tracesTotalPages}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </section>
      )}

      {activeTab === 'agentRuns' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{t('observability.tabs.agentRuns')}</h2>
          <div className="space-y-3">
            {agentRuns.length === 0 ? (
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-8 text-center text-[#6b7a9a]">
                {t('observability.noAgentRuns')}
              </div>
            ) : (
              agentRuns.map((run) => {
                const isFailed = run.success === 0;
                return (
                  <div key={run.run_id} className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {isFailed ? (
                          <AlertCircle className="w-5 h-5 text-red-400" />
                        ) : (
                          <CheckCircle className="w-5 h-5 text-green-400" />
                        )}
                        <div>
                          <code className="text-sm text-white">{(run.run_id || '').slice(0, 20)}...</code>
                          <p className="text-xs text-[#6b7a9a]">{t('observability.source')}: {run.source || '-'}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-white">{formatTimestamp(run.timestamp)}</p>
                        {run.duration_ms != null && (
                          <p className="text-xs text-[#6b7a9a]">
                            {t('observability.duration')}: {((run.duration_ms ?? 0) / 1000).toFixed(1)}s
                          </p>
                        )}
                      </div>
                    </div>
                    {run.query && (
                      <div className="mt-3 text-sm text-[#6b7a9a] truncate">
                        {t('observability.query')}: {run.query}
                      </div>
                    )}
                    {run.error_msg && (
                      <div className="mt-3 p-3 bg-red-900/30 border border-red-800/50 rounded text-sm text-red-300">
                        {run.error_msg}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>
      )}

      {activeTab === 'aiAnalysis' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Brain className="w-5 h-5" />
            {t('observability.aiAnalysisResults')}
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
              <p className="text-xs text-[#6b7a9a] uppercase">{t('observability.totalAnalyses')}</p>
              <p className="text-2xl font-bold text-white mt-2">{totalAiAnalyses}</p>
            </div>
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
              <p className="text-xs text-[#6b7a9a] uppercase">{t('observability.avgAnomalyCount')}</p>
              <p className="text-2xl font-bold text-white mt-2">
                {totalAiAnalyses > 0 
                  ? ((aiAnalysisResults.reduce((sum, r) => sum + (r.anomaly_count || 0), 0) / aiAnalysisResults.length) || 0).toFixed(1)
                  : 0}
              </p>
            </div>
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
              <p className="text-xs text-[#6b7a9a] uppercase">{t('observability.avgComfortScore')}</p>
              <p className="text-2xl font-bold text-white mt-2">
                {aiAnalysisResults.filter(r => r.comfort_score !== null).length > 0 
                  ? ((aiAnalysisResults.filter(r => r.comfort_score !== null).reduce((sum, r) => sum + (r.comfort_score || 0), 0) / aiAnalysisResults.filter(r => r.comfort_score !== null).length) || 0).toFixed(1)
                  : '-'}
              </p>
            </div>
          </div>

          <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden mt-4">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0f1419]">
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('id')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('type')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.anomalies')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.comfort')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.activity')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.time')}</th>
                </tr>
              </thead>
              <tbody>
                {aiAnalysisResults.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[#6b7a9a]">
                      {t('observability.noAiAnalysis')}
                    </td>
                  </tr>
                ) : (
                  aiAnalysisResults.map((result) => (
                    <>
                      <tr
                        key={result.analysis_id}
                        className="border-t border-[#2a3142] hover:bg-[#2a3142] cursor-pointer"
                        onClick={() => toggleAiResult(result.analysis_id)}
                      >
                        <td className="px-4 py-3">
                          <code className="text-xs text-[#6b7a9a]">{(result.analysis_id || '').slice(0, 16)}...</code>
                        </td>
                        <td className="px-4 py-3 text-sm text-white">
                          {(() => {
                            const typeMap: Record<string, { key: string; dot: string }> = {
                              'event_triggered': { key: 'observability.event_triggered', dot: 'bg-red-400' },
                              'scheduled': { key: 'observability.scheduled', dot: 'bg-blue-400' },
                              'comprehensive': { key: 'observability.comprehensive', dot: 'bg-purple-400' },
                              'llm_home_advisor': { key: 'observability.llm_home_advisor', dot: 'bg-green-400' },
                            };
                            const info = typeMap[result.analysis_type] || typeMap['scheduled'];
                            return (
                              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-[#2a3142] text-white border border-[#3a4152]">
                                <span className={`w-1.5 h-1.5 rounded-full ${info.dot}`} />
                                {t(info.key)}
                              </span>
                            );
                          })()}
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{result.anomaly_count}</td>
                        <td className="px-4 py-3 text-sm text-white">
                          {result.comfort_score !== null ? `${result.comfort_score}` : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-white">
                          {result.activity_type || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{formatTimestamp(result.timestamp_ms)}</td>
                      </tr>
                      {expandedAiResults.has(result.analysis_id) && (
                        <tr key={`${result.analysis_id}-detail`} className="bg-[#1a2030]">
                          <td colSpan={6} className="px-6 py-4">
                            <div className="text-sm text-[#6b7a9a]">
                              <strong className="text-white">{t('observability.payload')}:</strong>
                              {result.result_data ? (
                                <pre className="mt-2 p-3 bg-[#0f1419] rounded text-xs text-white overflow-x-auto whitespace-pre-wrap">
                                  {JSON.stringify(result.result_data, null, 2)}
                                </pre>
                              ) : (
                                <span className="ml-2">-</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {/* AI分析结果分页 */}
          {aiAnalysisTotalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => { const p = aiAnalysisPage - 1; if (p >= 1) { loadAiAnalysis(p); } }}
                disabled={aiAnalysisPage <= 1}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.prev')}
              </button>
              <span className="text-sm text-[#6b7a9a] px-3">
                {aiAnalysisPage} / {aiAnalysisTotalPages}
              </span>
              <button
                onClick={() => { const p = aiAnalysisPage + 1; if (p <= aiAnalysisTotalPages) { loadAiAnalysis(p); } }}
                disabled={aiAnalysisPage >= aiAnalysisTotalPages}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </section>
      )}

      {activeTab === 'tokenUsage' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <CreditCard className="w-5 h-5" />
            {t('observability.tokenUsageQuota')}
          </h2>
          
          {tokenQuota && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-[#6b7a9a] uppercase">{t('observability.quotaStatus')}</p>
                  <span className={`px-2 py-1 rounded text-xs ${
                    tokenQuota.status === 'ok' ? 'bg-green-900/30 text-green-300' :
                    tokenQuota.status === 'warning' ? 'bg-yellow-900/30 text-yellow-300' :
                    'bg-red-900/30 text-red-300'
                  }`}>
                    {(tokenQuota.status || 'unknown').toUpperCase()}
                  </span>
                </div>
                <p className="text-2xl font-bold text-white">{tokenQuota.message}</p>
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-[#6b7a9a] mb-1">
                    <span>Used: {(tokenQuota.current_usage ?? 0).toLocaleString()}</span>
                    <span>Limit: {(tokenQuota.daily_limit ?? 0).toLocaleString()}</span>
                  </div>
                  <div className="h-2 bg-[#0f1419] rounded overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        tokenQuota.status === 'ok' ? 'bg-[#00ff88]' :
                        tokenQuota.status === 'warning' ? 'bg-[#fbbf24]' :
                        'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(100, tokenQuota.usage_percent)}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                <p className="text-xs text-[#6b7a9a] uppercase">{t('observability.remaining')}</p>
                <p className="text-3xl font-bold text-white mt-2">{(tokenQuota.remaining ?? 0).toLocaleString()}</p>
                <p className="text-xs text-[#6b7a9a] mt-1">{t('observability.tokensLeftToday')}</p>
                <div className="mt-3 pt-3 border-t border-[#2a3142]">
                  <p className="text-xs text-[#6b7a9a]">{t('observability.warningThreshold')}</p>
                  <p className="text-sm text-white">{((tokenQuota.warning_threshold ?? 0) * 100).toFixed(0)}%</p>
                </div>
              </div>
            </div>
          )}

          <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            {t('observability.dailyTokenUsage')}
          </h3>
          <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0f1419]">
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.date')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.prompt')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.completion')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.total.tokens')}</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.requests')}</th>
                </tr>
              </thead>
              <tbody>
                {tokenDailyData.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-[#6b7a9a]">
                      {t('observability.noTokenData')}
                    </td>
                  </tr>
                ) : (
                  tokenDailyData.map((day) => (
                    <tr key={day.date} className="border-t border-[#2a3142] hover:bg-[#2a3142]">
                      <td className="px-4 py-3 text-sm text-white">{day.date}</td>
                      <td className="px-4 py-3 text-sm text-white">{(day.prompt_tokens ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-white">{(day.completion_tokens ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm font-medium text-white">{(day.total_tokens ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-[#6b7a9a]">{day.request_count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === 'energyManagement' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Leaf className="w-5 h-5" />
            {t('observability.energyManagement')}
          </h2>

          {energyReport && (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-4">
              <StatCard
                title={t('observability.totalConsumption')}
                value={`${(energyReport.total_consumption_kwh ?? 0).toFixed(1)} kWh`}
                sub={`${energyReport.period_days} days`}
              />
              <StatCard
                title={t('observability.avgDaily')}
                value={`${(energyReport.average_daily_consumption_kwh ?? 0).toFixed(1)} kWh`}
              />
              <StatCard
                title={t('observability.peak')}
                value={`${energyReport.peak_consumption_watts} W`}
              />
              <StatCard
                title={t('observability.savings')}
                value={`${energyReport.energy_savings_pct}%`}
                sub={t('observability.comparedToBaseline')}
              />
            </div>
          )}

          {energyStats && energyStats.daily_stats.length > 0 && (
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden mb-4">
              <table className="w-full">
                <thead>
                  <tr className="bg-[#0f1419]">
                    <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.date')}</th>
                    <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.consumption')}</th>
                    <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.generation')}</th>
                    <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.peak')}</th>
                    <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">{t('observability.avg')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(energyStats.daily_stats || []).map((day) => (
                    <tr key={day.date} className="border-t border-[#2a3142] hover:bg-[#2a3142]">
                      <td className="px-4 py-3 text-sm text-white">{day.date}</td>
                      <td className="px-4 py-3 text-sm text-white">{(day.consumption_kwh ?? 0).toFixed(1)} kWh</td>
                      <td className="px-4 py-3 text-sm text-green-400">{(day.generation_kwh ?? 0).toFixed(1)} kWh</td>
                      <td className="px-4 py-3 text-sm text-white">{day.peak_watts} W</td>
                      <td className="px-4 py-3 text-sm text-[#6b7a9a]">{day.avg_watts} W</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {energyOptimization && (
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-white flex items-center gap-2">
                  <Zap className="w-4 h-4" />
                  {t('observability.optimizationRecommendations')}
                </h3>
                <span className={`px-2 py-1 rounded text-xs ${
                  energyOptimization.current_mode === 'eco' ? 'bg-green-900/30 text-green-300' : 'bg-blue-900/30 text-blue-300'
                }`}>
                  {(energyOptimization.current_mode || 'unknown').toUpperCase()} Mode
                </span>
              </div>
              <div className="space-y-3">
                {(energyOptimization.recommendations || []).map((rec, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-[#0f1419] rounded">
                    <span className={`px-2 py-1 rounded text-xs ${
                      rec.priority === 'high' ? 'bg-red-900/30 text-red-300' :
                      rec.priority === 'medium' ? 'bg-yellow-900/30 text-yellow-300' :
                      'bg-blue-900/30 text-blue-300'
                    }`}>
                      {(rec.priority || 'low').toUpperCase()}
                    </span>
                    <div>
                      <p className="text-sm text-white">{rec.description}</p>
                      <p className="text-xs text-[#6b7a9a] mt-1">
                        Estimated savings: {rec.estimated_savings_watts} W
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {activeTab === 'aiAssistant' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Home className="w-5 h-5" />
            {t('observability.aiSmartAssistant')}
          </h2>

          {assistantData && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-4">
                <StatCard
                  title={t('observability.devices')}
                  value={assistantData.device_count}
                  sub={`${assistantData.online_count} online`}
                />
                <StatCard
                  title={t('observability.activity')}
                  value={assistantData.activity?.activity_label || assistantData.activity?.activity || '-'}
                  sub={assistantData.activity?.confidence != null ? `${((assistantData.activity.confidence ?? 0) * 100).toFixed(0)}% ${t('observability.confidence')}` : ''}
                />
                <StatCard
                  title={t('observability.emotion')}
                  value={assistantData.emotion?.emotion_label || assistantData.emotion?.emotion || '-'}
                  sub={assistantData.emotion?.confidence != null ? `${((assistantData.emotion.confidence ?? 0) * 100).toFixed(0)}% ${t('observability.confidence')}` : ''}
                />
                <StatCard
                  title={t('observability.proactiveActions')}
                  value={assistantActionsTotal || assistantData.proactive_actions?.length || 0}
                />
              </div>

              {assistantData.proactive_actions && assistantData.proactive_actions.length > 0 && (
                <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4 mb-4">
                  <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <Brain className="w-4 h-4" />
                    {t('observability.recommendedActions')}
                  </h3>
                  <div className="space-y-3">
                    {(assistantData.proactive_actions || []).map((action, idx) => (
                      <div key={idx} className="flex items-start gap-3 p-3 bg-[#0f1419] rounded">
                        <span className={`px-2 py-1 rounded text-xs ${
                          action.priority === 'critical' ? 'bg-red-900/30 text-red-300' :
                          action.priority === 'high' ? 'bg-orange-900/30 text-orange-300' :
                          action.priority === 'medium' ? 'bg-yellow-900/30 text-yellow-300' :
                          'bg-blue-900/30 text-blue-300'
                        }`}>
                          {(action.priority || 'low').toUpperCase()}
                        </span>
                        <div className="flex-1">
                          <p className="text-sm text-white font-medium">{action.title}</p>
                          <p className="text-xs text-[#6b7a9a] mt-1">{action.description}</p>
                          {action.params && Object.keys(action.params).length > 0 && (
                            <div className="mt-2 p-2 bg-[#1a2030] rounded text-xs">
                              {Object.entries(action.params).map(([key, val]) => (
                                <div key={key} className="flex justify-between">
                                  <span className="text-[#6b7a9a]">{key}:</span>
                                  <span className="text-white">{String(val)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 主动操作分页 */}
              {assistantActionsTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mb-4">
                  <button
                    onClick={() => { const p = assistantActionsPage - 1; if (p >= 1) { loadAssistantData(p); } }}
                    disabled={assistantActionsPage <= 1}
                    className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {t('common.prev')}
                  </button>
                  <span className="text-sm text-[#6b7a9a] px-3">
                    {assistantActionsPage} / {assistantActionsTotalPages}
                  </span>
                  <button
                    onClick={() => { const p = assistantActionsPage + 1; if (p <= assistantActionsTotalPages) { loadAssistantData(p); } }}
                    disabled={assistantActionsPage >= assistantActionsTotalPages}
                    className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {t('common.next')}
                  </button>
                </div>
              )}

              {privacyStatus && (
                <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
                  <h3 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    {t('observability.privacyProtection')}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#6b7a9a]">{t('observability.anonymization')}</span>
                      {privacyStatus.anonymization_enabled ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#6b7a9a]">{t('observability.federatedLearning')}</span>
                      {privacyStatus.federated_learning_enabled ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#6b7a9a]">{t('observability.localProcessing')}</span>
                      {privacyStatus.local_only_processing ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#6b7a9a]">{t('observability.dataRetention')}</span>
                      <span className="text-sm text-white">{privacyStatus.data_retention_days} days</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {activeTab === 'alertAnalysis' && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-[#f97316]" />
              {t('observability.alertAnalysis.title')}
            </h2>
            <div className="flex items-center gap-2">
              {/* 类型筛选 */}
              <select
                value={alertFilter.alert_type || ''}
                onChange={(e) => { setAlertFilter(prev => ({ ...prev, alert_type: e.target.value || undefined })); }}
                className="bg-[#1a2030] border border-[#2a3142] rounded px-3 py-1.5 text-sm text-white focus:border-[#00d4ff] focus:outline-none"
              >
                <option value="">{t('observability.alertAnalysis.allTypes')}</option>
                {Object.entries(ALERT_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              {/* 紧急度筛选 */}
              <select
                value={alertFilter.urgency_level || ''}
                onChange={(e) => { setAlertFilter(prev => ({ ...prev, urgency_level: e.target.value || undefined })); }}
                className="bg-[#1a2030] border border-[#2a3142] rounded px-3 py-1.5 text-sm text-white focus:border-[#00d4ff] focus:outline-none"
              >
                <option value="">{t('observability.alertAnalysis.allUrgency')}</option>
                <option value="critical">{t('observability.alertAnalysis.urgencyCritical')}</option>
                <option value="high">{t('observability.alertAnalysis.urgencyHigh')}</option>
                <option value="medium">{t('observability.alertAnalysis.urgencyMedium')}</option>
                <option value="low">{t('observability.alertAnalysis.urgencyLow')}</option>
              </select>
              <button
                onClick={() => loadAlertAnalyses(1)}
                className="px-3 py-1.5 bg-[#00d4ff] text-[#0a0e1a] rounded text-sm font-medium hover:bg-[#00e4ff] transition-colors"
              >
                {t('common.search')}
              </button>
            </div>
          </div>

          {/* 统计概览 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard
              title={t('observability.alertAnalysis.totalAlerts')}
              value={alertAnalysesTotal}
            />
            <StatCard
              title={t('observability.alertAnalysis.criticalAlerts')}
              value={alertAnalyses.filter(a => a.urgency_level === 'critical').length}
            />
            <StatCard
              title={t('observability.alertAnalysis.highAlerts')}
              value={alertAnalyses.filter(a => a.urgency_level === 'high').length}
            />
            <StatCard
              title={t('observability.alertAnalysis.successRate')}
              value={`${alertAnalyses.length > 0 ? Math.round(alertAnalyses.filter(a => a.success).length / alertAnalyses.length * 100) : 0}%`}
            />
          </div>

          {/* 分析列表 */}
          {alertAnalysesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-[#00d4ff]" />
            </div>
          ) : alertAnalyses.length === 0 ? (
            <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-8 text-center text-[#6b7a9a]">
              {t('observability.alertAnalysis.noData')}
            </div>
          ) : (
            <div className="space-y-2">
              {alertAnalyses.map((analysis) => {
                const urgencyColor =
                  analysis.urgency_level === 'critical' ? 'text-red-400 bg-red-400/10 border-red-400/30' :
                  analysis.urgency_level === 'high' ? 'text-orange-400 bg-orange-400/10 border-orange-400/30' :
                  analysis.urgency_level === 'medium' ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30' :
                  'text-green-400 bg-green-400/10 border-green-400/30';

                return (
                  <div key={analysis.analysis_id} className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden">
                    {/* 行头部 */}
                    <button
                      onClick={() => openAlertDetail(analysis.analysis_id)}
                      className="w-full flex items-center justify-between p-4 hover:bg-[#2a3142]/50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {/* 紧急度标签 */}
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${urgencyColor}`}>
                          {analysis.urgency_level.toUpperCase()}
                        </span>
                        {/* 告警类型 */}
                        <span className="text-sm text-white font-medium truncate">
                          {ALERT_TYPE_LABELS[analysis.alert_type] || analysis.alert_type}
                        </span>
                        {/* 事件ID */}
                        <span className="text-xs text-[#6b7a9a] truncate hidden sm:inline">
                          {analysis.event_id.slice(0, 12)}...
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {analysis.success ? (
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-red-400" />
                        )}
                        <span className="text-xs text-[#6b7a9a]">
                          {formatTimestamp(analysis.created_at_ms || new Date(analysis.created_at).getTime())}
                        </span>
                      </div>
                    </button>

                    {/* 展开详情 */}
                    {expandedAlert === analysis.analysis_id && (
                      <div className="border-t border-[#2a3142] p-4 space-y-4">
                        {alertDetailLoading ? (
                          <div className="flex items-center justify-center py-6">
                            <Loader2 className="w-6 h-6 animate-spin text-[#00d4ff]" />
                          </div>
                        )                         : selectedAlertDetail ? (
                          <>
                            {/* 根因分析 */}
                            {selectedAlertDetail.root_cause && (
                              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-[#00d4ff] mb-2">
                                  {t('observability.alertAnalysis.rootCause')}
                                </h4>
                                <p className="text-sm text-white mb-2">
                                  {selectedAlertDetail.root_cause.primary_cause}
                                </p>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                                  <div>
                                    <span className="text-[#6b7a9a]">{t('observability.alertAnalysis.confidence')}: </span>
                                    <span className="text-white">{Math.round(selectedAlertDetail.root_cause.confidence * 100)}%</span>
                                  </div>
                                  <div>
                                    <span className="text-[#6b7a9a]">{t('observability.alertAnalysis.falseAlarm')}: </span>
                                    <span className={selectedAlertDetail.root_cause.is_false_alarm ? 'text-yellow-400' : 'text-green-400'}>
                                      {selectedAlertDetail.root_cause.is_false_alarm ? 'YES / 是' : 'NO / 否'}
                                    </span>
                                  </div>
                                </div>
                                {selectedAlertDetail.root_cause.contributing_factors?.length > 0 && (
                                  <div className="mt-2">
                                    <span className="text-xs text-[#6b7a9a]">{t('observability.alertAnalysis.contributingFactors')}:</span>
                                    <ul className="mt-1 space-y-0.5">
                                      {selectedAlertDetail.root_cause.contributing_factors.map((f, i) => (
                                        <li key={i} className="text-xs text-[#c0c8d8] pl-3">• {f || '(empty)'}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {selectedAlertDetail.root_cause.evidence?.length > 0 && (
                                  <div className="mt-2">
                                    <span className="text-xs text-[#6b7a9a]">{t('observability.alertAnalysis.evidence')}:</span>
                                    <ul className="mt-1 space-y-0.5">
                                      {selectedAlertDetail.root_cause.evidence.map((e, i) => (
                                        <li key={i} className="text-xs text-[#c0c8d8] pl-3">• {e || '(empty)'}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {selectedAlertDetail.root_cause.false_alarm_reason && (
                                  <div className="mt-2 text-xs">
                                    <span className="text-[#6b7a9a]">{t('observability.alertAnalysis.falseAlarmReason')}: </span>
                                    <span className="text-yellow-300">{selectedAlertDetail.root_cause.false_alarm_reason}</span>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* 影响评估 */}
                            {selectedAlertDetail.impact && (
                              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-[#f97316] mb-2">
                                  {t('observability.alertAnalysis.impact')}
                                </h4>
                                <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                                  <div>
                                    <span className="text-[#6b7a9a]">{t('observability.alertAnalysis.severity')}: </span>
                                    <span className="text-white">{selectedAlertDetail.impact.severity}</span>
                                  </div>
                                  <div>
                                    <span className="text-[#6b7a9a]">{t('observability.alertAnalysis.estimatedScope')}: </span>
                                    <span className="text-white">{selectedAlertDetail.impact.estimated_scope}</span>
                                  </div>
                                </div>
                                {selectedAlertDetail.impact.affected_rooms?.filter(r => r).length > 0 && (
                                  <div className="mb-2">
                                    <span className="text-xs text-[#6b7a9a]">{t('observability.alertAnalysis.affectedRooms')}: </span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {selectedAlertDetail.impact.affected_rooms.filter(r => r).map((room, i) => (
                                        <span key={i} className="text-xs px-2 py-0.5 bg-blue-400/10 text-blue-400 rounded-full border border-blue-400/20">
                                          {room}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {selectedAlertDetail.impact.affected_devices?.length > 0 && (
                                  <div className="mb-2">
                                    <span className="text-xs text-[#6b7a9a]">{t('observability.alertAnalysis.affectedDevices')}: </span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {selectedAlertDetail.impact.affected_devices.map((dev, i) => (
                                        <span key={i} className="text-xs px-2 py-0.5 bg-orange-400/10 text-orange-400 rounded-full border border-orange-400/20">
                                          {dev}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {selectedAlertDetail.impact.potential_consequences?.length > 0 && (
                                  <div>
                                    <span className="text-xs text-[#6b7a9a]">{t('observability.alertAnalysis.potentialConsequences')}:</span>
                                    <ul className="mt-1 space-y-0.5">
                                      {selectedAlertDetail.impact.potential_consequences.map((c, i) => (
                                        <li key={i} className="text-xs text-[#c0c8d8] pl-3">• {c || '(empty)'}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* 修复建议 */}
                            {selectedAlertDetail.remediation && selectedAlertDetail.remediation.length > 0 && (
                              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-[#00ff88] mb-2">
                                  {t('observability.alertAnalysis.remediation')}
                                </h4>
                                <div className="space-y-2">
                                  {selectedAlertDetail.remediation.map((step) => (
                                    <div key={step.step} className="bg-[#2a3142] rounded p-3 border border-[#3a4152]">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-xs px-1.5 py-0.5 rounded bg-[#00ff88]/20 text-[#00ff88] font-mono">
                                          #{step.step}
                                        </span>
                                        <span className="text-sm text-white font-medium">{step.action}</span>
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                                          step.urgency === 'immediate' ? 'bg-red-400/10 text-red-400' :
                                          step.urgency === 'short_term' ? 'bg-yellow-400/10 text-yellow-400' :
                                          'bg-blue-400/10 text-blue-400'
                                        }`}>
                                          {step.urgency}
                                        </span>
                                      </div>
                                      <p className="text-xs text-[#6b7a9a]">
                                        {t('observability.alertAnalysis.expectedOutcome')}: {step.expected_outcome}
                                      </p>
                                      {step.requires_manual_intervention && (
                                        <p className="text-xs text-yellow-400 mt-1">
                                          {t('observability.alertAnalysis.requiresManual')}
                                        </p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 建议操作 */}
                            {selectedAlertDetail.recommended_actions && selectedAlertDetail.recommended_actions.length > 0 && (
                              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-[#a78bfa] mb-2">
                                  {t('observability.alertAnalysis.recommendedActions')}
                                </h4>
                                <ul className="space-y-1">
                                  {selectedAlertDetail.recommended_actions.map((action, i) => (
                                    <li key={i} className="text-sm text-[#c0c8d8] pl-3">• {action}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* 元信息 */}
                            <div className="flex flex-wrap items-center gap-4 text-xs text-[#6b7a9a]">
                              <span>{t('observability.alertAnalysis.modelUsed')}: {selectedAlertDetail.model_used}</span>
                              {selectedAlertDetail.root_cause?.confidence != null && (
                                <span>{t('observability.alertAnalysis.confidence')}: {Math.round(selectedAlertDetail.root_cause.confidence * 100)}%</span>
                              )}
                              {selectedAlertDetail.root_cause?.is_false_alarm && (
                                <span className="text-yellow-400">{t('observability.alertAnalysis.possibleFalseAlarm')}</span>
                              )}
                            </div>
                          </>
                        ) : (
                          <div className="text-sm text-[#6b7a9a] text-center py-4">
                            {t('observability.alertAnalysis.loadFailed')}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 分页 */}
          {alertAnalysesTotalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => { const p = alertAnalysesPage - 1; if (p >= 1) { loadAlertAnalyses(p); } }}
                disabled={alertAnalysesPage <= 1}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.prev')}
              </button>
              <span className="text-sm text-[#6b7a9a] px-3">
                {alertAnalysesPage} / {alertAnalysesTotalPages}
              </span>
              <button
                onClick={() => { const p = alertAnalysesPage + 1; if (p <= alertAnalysesTotalPages) { loadAlertAnalyses(p); } }}
                disabled={alertAnalysesPage >= alertAnalysesTotalPages}
                className="px-3 py-1.5 rounded bg-[#1a2030] border border-[#2a3142] text-sm text-white hover:bg-[#2a3142] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </section>
      )}

      {/* Trace Detail Modal */}
      {selectedTraceId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={closeTraceDetail}>
          <div className="bg-[#1a2030] border border-[#2a3142] rounded-xl w-full max-w-2xl max-h-[80vh] overflow-auto m-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-[#2a3142]">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-[#00d4ff]" />
                {t('observability.traceDetail')}
              </h2>
              <button onClick={closeTraceDetail} className="text-[#6b7a9a] hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4">
              {traceDetailLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-[#00d4ff]" />
                </div>
              ) : traceDetail ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-[#6b7a9a] uppercase mb-1">{t('observability.traceId')}</p>
                    <code className="text-sm text-[#00d4ff]">{traceDetail.cycle.trace_id}</code>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-[#6b7a9a] uppercase mb-1">{t('observability.time')}</p>
                      <p className="text-sm text-white">{formatTimestamp(traceDetail.cycle.timestamp)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6b7a9a] uppercase mb-1">{t('observability.cycleMs')}</p>
                      <p className="text-sm text-white">{(traceDetail.cycle.cycle_total_ms ?? 0).toFixed(1)} ms</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6b7a9a] uppercase mb-1">{t('observability.pipelineMs')}</p>
                      <p className="text-sm text-white">{(traceDetail.cycle.pipeline_total_ms ?? 0).toFixed(1)} ms</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6b7a9a] uppercase mb-1">{t('observability.heimanCalls')}</p>
                      <p className="text-sm text-white">{traceDetail.cycle.heiman_call_count ?? 0}</p>
                    </div>
                  </div>

                  {traceDetail.devices && traceDetail.devices.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-2">{t('observability.devices')} ({traceDetail.devices.length})</h3>
                      <div className="space-y-2">
                        {traceDetail.devices.map((device: TraceDevice) => (
                          <div key={device.did} className="bg-[#0f1419] rounded p-3">
                            <div className="flex items-center justify-between mb-2">
                              <code className="text-sm text-[#00d4ff]">{device.did}</code>
                              <span className={`px-2 py-0.5 rounded text-xs ${device.skipped ? 'bg-yellow-900/30 text-yellow-300' : 'bg-green-900/30 text-green-300'}`}>
                                {device.skipped ? 'Skipped' : 'Processed'}
                              </span>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-xs">
                              <div><span className="text-[#6b7a9a]">{t('observability.duration')}: </span><span className="text-white">{device.heiman_ms != null ? `${device.heiman_ms}ms` : '-'}</span></div>
                              <div><span className="text-[#6b7a9a]">Decode: </span><span className="text-white">{device.decode_ms != null ? `${device.decode_ms}ms` : '-'}</span></div>
                              <div><span className="text-[#6b7a9a]">Collect: </span><span className="text-white">{device.collect_ms != null ? `${device.collect_ms}ms` : '-'}</span></div>
                              <div><span className="text-[#6b7a9a]">Convert: </span><span className="text-white">{device.convert_ms != null ? `${device.convert_ms}ms` : '-'}</span></div>
                              <div><span className="text-[#6b7a9a]">In Delay: </span><span className="text-white">{device.in_delay_ms != null ? `${device.in_delay_ms}ms` : '-'}</span></div>
                              <div><span className="text-[#6b7a9a]">Out Delay: </span><span className="text-white">{device.out_delay_ms != null ? `${device.out_delay_ms}ms` : '-'}</span></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {(!traceDetail.devices || traceDetail.devices.length === 0) && (
                    <p className="text-sm text-[#6b7a9a] text-center py-4">{t('observability.noPayload')}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-[#6b7a9a] text-center py-12">{t('observability.noPayload')}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? 'text-white border-b-2 border-[#00d4ff] bg-[#1a2030]'
          : 'text-[#6b7a9a] hover:text-white hover:bg-[#2a3142]'
      }`}
    >
      {children}
    </button>
  );
}

function MetricCard({
  icon: Icon,
  title,
  value,
  sub,
  pct,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: string;
  sub?: string;
  pct: number;
  color: 'blue' | 'purple' | 'green';
}) {
  const colorMap = {
    blue: 'bg-[#00d4ff]',
    purple: 'bg-[#a78bfa]',
    green: 'bg-[#00ff88]',
  };
  return (
    <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-[#6b7a9a] uppercase">{title}</p>
        <Icon className="w-4 h-4 text-[#6b7a9a]" />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-[#6b7a9a] mt-1">{sub}</p>}
      <div className="h-1.5 bg-[#0f1419] rounded overflow-hidden mt-2">
        <div
          className={`h-full ${colorMap[color]} transition-all`}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>
    </div>
  );
}

function StatCard({ title, value, sub }: { title: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4">
      <p className="text-xs text-[#6b7a9a] uppercase">{title}</p>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
      {sub && <p className="text-xs text-[#6b7a9a] mt-1">{sub}</p>}
    </div>
  );
}

export default Observability;
