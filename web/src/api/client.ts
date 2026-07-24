import axios, { AxiosError, AxiosResponse } from 'axios';
import type { SensorData, SensorEvent, Rule, SensorHistoryData, HomeEntry, HomeEntryType, HomeEntries } from '../types';
import { authManager } from './auth-manager';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

export interface ApiError {
  status: number;
  message: string;
  code?: string;
}

export interface ApiResponse<T = unknown> {
  data: T;
  success: boolean;
  message?: string;
  code?: string;
}

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  console.debug('[API] Request:', config.method?.toUpperCase(), config.url, config.params || config.data);
  return config;
}, (error) => {
  console.error('[API] Request error:', error);
  return Promise.reject(error);
});

api.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    console.debug('[API] Response:', response.status, response.config.url, response.data);
    return response;
  },
  (error: AxiosError<ApiResponse>) => {
    const status = error.response?.status;
    
    console.error('[API] Response error:', status, error.config?.url, error.response?.data || error.message);

    if (status === 401) {
      authManager.logout();
      return Promise.reject({
        status: 401,
        message: 'Not authenticated',
      });
    }

    if (status === 403) {
      return Promise.reject({
        status: 403,
        message: 'Permission denied',
      });
    }

    if (status === 500) {
      return Promise.reject({
        status: 500,
        message: 'Server error',
      });
    }

    if (error.code === 'ECONNABORTED') {
      return Promise.reject({
        status: 0,
        message: 'Request timed out',
      });
    }

    if (!error.response) {
      return Promise.reject({
        status: 0,
        message: 'Network error',
      });
    }

    return Promise.reject({
      status: error.response.status,
      message: error.response.data?.message || 'Request failed',
      code: error.response.data?.code,
    });
  }
);

export const authApi = {
  logout: () => {
    authManager.logout();
  },
  getAuthStatus: () => api.get<ApiResponse<{ authenticated: boolean; user_id: string }>>('/auth/token'),
  getProfile: () => api.get<ApiResponse<{ username: string; nickName?: string; email: string; phone: string; bindStatus: boolean; userId?: string; avatar?: string }>>('/auth/profile'),
  saveHomeSelection: (home_id: string) => api.post<ApiResponse>('/auth/home-select', { home_id }),
  getLastHome: () => api.get<ApiResponse<{ home_id: string | null }>>('/auth/last-home'),
};

export const sensorApi = {
  getAll: (home_id?: string) => api.get<ApiResponse<SensorData[]>>('/sensors', { params: { home_id } }),
  getById: (did: string, home_id?: string) => api.get<ApiResponse<SensorData>>(`/sensors/${did}`, { params: { home_id } }),
  getHistory: (did: string, params?: { start_time?: string; end_time?: string; limit?: number }) =>
    api.get<ApiResponse<SensorHistoryData[]>>(`/sensors/${did}/history`, { params }),
  pushData: (data: SensorData) => api.post<ApiResponse<SensorData>>('/sensors/data', data),
};

export const eventApi = {
  getAll: (params?: { event_type?: string; level?: string; acknowledged?: boolean; home_id?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<SensorEvent>>('/events', { params }),
  getById: (event_id: string) => api.get<ApiResponse<SensorEvent>>(`/events/${event_id}`),
  acknowledge: (event_id: string) => api.post<ApiResponse>(`/events/${event_id}/acknowledge`),
  batchAcknowledge: (event_ids: string[]) => api.post<ApiResponse>('/events/batch/acknowledge', { event_ids }),
};

export const ruleApi = {
  getAll: () => api.get<ApiResponse<Rule[]>>('/rules'),
  getById: (rule_id: string) => api.get<ApiResponse<Rule>>(`/rules/${rule_id}`),
  create: (data: Omit<Rule, 'rule_id' | 'created_at' | 'updated_at'>) =>
    api.post<ApiResponse<Rule>>('/rules', data),
  update: (rule_id: string, data: Partial<Rule>) => api.put<ApiResponse<Rule>>(`/rules/${rule_id}`, data),
  delete: (rule_id: string) => api.delete<ApiResponse>(`/rules/${rule_id}`),
};

export interface HomeData {
  id: string;
  name: string;
  address: string;
  members: Member[];
  devices: number;
  createdAt: string;
}

export interface Member {
  id: string;
  name: string;
  role: 'owner' | 'admin' | 'member' | 'device';
  avatar: string | { url: string };
}

export const homeApi = {
  getAll: () => api.get<ApiResponse<HomeData[]>>('/homes'),
  getById: (homeId: string) => api.get<ApiResponse<HomeData>>(`/homes/${homeId}`),
  create: (data: { name: string; address?: string }) => api.post<ApiResponse<HomeData>>('/homes', data),
  update: (homeId: string, data: Partial<HomeData>) => api.put<ApiResponse<HomeData>>(`/homes/${homeId}`, data),
  delete: (homeId: string) => api.delete<ApiResponse>(`/homes/${homeId}`),
  addMember: (homeId: string, data: { name: string; role?: string }) => api.post<ApiResponse<Member>>(`/homes/${homeId}/members`, data),
  removeMember: (homeId: string, memberId: string) => api.delete<ApiResponse>(`/homes/${homeId}/members/${memberId}`),
  updateMember: (homeId: string, memberId: string, data: { name?: string; role?: string }) => api.put<ApiResponse<Member>>(`/homes/${homeId}/members/${memberId}`, data),
};

export interface LogEntry {
  id: string;
  time: string;
  level: 'info' | 'warning' | 'error' | 'success';
  action: string;
  user: string;
  message: string;
}

export interface DeviceLogEntry {
  id: string;
  did: string;
  sensor_type: string;
  value: string | number;
  unit: string;
  status: string;
  room_name: string;
  home_id: string;
  timestamp: string;
  property_name: string;
  attribute: string;
  battery?: number;
  rssi?: number;
  switch_state?: number;
  contact_state?: number;
  motion_state?: number;
  temperature?: number;
  humidity?: number;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  page_size: number;
  message?: string;
}

export interface PaginatedData<T> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: T[];
}

export const logApi = {
  getAll: (params?: { level?: string; action?: string; user?: string; search?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<LogEntry>>('/logs', { params }),
  getOperationLogs: (params?: { search?: string }) => api.get<ApiResponse<LogEntry[]>>('/logs/operation', { params }),
  getErrorLogs: (params?: { search?: string }) => api.get<ApiResponse<LogEntry[]>>('/logs/error', { params }),
  getDeviceLogs: (params?: { did?: string; sensor_type?: string; home_id?: string; after?: string; before?: string; search?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<DeviceLogEntry>>('/logs/device', { params }),
  exportLogs: (params?: { level?: string; start_time?: string; end_time?: string }) =>
    api.get<Blob>('/logs/export', { params, responseType: 'blob' }),
};

export interface ModelData {
  id: string;
  name: string;
  version: string;
  type: 'classification' | 'detection' | 'forecast';
  status: 'deployed' | 'not_deployed' | 'training';
  description: string;
  accuracy: number;
  lastDeployed: string;
}

export const modelApi = {
  getAll: () => api.get<ApiResponse<ModelData[]>>('/models'),
  getById: (modelId: string) => api.get<ApiResponse<ModelData>>(`/models/${modelId}`),
  deploy: (modelId: string) => api.post<ApiResponse>(`/models/${modelId}/deploy`),
  stop: (modelId: string) => api.post<ApiResponse>(`/models/${modelId}/stop`),
  configure: (modelId: string, data: Record<string, unknown>) => api.put<ApiResponse>(`/models/${modelId}/configure`, data),
  upload: (formData: FormData) => api.post<ApiResponse<ModelData>>('/models/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};

export interface DeviceData {
  id: string;
  name: string;
  type: string;
  status: string;
  value: number;
  unit: string;
  room: string;
  battery: number;
  rssi: number;
  switchState: number | null;
  smokeState: number | null;
  gasState: number | null;
  waterState: number | null;
  temperature: number | null;
  humidity: number | null;
  co2: number | null;
  pm25: number | null;
  pm10: number | null;
  hcho: number | null;
  motionState: number | null;
  tamperState: number | null;
  sensorLifeStatus: number | null;
  alarmState: number | null;
  lastUpdate: string;
  home_id?: string;
  productName?: string;
  photoUrl?: string;
  parentId?: string;
  productId?: string;
  properties?: Record<string, any>;
  deriveMetadata?: any[];
}

export interface PanelData {
  deviceId: string;
  deviceName: string;
  productId: string;
  productName: string;
  panelUrl: string;
  entryUrl: string;
  sessionId: string;
  fileCount: number;
}

export const deviceApi = {
  getAll: (params?: { type?: string; status?: string; search?: string; home_id?: string }) =>
    api.get<ApiResponse<DeviceData[]>>('/devices', { params }),
  getById: (deviceId: string) => api.get<ApiResponse<DeviceData>>(`/devices/${deviceId}`),
  create: (data: { name: string; type: string; room?: string }) => api.post<ApiResponse<DeviceData>>('/devices', data),
  update: (deviceId: string, data: Partial<DeviceData>) => api.put<ApiResponse<DeviceData>>(`/devices/${deviceId}`, data),
  delete: (deviceId: string) => api.delete<ApiResponse>(`/devices/${deviceId}`),
  toggle: (deviceId: string) => api.post<ApiResponse>(`/devices/${deviceId}/toggle`),
  control: (deviceId: string, property_identifier: string, value: any) =>
    api.post<ApiResponse>(`/devices/${deviceId}/control`, { property_identifier, value }),
  getPanel: (deviceId: string, home_id?: string) => api.get<ApiResponse<PanelData>>(`/devices/${deviceId}/panel`, { params: { home_id } }),
  closePanelSession: (sessionId: string) => api.post<ApiResponse>('/devices/panel/session/close', { sessionId }),
};

export interface Person {
  id: string;
  name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface Person {
  id: string;
  name: string;
  role: string | null;
  user_id?: string | null;
  home_id?: string | null;
  home_name?: string | null;
  user_account?: string | null;
  alias_name?: string | null;
  head_img_url?: string | null;
  is_home_root?: number | null;
  role_type?: number | null;
  status?: number | null;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export const personApi = {
  getAll: (home_id?: string) =>
    api.get<ApiResponse<Person[]>>('/identity/persons', { params: { home_id } }),
  getById: (id: string) => api.get<ApiResponse<Person>>(`/identity/persons/${id}`),
  create: (data: { name: string; role?: string; home_id?: string }) =>
    api.post<ApiResponse<Person>>('/identity/persons', data),
  update: (id: string, data: { name?: string; role?: string }) =>
    api.put<ApiResponse<Person>>(`/identity/persons/${id}`, data),
  delete: (id: string) => api.delete<ApiResponse>(`/identity/persons/${id}`),
  sync: (home_id: string) =>
    api.post<ApiResponse<{ synced: number; added: number; updated: number; members: Person[] }>>(
      '/identity/persons/sync',
      null,
      { params: { home_id } }
    ),
};

export interface Task {
  task_id: string;
  description: string;
  status: 'active' | 'paused';
  paused_at: string | null;
  created_at: string;
  updated_at: string;
  record?: ProgressRecord | DurationRecord | EventRecord;
}

export interface ProgressRecord {
  kind: 'progress';
  target: number;
  current: number;
  unit: string;
  window: 'day' | 'week' | 'month' | 'longterm';
  status: 'active' | 'completed';
}

export interface DurationRecord {
  kind: 'duration';
  target_minutes: number;
  accumulated_minutes: number;
  active_session_start_at: string | null;
  status: 'active' | 'completed';
}

export interface EventRecord {
  kind: 'event';
  total_count: number;
  today_count: number;
  status: 'active' | 'completed';
}

export const taskApi = {
  getAll: (home_id?: string) => api.get<ApiResponse<Task[]>>('/tasks', { params: { home_id } }),
  getById: (id: string) => api.get<ApiResponse<Task>>(`/tasks/${id}`),
  create: (data: {
    description: string;
    kind: 'progress' | 'duration' | 'event';
    target?: number;
    unit?: string;
    window?: 'day' | 'week' | 'month' | 'longterm';
    target_minutes?: number;
  }) => api.post<ApiResponse<Task>>('/tasks', data),
  delete: (id: string) => api.delete<ApiResponse>(`/tasks/${id}`),
  pause: (id: string) => api.post<ApiResponse<Task>>(`/tasks/${id}/pause`),
  resume: (id: string) => api.post<ApiResponse<Task>>(`/tasks/${id}/resume`),
  initRecord: (id: string, data: Record<string, unknown>) => api.post<ApiResponse>(`/tasks/${id}/record`, data),
  incrementProgress: (id: string, delta: number) =>
    api.post<ApiResponse>(`/tasks/${id}/progress/increment`, { delta }),
  startSession: (id: string) => api.post<ApiResponse>(`/tasks/${id}/session/start`),
  endSession: (id: string) => api.post<ApiResponse>(`/tasks/${id}/session/end`),
  appendEvent: (id: string, description: string) =>
    api.post<ApiResponse>(`/tasks/${id}/event/append`, { description }),
  setEnabled: (taskId: string, enabled: boolean) => api.post<ApiResponse>(`/tasks/${taskId}/${enabled ? 'enable' : 'disable'}`),
};

export interface ObservabilityOverview {
  system: {
    cpu_percent: number;
    memory_percent: number;
    memory_used_mb: number;
    memory_total_mb: number;
    disk_percent: number;
    disk_used_gb: number;
    disk_total_gb: number;
    uptime_seconds: number;
  };
  sensor: {
    total_sensors: number;
    online_sensors: number;
    offline_sensors: number;
    data_points_today: number;
    data_points_total: number;
    by_type: Record<string, number>;
  };
  rule: {
    total_rules: number;
    enabled_rules: number;
    triggered_today: number;
    triggered_total: number;
    actions_executed_today: number;
  };
  event: {
    total_events: number;
    events_today: number;
    by_level: Record<string, number>;
    by_type: Record<string, number>;
    unacknowledged: number;
  };
  database: {
    db_size_mb: number;
    table_count: number;
    sensor_logs_count: number;
    events_count: number;
    rules_count: number;
  };
}

export interface TraceRecord {
  trace_id: string;
  timestamp: number;
  device_count: number;
  skipped: number;
  in_delay_ms: number;
  out_delay_ms: number;
  decode_ms: number;
  collect_ms: number;
  convert_ms: number;
  log_ms: number;
  cycle_total_ms: number;
  pipeline_total_ms: number;
  window_duration_ms: number;
  gate_ms: number;
  gate_video_ms: number;
  gate_audio_ms: number;
  gate_video_pass: number;
  gate_audio_pass: number;
  identity_ms: number;
  heiman_ms: number;
  heiman_call_count: number;
  heiman_error_count: number;
}

export interface TraceDevice {
  cycle_id: string;
  did: string;
  timestamp: number;
  skipped: number;
  in_delay_ms: number;
  out_delay_ms: number;
  decode_ms: number;
  collect_ms: number;
  convert_ms: number;
  gate_ms: number;
  gate_video_ms: number;
  gate_audio_ms: number;
  gate_video_pass: number;
  gate_audio_pass: number;
  gate_hold_pass: number;
  identity_ms: number;
  heiman_ms: number;
  heiman_call_count: number;
  heiman_error_count: number;
}

export interface AgentRun {
  run_id: string;
  trace_id: string;
  timestamp: number;
  source: string;
  query: string | null;
  duration_ms: number | null;
  llm_call_count: number | null;
  tool_call_count: number | null;
  success: number | null;
  error_count: number | null;
  error_msg: string | null;
}

export const observabilityApi = {
  getOverview: () => api.get<ApiResponse<ObservabilityOverview>>('/observability/overview'),
  getSystem: () => api.get<ApiResponse<ObservabilityOverview['system']>>('/observability/system'),
  getSensor: () => api.get<ApiResponse<ObservabilityOverview['sensor']>>('/observability/sensor'),
  getRule: () => api.get<ApiResponse<ObservabilityOverview['rule']>>('/observability/rule'),
  getEvent: () => api.get<ApiResponse<ObservabilityOverview['event']>>('/observability/event'),
  getDatabase: () => api.get<ApiResponse<ObservabilityOverview['database']>>('/observability/database'),
  // Token Usage APIs
  getTokenUsage: (params?: { since?: number; until?: number; limit?: number }) =>
    api.get<ApiResponse<{ events: any[]; total: number; truncated: boolean }>>('/observability/token-usage', { params }),
  getTokenUsageDaily: (params?: { since?: string; until?: string }) =>
    api.get<ApiResponse<{ rows: any[]; total: number }>>('/observability/token-usage/daily', { params }),
  getTokenUsageBuckets: (params?: { since?: number; until?: number; bin?: number }) =>
    api.get<ApiResponse<{ rows: any[]; total: number }>>('/observability/token-usage/buckets', { params }),
  clearTokenUsage: () => api.post<ApiResponse>('/observability/token-usage/clear'),
  // Performance Metrics
  getPerformance: () => api.get<ApiResponse<any>>('/observability/performance'),
  // Traces APIs
  getTraces: (params?: { page?: number; page_size?: number; since?: number; until?: number }) =>
    api.get<ApiResponse<PaginatedData<TraceRecord>>>('/observability/traces', { params }),
  getTrace: (traceId: string) => api.get<ApiResponse<{ cycle: TraceRecord; devices: TraceDevice[] }>>(`/observability/traces/${traceId}`),
  // Agent Runs APIs
  getAgentRuns: (params?: { limit?: number; since?: number; until?: number }) =>
    api.get<ApiResponse<AgentRun[]>>('/observability/agent-runs', { params }),
  getAgentRun: (runId: string) => api.get<ApiResponse<AgentRun>>(`/observability/agent-runs/${runId}`),
  // Stats APIs
  getStats: (name: string, params?: { bucket?: string; since?: number; until?: number }) =>
    api.get<ApiResponse<{ data: any[]; total: number }>>(`/observability/stats/${name}`, { params }),
};

export interface AdminStatus {
  api: { ok: boolean };
  sqlite: { ok: boolean };
  sensor: { total_sensors: number; online_sensors: number };
  rule_engine: { total_rules: number; enabled_rules: number };
}

export interface HeimanProfile {
  label: string;
  model: string;
  base_url: string;
  api_key_masked: string;
  has_key: boolean;
  active?: boolean;
}

export interface HeimanConfig {
  active: HeimanProfile;
  profiles: HeimanProfile[];
}

export const adminApi = {
  getStatus: () => api.get<ApiResponse<AdminStatus>>('/admin/status'),
  getDebug: () => api.get<ApiResponse<{ enabled: boolean }>>('/admin/debug'),
  setDebug: (enabled: boolean) => api.post<ApiResponse<{ enabled: boolean }>>('/admin/debug', { enabled }),
  buildLogPack: () => api.post<ApiResponse<{ filename: string; size_mb: number; file_count: number; path: string }>>('/admin/debug/log-pack'),
  getHeimanConfig: () => api.get<ApiResponse<HeimanConfig>>('/admin/heiman-config'),
  saveHeimanConfig: (data: {
    label: string;
    base_url: string;
    model: string;
    api_key?: string;
    original_label?: string;
    activate?: boolean;
  }) => api.put<ApiResponse<HeimanConfig>>('/admin/heiman-config', data),
  activateHeimanConfig: (label: string) => api.post<ApiResponse<HeimanConfig>>('/admin/heiman-config/activate', { label }),
  deleteHeimanConfig: (label: string) => api.post<ApiResponse<HeimanConfig>>('/admin/heiman-config/delete', { label }),
  testHeimanConfig: (data?: { model?: string; base_url?: string; api_key?: string; label?: string }) =>
    api.post<ApiResponse<any>>('/admin/heiman-config/test', data || {}),
  listHeimanModels: (data: { base_url: string; api_key?: string; label?: string }) =>
    api.post<ApiResponse<any>>('/admin/heiman-config/models', data),
};

export interface MonitorStatus {
  node_count: number;
  uptime_s: number;
  uname?: string;
  resources?: Record<string, any>;
}

export interface MonitorNode {
  name: string;
  kind: string;
  watchdog_s: number;
  lifecycle: string;
  last_progress_at: string | null;
  last_error: string | null;
  detail: Record<string, any>;
  rolling: { success: number; failure: number; total: number };
}

export interface MemorySnapshot {
  ts: number;
  cpu_pct: number;
  rss_mb: number;
  vms_mb: number;
  fd: number;
  threads: number;
  sys_mem_total_mb: number;
  sys_mem_available_mb: number;
  sys_mem_percent: number;
  sys_cpu_pct: number;
  log_size_mb: number;
  log_files: number;
  disk_total_mb: number;
  disk_used_mb: number;
  disk_free_mb: number;
  disk_percent: number;
}

export interface MemorySeries {
  buckets: Array<{
    ts: number;
    rss_mb_avg: number;
    rss_mb_max: number;
    cpu_pct_avg: number;
    samples: number;
  }>;
  count: number;
}

export const monitorApi = {
  getStatus: () => api.get<ApiResponse<MonitorStatus>>('/monitor/status'),
  getNodes: () => api.get<ApiResponse<{ ts: number; nodes: MonitorNode[] }>>('/monitor/nodes'),
  getNode: (name: string) => api.get<ApiResponse<MonitorNode>>(`/monitor/nodes/${name}`),
  getResources: () => api.get<ApiResponse<Record<string, any>>>('/monitor/resources'),
  getMemory: () => api.get<ApiResponse<MemorySnapshot | null>>('/monitor/memory'),
  getMemorySeries: (params?: { window?: '1h' | '6h' | '24h' | '3d'; bucket?: '1m' | '5m' | '1h' }) =>
    api.get<ApiResponse<MemorySeries>>('/monitor/memory/series', { params }),
};

export interface ProfileEntry {
  entry_id: string;
  type: string;
  subject_id: string;
  subject_name: string;
  content: string;
  source: string;
  confidence: number;
  archived: boolean;
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
}

export interface HomeProfileData {
  profile: ProfileEntry[];
  profile_count: number;
  candidates: ProfileEntry[];
  candidates_count: number;
}

export const homeProfileApi = {
  listEntries: (home_id?: string, target: 'profile' | 'candidates' | 'both' = 'both') =>
    api.get<ApiResponse<HomeEntries>>('/home-profile/entries', { params: { home_id, target } }),
  addEntry: (data: { type: string; content: string; subjectId?: string | null; subjectName?: string | null }) =>
    api.post<ApiResponse>('/home-profile/profile:write', { ops: [{ op: 'add', entry: { type: data.type, content: data.content, subject_id: data.subjectId ?? null, subject_name: data.subjectName ?? null, source: 'user_told', confidence: 1.0 } }], user_edit: true }),
  updateEntry: (id: string, data: { type?: string; content?: string; subjectId?: string | null; subjectName?: string | null }) =>
    api.post<ApiResponse>('/home-profile/profile:write', { ops: [{ op: 'update', id, edit: { ...(data.type && { type: data.type }), ...(data.content && { content: data.content }), ...(data.subjectId !== undefined && { subject_id: data.subjectId }), ...(data.subjectName !== undefined && { subject_name: data.subjectName }) } }], user_edit: true }),
  deleteEntry: (id: string) =>
    api.post<ApiResponse>('/home-profile/profile:write', { ops: [{ op: 'delete', id }], user_edit: true }),
  confirmCandidate: (candidateId: string) =>
    api.post<ApiResponse>('/home-profile/profile:write', { ops: [{ op: 'add', from: candidateId }], user_edit: true }),
  ignoreCandidate: (candidateId: string) =>
    api.post<ApiResponse>('/home-profile/candidates:write', { ops: [{ op: 'delete', id: candidateId, date: new Date().toISOString().slice(0, 10) }] }),
  commitProfile: () => api.post<ApiResponse>('/home-profile/commit'),
  getEntries: () => api.get<ApiResponse<HomeProfileData>>('/home-profile/entries'),
  getRendered: () => api.get<ApiResponse<{ content: string }>>('/home-profile/rendered'),
  writeProfile: (entries: Array<{
    entry_id?: string;
    type: string;
    subject_id?: string;
    subject_name?: string;
    content: string;
    confidence?: number;
  }>) => api.post<ApiResponse>('/home-profile/profile:write', { entries }),
  writeCandidates: (candidates: Array<{
    entry_id?: string;
    type: string;
    subject_id?: string;
    subject_name?: string;
    content: string;
    confidence?: number;
  }>) => api.post<ApiResponse>('/home-profile/candidates:write', { candidates }),
  commit: (entry_ids: string[]) => api.post<ApiResponse>('/home-profile/commit', { entry_ids }),
  reset: () => api.post<ApiResponse>('/home-profile/reset'),
};

export interface RoomData {
  id: string;
  name: string;
  homeId: string;
}

export const roomApi = {
  getAll: (home_id?: string) => api.get<ApiResponse<RoomData[]>>('/rooms', { params: { home_id } }),
};

export interface ProductData {
  id: string;
  name: string;
  classified_id?: string;
  classified_name?: string;
  device_type?: string;
  photo_url?: string;
  state?: number;
  metadata?: string;
  project_id?: string;
  project_name?: string;
  describe?: string;
  message_protocol?: string;
  protocol_name?: string;
  transport_protocol?: string;
  network_way?: string;
  configuration?: string;
  creator_id?: string;
  create_time?: number;
  org_id?: string;
  access_id?: string;
  access_provider?: string;
  access_name?: string;
  store_policy?: string;
  store_policy_configuration?: string;
  modifier_id?: string;
  modify_time?: number;
  bind_type?: number;
  network_type?: number;
  target_id?: string;
  dueros_product?: string;
  keep_online_second?: number;
  ifttt?: string;
}

export interface ProductPropertyData {
  id: number;
  product_id: string;
  property_id: string;
  property_name?: string;
  property_type?: string;
  value_type?: string;
  expands?: string;
  description?: string;
  created_at?: string;
}

export interface ProductStats {
  total: number;
  classifications: number;
  by_classification: Array<{
    classified_id: string;
    classified_name: string;
    count: number;
  }>;
}

export const productApi = {
  list: (params?: { classified_name?: string; keyword?: string; limit?: number; offset?: number }) =>
    api.get<ApiResponse<{ items: ProductData[]; total: number }>>('/products', { params }),
  get: (product_id: string) =>
    api.get<ApiResponse<ProductData>>(`/products/${product_id}`),
  getProperties: (product_id: string) =>
    api.get<ApiResponse<ProductPropertyData[]>>(`/products/${product_id}/properties`),
  listClassifications: () =>
    api.get<ApiResponse<Array<{ classified_id: string; classified_name: string; count: number }>>>('/products/classifications'),
  getStats: () =>
    api.get<ApiResponse<ProductStats>>('/products/stats/summary'),
  import: (sql_path?: string) =>
    api.post<ApiResponse<{ count: number; message: string }>>('/products/import', { sql_path }),
  search: (keyword: string, limit?: number) =>
    api.get<ApiResponse<{ items: ProductData[]; total: number }>>('/products', { params: { keyword, limit } }),
};

export interface AIAnalysisResult {
  analysis_id: string;
  analysis_type: string;
  result_data: any;
  timestamp_ms: number;
  anomaly_count: number;
  comfort_score: number | null;
  activity_type: string | null;
  home_id: string | null;
  created_at: string;
}

/** 告警分析结果（规则引擎生成） */
export interface AlertAnalysisResult {
  id: number;
  analysis_id: string;
  event_id: string;
  alert_type: string;
  root_cause: {
    primary_cause: string;
    confidence: number;
    contributing_factors: string[];
    evidence: string[];
    is_false_alarm: boolean;
    false_alarm_reason: string;
  } | null;
  impact: {
    severity: string;
    affected_rooms: string[];
    affected_devices: string[];
    potential_consequences: string[];
    estimated_scope: string;
  } | null;
  remediation: Array<{
    step: number;
    action: string;
    urgency: string;
    expected_outcome: string;
    requires_manual_intervention: boolean;
  }> | null;
  urgency_level: 'critical' | 'high' | 'medium' | 'low';
  recommended_actions: string[] | null;
  raw_response: Record<string, any> | null;
  model_used: string;
  success: number;
  created_at_ms: number;
  created_at: string;
}

export interface TokenUsageEvent {
  id: string;
  timestamp_ms: number;
  model: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_id: string;
  created_at: string;
}

export interface TokenQuotaStatus {
  model: string;
  usage_type: string;
  daily_limit: number;
  warning_threshold: number;
  current_usage: number;
  remaining: number;
  usage_percent: number;
  status: 'ok' | 'warning' | 'exceeded';
  message: string;
}

export interface TokenDailyData {
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface SmartHomeAssistantResponse {
  assistant_mode: string;
  timestamp: string;
  user_id: string;
  anomalies: any[];
  activity: any;
  comfort: any;
  emotion: any;
  behavior_prediction: any;
  energy_optimization: any;
  proactive_actions: any[];
  proactive_actions_total: number;
  proactive_actions_page: number;
  proactive_actions_page_size: number;
  proactive_actions_total_pages: number;
  device_count: number;
  online_count: number;
  connected_protocols: string[];
}

export interface EmotionAnalysisResult {
  emotion: string;
  confidence: number;
  description: string;
  suggested_environment: {
    lighting?: string;
    temperature?: number;
    music?: string;
  };
}

export interface EmotionalProfile {
  user_id: string;
  average_emotion: string;
  emotion_patterns: {
    hour: number;
    emotion: string;
    confidence: number;
  }[];
  preferences: {
    lighting?: string;
    temperature?: number;
    music?: string;
  };
}

export interface EnergyStats {
  daily_stats: {
    date: string;
    consumption_kwh: number;
    generation_kwh: number;
    peak_watts: number;
    avg_watts: number;
  }[];
}

export interface EnergyReport {
  period_days: number;
  total_consumption_kwh: number;
  total_generation_kwh: number;
  average_daily_consumption_kwh: number;
  peak_consumption_watts: number;
  energy_savings_pct: number;
  recommendations: any[];
}

export interface EnergyOptimization {
  current_mode: string;
  recommendations: {
    action: string;
    description: string;
    priority: string;
    estimated_savings_watts: number;
  }[];
  current_price_per_kwh: number;
}

export interface DeviceInfo {
  device_id: string;
  name: string;
  type: string;
  category: string;
  state: string;
  protocol: string;
  properties: any;
}

export interface PrivacyStatus {
  anonymization_enabled: boolean;
  data_retention_days: number;
  federated_learning_enabled: boolean;
  local_only_processing: boolean;
}

export interface LearningStatus {
  is_running: boolean;
  models: Array<{
    name: string;
    status: string;
    last_learning_time: string | null;
    feedback_count: number;
  }>;
  total_feedback_count: number;
  last_cycle_time: string | null;
}

export interface LearningCycle {
  cycle_id: string;
  model_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  feedback_used: number;
  rules_generated: number;
  duration_ms: number | null;
}

export interface LearningRule {
  rule_id: string;
  model_name: string;
  rule_type: string;
  condition: string;
  action: string;
  confidence: number;
  enabled: boolean;
  created_at: string;
  applied_count: number;
}

export interface PerformanceMetric {
  model_name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  feedback_count: number;
  learning_cycles: number;
  window_hours: number;
}

export interface ProblematicPattern {
  pattern_id: string;
  model_name: string;
  pattern_type: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  affected_count: number;
  suggested_fix: string;
  detected_at: string;
}

export const aiApi = {
  getAnalysisResults: (params?: { page?: number; page_size?: number; analysis_type?: string; home_id?: string }) =>
    api.get<ApiResponse<PaginatedData<AIAnalysisResult>>>('/ai/analysis/results', { params }),
  getTokenUsage: (params?: { since_ms?: number; until_ms?: number; model?: string; usage_type?: string }) =>
    api.get<ApiResponse<{ usage: TokenUsageEvent[]; summary: { prompt_tokens: number; completion_tokens: number; total_tokens: number; request_count: number }; truncated: boolean }>>('/ai/token/usage', { params }),
  getTokenQuota: (params?: { model?: string; usage_type?: string }) =>
    api.get<ApiResponse<TokenQuotaStatus>>('/ai/token/quota', { params }),
  setTokenQuota: (model: string, usage_type: string, daily_limit: number, warning_threshold: number) =>
    api.post<ApiResponse<{ status: string; message: string; quota: TokenQuotaStatus }>>('/ai/token/quota', { params: { model, usage_type, daily_limit, warning_threshold } }),
  getTokenDailyUsage: (params?: { since_date?: string; until_date?: string }) =>
    api.get<ApiResponse<{ daily_data: TokenDailyData[]; total_tokens: number }>>('/ai/token/daily', { params }),
  getSmartHomeAssistant: (params?: { user_id?: string; page?: number; page_size?: number }) =>
    api.get<ApiResponse<SmartHomeAssistantResponse>>('/ai/assistant', { params: params || {} }),
  analyzeEmotion: (user_id?: string, activity?: string, hour?: number) =>
    api.get<ApiResponse<EmotionAnalysisResult>>('/ai/emotion', { params: { user_id, activity, hour } }),
  getEmotionalProfile: (user_id?: string) =>
    api.get<ApiResponse<EmotionalProfile>>('/ai/emotion/profile', { params: { user_id } }),
  getEnergyStats: (days?: number) =>
    api.get<ApiResponse<EnergyStats>>('/ai/energy/stats', { params: { days } }),
  getEnergyReport: (days?: number) =>
    api.get<ApiResponse<EnergyReport>>('/ai/energy/report', { params: { days } }),
  getEnergyOptimization: () =>
    api.get<ApiResponse<EnergyOptimization>>('/ai/energy/optimization'),
  getDevices: () =>
    api.get<ApiResponse<{ devices: DeviceInfo[]; count: number; protocols: string[] }>>('/ai/devices'),
  executeDeviceAction: (device_id: string, action: string, params?: string) =>
    api.post<ApiResponse<{ success: boolean; message: string }>>('/ai/devices/action', { params: { device_id, action, params } }),
  getPrivacyStatus: () =>
    api.get<ApiResponse<PrivacyStatus>>('/ai/privacy/status'),
  anonymizeData: (data: string) =>
    api.post<ApiResponse<{ original: any; anonymized: any }>>('/ai/privacy/anonymize', { params: { data } }),
  discoverMatterDevices: () =>
    api.get<ApiResponse<{ devices: any[]; count: number }>>('/ai/matter/devices'),
  commissionMatterDevice: (device_id: string, setup_code: string) =>
    api.post<ApiResponse<{ success: boolean; message: string }>>('/ai/matter/commission', { params: { device_id, setup_code } }),
  // Self-learning APIs
  getLearningStatus: () => api.get<ApiResponse<LearningStatus>>('/ai/learning/status'),
  startLearning: () => api.post<ApiResponse>('/ai/learning/start'),
  stopLearning: () => api.post<ApiResponse>('/ai/learning/stop'),
  getLearningPerformance: (params?: { model_name?: string; window_hours?: number }) =>
    api.get<ApiResponse<Record<string, PerformanceMetric>>>('/ai/learning/performance', { params }),
  getLearningCycles: (params?: { model_name?: string; limit?: number }) =>
    api.get<ApiResponse<LearningCycle[]>>('/ai/learning/cycles', { params }),
  getLearningRules: (params?: { model_name?: string }) =>
    api.get<ApiResponse<LearningRule[]>>('/ai/learning/rules', { params }),
  submitLearningFeedback: (data: {
    model_name: string;
    input_features: Record<string, unknown>;
    predicted_output: Record<string, unknown>;
    actual_output?: Record<string, unknown>;
    feedback_type: string;
    confidence: number;
  }) => api.post<ApiResponse>('/ai/learning/feedback', data),
  triggerLearningCycle: (model_name: string) =>
    api.post<ApiResponse>('/ai/learning/trigger', { params: { model_name } }),
  getProblematicPatterns: (model_name: string) =>
    api.get<ApiResponse<ProblematicPattern[]>>('/ai/learning/problematic-patterns', { params: { model_name } }),
  // 告警分析 API（规则引擎）
  getAlertAnalyses: (params?: { page?: number; page_size?: number; alert_type?: string; urgency_level?: string }) =>
    api.get<ApiResponse<PaginatedData<AlertAnalysisResult>>>('/ai/alerts', { params }),
  getAlertAnalysis: (analysis_id: string) =>
    api.get<ApiResponse<AlertAnalysisResult>>(`/ai/alerts/${analysis_id}`),
  getAlertAnalysisByEvent: (event_id: string) =>
    api.get<ApiResponse<AlertAnalysisResult[]>>(`/ai/alerts/event/${event_id}`),
};

/* ──────── ML 模型 API（V2 机器学习） ──────── */

export interface MlModelInfo {
  name: string;
  type: string;
  status: 'ready' | 'not_trained' | 'training' | 'error';
  accuracy: number | null;
  feature_count: number;
  samples: number;
  last_trained: string | null;
  error: string | null;
  trainable?: boolean;
  training_source?: 'bootstrap' | 'real_feedback' | 'mixed' | 'unknown';
}

export interface MlModelDetail extends MlModelInfo {
  feature_names: string[];
  hyperparameters: Record<string, unknown>;
}

export interface TrainResult {
  model_name: string;
  accuracy: number;
  samples: number;
  train_time: number;
  message: string;
  training_source?: 'bootstrap' | 'real_feedback' | 'mixed' | 'unknown';
}

export interface RetrainCheckResult {
  model_name: string;
  needs_retrain: boolean;
  accumulated_feedback: number;
  threshold: number;
  current_accuracy: number | null;
}

export interface AbExperiment {
  name: string;
  model_name: string;
  ml_ratio: number;
  shadow_mode: boolean;
  min_sample_size: number;
  status: 'running' | 'stopped' | 'completed';
  start_time: string;
  variant_a_samples: number;
  variant_b_samples: number;
}

export interface AbAnalysisResult {
  experiment_name: string;
  variant_a_metrics: Record<string, number>;
  variant_b_metrics: Record<string, number>;
  winner: 'a' | 'b' | 'tie';
  confidence: number;
  improvement: Record<string, number>;
}

export interface OnlineLearningStatus {
  models: Array<{
    name: string;
    feedback_since_last_train: number;
    retrain_threshold: number;
    last_retrain: string | null;
    accuracy_trend: number[];
  }>;
}

export interface FeatureImportanceItem {
  feature: string;
  importance: number;
  std?: number;
}

export interface ModelExplanation {
  model_name: string;
  feature_importance: FeatureImportanceItem[];
  top_features: string[];
  model_type: string;
  accuracy: number | null;
}

export interface PredictionExplanation {
  features: Record<string, number>;
  contributions: Record<string, number>;
  top_contributors: Array<{ feature: string; contribution: number }>;
}

export const mlApi = {
  getModels: () => api.get<ApiResponse<{ models: MlModelInfo[]; total: number }>>('/ai/ml/models'),
  getModelDetail: (name: string) => api.get<ApiResponse<MlModelDetail>>(`/ai/ml/models/${name}`),
  trainModel: (name: string) => api.post<ApiResponse<TrainResult>>(`/ai/ml/models/${name}/train`),
  trainAllModels: () => api.post<ApiResponse<{ results: TrainResult[] }>>('/ai/ml/models/train-all'),
  submitFeedback: (data: {
    model_name: string;
    actual: Record<string, unknown>;
    predicted: Record<string, unknown>;
    score?: number;
  }) => api.post<ApiResponse>(`/ai/ml/models/${data.model_name}/feedback`, data),
  checkRetrain: (name: string) =>
    api.post<ApiResponse<RetrainCheckResult>>(`/ai/ml/models/${name}/check-retrain`),

  getHealth: () => api.get<ApiResponse<Record<string, unknown>>>('/ai/ml/health'),

  startExperiment: (config: {
    name: string;
    model_name: string;
    ml_ratio?: number;
    shadow_mode?: boolean;
    min_sample_size?: number;
  }) => api.post<ApiResponse>('/ai/ml/ab/start', config),
  getExperimentStatus: () => api.get<ApiResponse<{ experiments: AbExperiment[] }>>('/ai/ml/ab/status'),
  analyzeExperiment: (name: string) =>
    api.post<ApiResponse<AbAnalysisResult>>('/ai/ml/ab/analyze', { experiment_name: name }),
  promoteExperiment: (name: string) =>
    api.post<ApiResponse>('/ai/ml/ab/promote', { experiment_name: name }),

  getOnlineStatus: () => api.get<ApiResponse<OnlineLearningStatus>>('/ai/ml/online/status'),
  retrainOnline: (name: string) =>
    api.post<ApiResponse<TrainResult>>(`/ai/ml/online/retrain?model_name=${name}`),

  explainModel: (name: string) => api.get<ApiResponse<ModelExplanation>>(`/ai/ml/explain/${name}`),
  explainPrediction: (name: string, features: Record<string, number>) =>
    api.post<ApiResponse<PredictionExplanation>>('/ai/ml/explain/prediction', { model_name: name, features }),
  getFeatureImportance: (name: string) =>
    api.get<ApiResponse<{ model_name: string; feature_importance: FeatureImportanceItem[] }>>(
      `/ai/ml/feature-importance/${name}`
    ),
};

export default api;