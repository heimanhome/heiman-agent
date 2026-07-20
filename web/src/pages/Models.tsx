import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Cpu, ChevronDown, ChevronUp, Trash2, Play, RotateCcw, Plus, AlertCircle, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { adminApi, observabilityApi } from '../api/client';
import type { HeimanConfig, HeimanProfile } from '../api/client';

type Period = 'today' | '7d' | '30d';

interface TokenUsageEvent {
  id: number;
  timestamp_ms: number;
  model: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  endpoint: string;
  user_id: string;
}

interface TokenUsageBucket {
  bucket_start: number;
  model: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

interface TokenUsageDaily {
  date: string;
  model: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

const INPUT_CLS =
  "w-full px-3 py-2 rounded-lg bg-[#0f1419] border border-[#2a3142] " +
  "focus:border-[#00d4ff] focus:outline-none text-gray-900 dark:text-white text-sm";

const HEIMAN_CODE_MESSAGES: Record<string, string> = {
  ok: '连接正常',
  ok_model_found: '连接正常，模型可用',
  bad_key: 'API Key 无效或无权限',
  not_found: '模型或地址不存在',
  rejected_authed: '已连上且鉴权通过，但探测请求被模型拒绝',
  unreachable: '无法连接 Base URL',
  no_key: '未配置 API Key',
  http_error: 'HTTP 错误',
};

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

function formatTime(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function formatDate(d: string): string {
  return d.slice(5);
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function ComboBox({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  const q = value.trim().toLowerCase();
  const exact = options.some((o) => o.toLowerCase() === q);
  const list = !q || exact ? options : options.filter((o) => o.toLowerCase().includes(q));

  return (
    <div className="relative" ref={ref}>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className={INPUT_CLS + ' pr-9'}
        autoComplete="off"
      />
      {options.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-900 dark:text-white px-1 text-lg leading-none"
        >
          ▾
        </button>
      )}
      {open && list.length > 0 && (
        <ul className="absolute left-0 right-0 mt-1 z-20 max-h-60 overflow-auto rounded-lg bg-[#0a1628] border border-[#2a3142] shadow-md py-1">
          {list.map((o) => (
            <li key={o}>
              <button
                  type="button"
                  onClick={() => {
                    onChange(o);
                    setOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                {o}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Toast({ message, type }: { message: string; type: 'ok' | 'warn' | 'danger' }) {
  const colors = {
    ok: 'bg-green-500/20 border-green-500/30 text-green-400',
    warn: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
    danger: 'bg-red-500/20 border-red-500/30 text-red-400',
  };
  return (
    <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg border ${colors[type]} text-sm`}>
      {message}
    </div>
  );
}

export function Models() {
  const { t } = useTranslation('app');
  const [period, setPeriod] = useState<Period>('today');
  const [binMinutes, setBinMinutes] = useState(60);
  const [refreshKey, setRefreshKey] = useState(0);

  const [heimanConfig, setHeimanConfig] = useState<HeimanConfig | null>(null);
  const [heimanError, setHeimanError] = useState<string | null>(null);
  const [configCollapsed, setConfigCollapsed] = useState(false);

  const [adding, setAdding] = useState(false);
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsMsg, setModelsMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; code?: string; message: string; latency_ms?: number } | null>(null);

  const [toast, setToast] = useState<{ message: string; type: 'ok' | 'warn' | 'danger' } | null>(null);

  const [usageLoading, setUsageLoading] = useState(true);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [buckets, setBuckets] = useState<TokenUsageBucket[]>([]);
  const [daily, setDaily] = useState<TokenUsageDaily[]>([]);

  const profiles = heimanConfig?.profiles ?? [];
  const active = heimanConfig?.active;
  const hasKey = active?.has_key ?? false;
  const existing = profiles.find(
    (p) => p.base_url === baseUrl.trim() && p.model === model.trim(),
  );

  useEffect(() => {
    loadHeimanConfig();
  }, []);

  useEffect(() => {
    loadUsage();
  }, [period, binMinutes, refreshKey]);

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  const showToast = (message: string, type: 'ok' | 'warn' | 'danger') => {
    setToast({ message, type });
  };

  async function loadHeimanConfig() {
    try {
      const res = await adminApi.getHeimanConfig();
      setHeimanConfig(res.data?.data || null);
      setHeimanError(null);
    } catch (e) {
      setHeimanError(e instanceof Error ? e.message : '加载失败');
    }
  }

  async function loadUsage() {
    setUsageLoading(true);
    setUsageError(null);
    try {
      const now = Date.now();
      let since: number | undefined;
      if (period === 'today') {
        const d = new Date();
        d.setHours(0, 0, 0, 0);
        since = d.getTime();
      } else if (period === '7d') {
        since = now - 7 * 24 * 60 * 60 * 1000;
      } else if (period === '30d') {
        since = now - 30 * 24 * 60 * 60 * 1000;
      }

      if (period === 'today') {
        const res = await observabilityApi.getTokenUsageBuckets({ since, until: now, bin: binMinutes });
        setBuckets(res.data?.data?.rows || []);
        setDaily([]);
      } else {
        const d = new Date();
        const untilStr = d.toISOString().slice(0, 10);
        const sinceDate = new Date(since!);
        const sinceStr = sinceDate.toISOString().slice(0, 10);
        const res = await observabilityApi.getTokenUsageDaily({ since: sinceStr, until: untilStr });
        setDaily(res.data?.data?.rows || []);
        setBuckets([]);
      }
    } catch (e) {
      setUsageError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setUsageLoading(false);
    }
  }

  async function fetchModels(bu: string, key: string) {
    if (!bu.trim()) return;
    setModelsLoading(true);
    setModelsMsg(null);
    try {
      const res = await adminApi.listHeimanModels({ base_url: bu.trim(), api_key: key.trim() || undefined });
      const data = res.data?.data;
      if (data?.ok) {
        setModels(data.models || []);
        if (!data.models?.length) setModelsMsg('无可用模型');
      } else {
        setModels([]);
        const msg = data?.code ? HEIMAN_CODE_MESSAGES[data.code] || data.message : data?.message || '获取失败';
        setModelsMsg(msg);
      }
    } catch (e) {
      setModels([]);
      setModelsMsg(e instanceof Error ? e.message : '获取失败');
    } finally {
      setModelsLoading(false);
    }
  }

  function startAdd() {
    setAdding(true);
    setBaseUrl('');
    setApiKey('');
    setModel('');
    setModels([]);
    setModelsMsg(null);
    setTestResult(null);
  }

  async function onSave() {
    const bu = baseUrl.trim();
    const m = model.trim();
    if (!bu || !m) {
      showToast('Base URL 和模型不能为空', 'warn');
      return;
    }
    if (!apiKey.trim() && !existing?.has_key) {
      showToast('请输入 API Key', 'warn');
      return;
    }
    setSaving(true);
    try {
      const res = await adminApi.saveHeimanConfig({
        label: existing ? existing.label : `${m} @ ${bu}`,
        model: m,
        base_url: bu,
        api_key: apiKey.trim() || undefined,
        original_label: existing ? existing.label : undefined,
        activate: false,
      });
      setHeimanConfig(res.data?.data || null);
      setAdding(false);
      showToast('保存成功', 'ok');
    } catch (e) {
      showToast(e instanceof Error ? e.message : '保存失败', 'danger');
    } finally {
      setSaving(false);
    }
  }

  async function onTest() {
    const bu = baseUrl.trim();
    const m = model.trim();
    if (!bu || !m) {
      showToast('Base URL 和模型不能为空', 'warn');
      return;
    }
    if (!apiKey.trim() && !existing?.has_key) {
      showToast('请输入 API Key', 'warn');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const res = await adminApi.testHeimanConfig({
        label: existing ? existing.label : '',
        model: m,
        base_url: bu,
        api_key: apiKey.trim() || undefined,
      });
      const data = res.data?.data;
      setTestResult(data);
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : '测试失败' });
    } finally {
      setTesting(false);
    }
  }

  async function onActivate(p: HeimanProfile) {
    try {
      const res = await adminApi.activateHeimanConfig(p.label);
      setHeimanConfig(res.data?.data || null);
      showToast('已启用', 'ok');
    } catch (e) {
      showToast(e instanceof Error ? e.message : '启用失败', 'danger');
    }
  }

  async function onDelete(p: HeimanProfile) {
    if (!window.confirm(`确定删除 ${p.model} @ ${hostOf(p.base_url)} 吗？`)) return;
    try {
      const res = await adminApi.deleteHeimanConfig(p.label);
      setHeimanConfig(res.data?.data || null);
      showToast('已删除', 'ok');
    } catch (e) {
      showToast(e instanceof Error ? e.message : '删除失败', 'danger');
    }
  }

  async function onClearUsage() {
    if (!window.confirm('确定清空所有 Token 用量数据吗？此操作不可恢复。')) return;
    try {
      await observabilityApi.clearTokenUsage();
      setRefreshKey((k) => k + 1);
      showToast('已清空', 'ok');
    } catch (e) {
      showToast(e instanceof Error ? e.message : '清空失败', 'danger');
    }
  }

  const totalPrompt = buckets.reduce((s, b) => s + b.prompt_tokens, 0);
  const totalCompletion = buckets.reduce((s, b) => s + b.completion_tokens, 0);
  const totalAll = buckets.reduce((s, b) => s + b.total_tokens, 0);
  const totalRequests = buckets.reduce((s, b) => s + b.request_count, 0);

  const dailyTotalPrompt = daily.reduce((s, d) => s + d.prompt_tokens, 0);
  const dailyTotalCompletion = daily.reduce((s, d) => s + d.completion_tokens, 0);
  const dailyTotalAll = daily.reduce((s, d) => s + d.total_tokens, 0);
  const dailyTotalRequests = daily.reduce((s, d) => s + d.request_count, 0);

  const chartData = period === 'today' ? buckets : daily;
  const maxTokens = Math.max(
    1,
    ...chartData.map((d: any) => d.total_tokens || 0)
  );

  return (
    <div className="max-w-[1200px] w-full mx-auto px-4 md:px-8 pt-5 pb-12">
      {toast && <Toast message={toast.message} type={toast.type} />}

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">模型与用量</h1>
        <p className="text-sm text-gray-500 dark:text-[#6b7a9a] mt-1">管理 Heiman 模型配置，查看 Token 用量统计</p>
      </div>

      <div className="space-y-6">
        {/* Heiman 配置卡片 */}
        <section className="rounded-xl bg-[#0f1419] border border-[#2a3142] p-5 md:p-6">
          <button
            type="button"
            onClick={() => setConfigCollapsed((c) => !c)}
            className="w-full flex items-center justify-between gap-3 text-left"
          >
            <span className="flex items-baseline gap-3 flex-wrap">
              <span className="text-base font-semibold text-gray-900 dark:text-white">Heiman 模型配置</span>
              {configCollapsed && active && (
                <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">
                  当前: {hasKey ? `${active.model} · ${hostOf(active.base_url)}` : '未配置 API Key'}
                </span>
              )}
            </span>
            <span className="text-gray-500 dark:text-[#6b7a9a] text-sm">
              {configCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </span>
          </button>

          {!configCollapsed && (
            <div className="mt-4">
              {heimanError ? (
                <div className="text-red-400 text-center py-6">{heimanError}</div>
              ) : !heimanConfig || !active ? (
                <div className="text-gray-500 dark:text-[#6b7a9a] text-center py-6">加载中...</div>
              ) : (
                <>
                  {!hasKey && (
                    <div className="text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2 mb-3">
                      未配置 API Key，请先添加模型配置
                    </div>
                  )}

                  <div className="overflow-x-auto -mx-5 md:-mx-6">
                    <table className="w-full text-sm whitespace-nowrap">
                      <thead>
                        <tr className="text-gray-500 dark:text-[#6b7a9a] border-b border-[#2a3142]">
                          <th className="text-left px-5 md:px-6 py-2 font-medium">模型</th>
                          <th className="text-left px-3 py-2 font-medium">Base URL</th>
                          <th className="text-left px-3 py-2 font-medium">API Key</th>
                          <th className="text-right px-5 md:px-6 py-2 font-medium">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {profiles.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="px-5 md:px-6 py-5 text-center text-gray-500 dark:text-[#6b7a9a]">
                              暂无配置
                            </td>
                          </tr>
                        ) : (
                          profiles.map((p) => (
                            <tr
                              key={p.label}
                              className={`border-b border-[#2a3142] last:border-b-0 ${p.active ? 'bg-[#00d4ff]/5' : ''}`}
                            >
                              <td className="px-5 md:px-6 py-2.5 text-gray-900 dark:text-white font-mono">{p.model}</td>
                              <td className="px-3 py-2.5 text-gray-500 dark:text-[#6b7a9a] font-mono text-xs">{p.base_url}</td>
                              <td className="px-3 py-2.5 text-gray-500 dark:text-[#6b7a9a] font-mono text-xs">
                                {p.has_key ? p.api_key_masked : '未配置'}
                              </td>
                              <td className="px-5 md:px-6 py-2.5 text-right whitespace-nowrap">
                                {p.active ? (
                                  <span className="inline-block rounded-md px-2.5 py-1 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white text-xs font-medium mr-3">
                                    当前使用
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => onActivate(p)}
                                    className="hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600 rounded-md px-2.5 py-1 mr-3 text-xs"
                                  >
                                    启用
                                  </button>
                                )}
                                <button
                type="button"
                onClick={() => onDelete(p)}
                className="p-1.5 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 inline-flex items-center rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  {!adding && (
                    <button
                      type="button"
                      onClick={startAdd}
                      className="mt-3 text-sm text-gray-900 dark:text-white hover:text-gray-700 dark:hover:text-gray-300 inline-flex items-center gap-1"
                    >
                      <Plus className="w-4 h-4" /> 新增模型
                    </button>
                  )}

                  {adding && (
                    <div className="mt-4 rounded-lg bg-[#0a1628] border border-[#2a3142] p-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 items-start">
                      <div className="md:col-span-2 text-sm text-gray-500 dark:text-[#6b7a9a]">
                        添加新的 Heiman 模型配置，或更新已有配置
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-sm text-gray-500 dark:text-[#6b7a9a] mb-1">Base URL</label>
                        <input
                          value={baseUrl}
                          onChange={(e) => {
                            setBaseUrl(e.target.value);
                            setTestResult(null);
                          }}
                          onBlur={() => fetchModels(baseUrl, apiKey)}
                          placeholder="https://api.example.com/v1"
                          className={INPUT_CLS}
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-500 dark:text-[#6b7a9a] mb-1">API Key</label>
                        <input
                          type="password"
                          value={apiKey}
                          onChange={(e) => {
                            setApiKey(e.target.value);
                            setTestResult(null);
                          }}
                          onBlur={() => fetchModels(baseUrl, apiKey)}
                          placeholder={existing?.has_key ? '留空沿用原 Key' : 'sk-...'}
                          autoComplete="off"
                          className={INPUT_CLS}
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-500 dark:text-[#6b7a9a] mb-1">模型</label>
                        <ComboBox
                          value={model}
                          onChange={(v) => {
                            setModel(v);
                            setTestResult(null);
                          }}
                          options={models}
                          placeholder={modelsLoading ? '加载中...' : '选择或输入模型名'}
                        />
                        <span className="text-xs text-gray-500 dark:text-[#6b7a9a] mt-1 block">
                          {modelsLoading
                            ? '正在获取模型列表...'
                            : modelsMsg
                            ? modelsMsg
                            : models.length
                            ? `共 ${models.length} 个模型`
                            : '输入 Base URL 和 API Key 后自动获取'}
                        </span>
                      </div>
                      <div className="md:col-span-2 pt-1 flex items-center gap-3 flex-wrap">
                        <button
                          type="button"
                          onClick={onSave}
                          disabled={saving || testing}
                          className="px-5 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-medium hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-60 text-sm"
                        >
                          {saving ? '保存中...' : '保存'}
                        </button>
                        <button
                          type="button"
                          onClick={onTest}
                          disabled={saving || testing}
                          className="px-5 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-60 text-sm inline-flex items-center gap-2"
                        >
                          {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                          {testing ? '测试中...' : '测试连接'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setAdding(false);
                            setTestResult(null);
                          }}
                          disabled={saving || testing}
                          className="px-3 py-2 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-60"
                        >
                          取消
                        </button>
                        {testResult && (
                          <span className={`text-sm ${testResult.ok ? 'text-green-400' : 'text-red-400'} inline-flex items-center gap-1`}>
                            {testResult.ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                            {testResult.code ? HEIMAN_CODE_MESSAGES[testResult.code] || testResult.message : testResult.message}
                            {testResult.latency_ms != null ? ` · ${testResult.latency_ms}ms` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </section>

        {/* Token 用量卡片 */}
        <section className="rounded-xl bg-[#0f1419] border border-[#2a3142] p-5 md:p-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Token 用量</h2>
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg border border-[#2a3142] overflow-hidden">
                {(['today', '7d', '30d'] as Period[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-3 py-1.5 text-sm ${
                      period === p
                        ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    {p === 'today' ? '今日' : p === '7d' ? '近7天' : '近30天'}
                  </button>
                ))}
              </div>
              <button
                onClick={onClearUsage}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 text-sm inline-flex items-center gap-1"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                清空
              </button>
            </div>
          </div>

          {usageLoading ? (
            <div className="py-8 text-center text-gray-500 dark:text-[#6b7a9a]">加载中...</div>
          ) : usageError ? (
            <div className="py-8 text-center text-red-400">{usageError}</div>
          ) : (
            <>
              {/* 总览 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                <div className="bg-[#0a1628] rounded-lg p-4">
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">总 Token</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-white">
                    {formatNumber(period === 'today' ? totalAll : dailyTotalAll)}
                  </p>
                </div>
                <div className="bg-[#0a1628] rounded-lg p-4">
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">Prompt</p>
                  <p className="text-xl font-bold text-[#00d4ff]">
                    {formatNumber(period === 'today' ? totalPrompt : dailyTotalPrompt)}
                  </p>
                </div>
                <div className="bg-[#0a1628] rounded-lg p-4">
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">Completion</p>
                  <p className="text-xl font-bold text-[#00ff88]">
                    {formatNumber(period === 'today' ? totalCompletion : dailyTotalCompletion)}
                  </p>
                </div>
                <div className="bg-[#0a1628] rounded-lg p-4">
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">请求次数</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-white">
                    {formatNumber(period === 'today' ? totalRequests : dailyTotalRequests)}
                  </p>
                </div>
              </div>

              {/* 时间分布 */}
              {period === 'today' && (
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">时间分布</p>
                    <select
                      value={binMinutes}
                      onChange={(e) => setBinMinutes(Number(e.target.value))}
                      className="bg-[#0a1628] border border-[#2a3142] rounded px-2 py-1 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]"
                    >
                      <option value={15}>15 分钟</option>
                      <option value={30}>30 分钟</option>
                      <option value={60}>1 小时</option>
                      <option value={180}>3 小时</option>
                    </select>
                  </div>
                  {buckets.length === 0 ? (
                    <div className="py-8 text-center text-gray-500 dark:text-[#6b7a9a] text-sm">暂无数据</div>
                  ) : (
                    <div className="h-32 flex items-end gap-1">
                      {buckets.slice().reverse().map((b, i) => (
                        <div
                          key={i}
                          className="flex-1 bg-gradient-to-t from-[#00d4ff] to-[#00ff88] rounded-t transition-all hover:opacity-80"
                          style={{ height: `${(b.total_tokens / maxTokens) * 100}%`, minHeight: '2px' }}
                          title={`${formatTime(b.bucket_start)}: ${formatNumber(b.total_tokens)} tokens`}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 明细表 */}
              <div>
                <p className="text-sm text-gray-500 dark:text-[#6b7a9a] mb-2">
                  {period === 'today' ? '今日明细' : '每日明细'}
                </p>
                <div className="overflow-x-auto -mx-5 md:-mx-6">
                  <table className="w-full text-sm whitespace-nowrap">
                    <thead>
                      <tr className="text-gray-500 dark:text-[#6b7a9a] border-b border-[#2a3142]">
                        <th className="text-left px-5 md:px-6 py-2 font-medium">
                          {period === 'today' ? '时间' : '日期'}
                        </th>
                        <th className="text-left px-3 py-2 font-medium">模型</th>
                        <th className="text-right px-3 py-2 font-medium">Prompt</th>
                        <th className="text-right px-3 py-2 font-medium">Completion</th>
                        <th className="text-right px-3 py-2 font-medium">总计</th>
                        <th className="text-right px-5 md:px-6 py-2 font-medium">请求</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chartData.length === 0 ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-5 md:px-6 py-5 text-center text-gray-500 dark:text-[#6b7a9a]"
                          >
                            暂无数据
                          </td>
                        </tr>
                      ) : (
                        chartData.map((row: any, i: number) => (
                          <tr
                            key={i}
                            className="border-b border-[#2a3142] last:border-b-0"
                          >
                            <td className="px-5 md:px-6 py-2.5 text-gray-900 dark:text-white">
                              {period === 'today'
                                ? formatTime(row.bucket_start)
                                : formatDate(row.date)}
                            </td>
                            <td className="px-3 py-2.5 text-gray-500 dark:text-[#6b7a9a] font-mono text-xs">
                              {row.model || '-'}
                            </td>
                            <td className="px-3 py-2.5 text-right text-[#00d4ff]">
                              {formatNumber(row.prompt_tokens)}
                            </td>
                            <td className="px-3 py-2.5 text-right text-[#00ff88]">
                              {formatNumber(row.completion_tokens)}
                            </td>
                            <td className="px-3 py-2.5 text-right text-gray-900 dark:text-white font-medium">
                              {formatNumber(row.total_tokens)}
                            </td>
                            <td className="px-5 md:px-6 py-2.5 text-right text-gray-500 dark:text-[#6b7a9a]">
                              {formatNumber(row.request_count)}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
