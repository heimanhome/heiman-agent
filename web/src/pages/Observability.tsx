import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Activity, Cpu, MemoryStick, HardDrive, Database, Loader2, RefreshCw, Clock, Zap, Eye, ChevronRight, AlertCircle, CheckCircle } from 'lucide-react';
import { observabilityApi, type ObservabilityOverview, type TraceRecord, type AgentRun, type ObsEvent } from '../api/client';

export function Observability() {
  const { t } = useTranslation('app');
  const [overview, setOverview] = useState<ObservabilityOverview | null>(null);
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [events, setEvents] = useState<ObsEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'traces' | 'agentRuns' | 'events'>('overview');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadOverview = async () => {
    try {
      const r = await observabilityApi.getOverview();
      setOverview(r.data.data || null);
    } catch (e) {
      console.error('Failed to load overview:', e);
    }
  };

  const loadTraces = async () => {
    try {
      const r = await observabilityApi.getTraces({ limit: 20 });
      setTraces(Array.isArray(r.data.data) ? r.data.data : []);
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

  const loadEvents = async () => {
    try {
      const r = await observabilityApi.getEvents({ limit: 20 });
      setEvents(Array.isArray(r.data.data) ? r.data.data : []);
    } catch (e) {
      console.error('Failed to load events:', e);
    }
  };

  const load = async () => {
    setLoading(true);
    await loadOverview();
    await loadTraces();
    await loadAgentRuns();
    await loadEvents();
    setLoading(false);
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
          Overview
        </TabButton>
        <TabButton active={activeTab === 'traces'} onClick={() => setActiveTab('traces')}>
          <Zap className="w-4 h-4" />
          Traces
        </TabButton>
        <TabButton active={activeTab === 'agentRuns'} onClick={() => setActiveTab('agentRuns')}>
          <Clock className="w-4 h-4" />
          Agent Runs
        </TabButton>
        <TabButton active={activeTab === 'events'} onClick={() => setActiveTab('events')}>
          <Activity className="w-4 h-4" />
          Events
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
                value={`${overview.system.cpu_percent.toFixed(1)}%`}
                pct={overview.system.cpu_percent}
                color="blue"
              />
              <MetricCard
                icon={MemoryStick}
                title={t('memory')}
                value={`${overview.system.memory_percent.toFixed(1)}%`}
                sub={`${overview.system.memory_used_mb.toFixed(0)} / ${overview.system.memory_total_mb.toFixed(0)} MB`}
                pct={overview.system.memory_percent}
                color="purple"
              />
              <MetricCard
                icon={HardDrive}
                title={t('disk')}
                value={`${overview.system.disk_percent.toFixed(1)}%`}
                sub={`${overview.system.disk_used_gb.toFixed(1)} / ${overview.system.disk_total_gb.toFixed(1)} GB`}
                pct={overview.system.disk_percent}
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
                value={`${overview.database.db_size_mb.toFixed(1)} MB`}
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
                    <span className="text-sm text-[#6b7a9a]">{type}</span>
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
          <h2 className="text-lg font-semibold text-white mb-3">Traces</h2>
          <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0f1419]">
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Trace ID</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Time</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Devices</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Cycle (ms)</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Pipeline (ms)</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Heiman Calls</th>
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[#6b7a9a]">
                      No traces available
                    </td>
                  </tr>
                ) : (
                  traces.map((trace) => {
                    const cycleMs = trace.cycle_total_ms ?? 0;
                    const pipelineMs = trace.pipeline_total_ms ?? 0;
                    const heimanCalls = trace.heiman_call_count ?? 0;
                    const heimanErrors = trace.heiman_error_count ?? 0;
                    return (
                      <tr key={trace.trace_id} className="border-t border-[#2a3142] hover:bg-[#2a3142]">
                        <td className="px-4 py-3">
                          <code className="text-xs text-[#00d4ff]">{trace.trace_id.slice(0, 16)}...</code>
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{formatTimestamp(trace.timestamp)}</td>
                        <td className="px-4 py-3 text-sm text-white">{trace.device_count ?? 0}</td>
                        <td className="px-4 py-3 text-sm text-white">{cycleMs.toFixed(1)}</td>
                        <td className="px-4 py-3 text-sm text-white">{pipelineMs.toFixed(1)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={heimanErrors > 0 ? 'text-red-400' : 'text-green-400'}>
                            {heimanCalls}
                            {heimanErrors > 0 && ` (${heimanErrors} errors)`}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === 'agentRuns' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">Agent Runs</h2>
          <div className="space-y-3">
            {agentRuns.length === 0 ? (
              <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-8 text-center text-[#6b7a9a]">
                No agent runs available
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
                          <code className="text-sm text-white">{run.run_id.slice(0, 20)}...</code>
                          <p className="text-xs text-[#6b7a9a]">Source: {run.source || '-'}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-white">{formatTimestamp(run.timestamp)}</p>
                        {run.duration_ms != null && (
                          <p className="text-xs text-[#6b7a9a]">
                            Duration: {(run.duration_ms / 1000).toFixed(1)}s
                          </p>
                        )}
                      </div>
                    </div>
                    {run.query && (
                      <div className="mt-3 text-sm text-[#6b7a9a] truncate">
                        Query: {run.query}
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

      {activeTab === 'events' && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">Events</h2>
          <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0f1419]">
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Time</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Source</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Type</th>
                  <th className="text-left px-4 py-3 text-xs text-[#6b7a9a] uppercase">Payload</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[#6b7a9a]">
                      No events available
                    </td>
                  </tr>
                ) : (
                  events.map((event) => {
                    let payloadStr = '';
                    try {
                      if (typeof event.payload === 'string') {
                        payloadStr = event.payload;
                      } else if (event.payload && typeof event.payload === 'object') {
                        payloadStr = JSON.stringify(event.payload);
                      } else {
                        payloadStr = String(event.payload ?? '');
                      }
                    } catch {
                      payloadStr = String(event.payload ?? '');
                    }
                    return (
                      <tr key={event.event_id} className="border-t border-[#2a3142] hover:bg-[#2a3142]">
                        <td className="px-4 py-3 text-sm text-white">{formatTimestamp(event.timestamp)}</td>
                        <td className="px-4 py-3 text-sm text-[#00d4ff]">{event.source || '-'}</td>
                        <td className="px-4 py-3 text-sm text-white">{event.event_type}</td>
                        <td className="px-4 py-3">
                          <code className="text-xs text-[#6b7a9a]">
                            {payloadStr.length > 80 ? payloadStr.slice(0, 80) + '...' : payloadStr}
                          </code>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
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
