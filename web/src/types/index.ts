export type SensorType = 'smoke' | 'temperature' | 'humidity' | 'co' | 'water' | 'contact' | 'motion' | 'plug' | 'siren' | 'button' | 'gateway' | 'remote';
export type SensorStatus = 'normal' | 'warning' | 'alarm' | 'offline' | 'lowBattery';
export type EventType = 'alarm' | 'warning' | 'info';
export type EventLevel = 'critical' | 'high' | 'medium' | 'low' | 'warning' | 'info';
export type RuleActionType = 'LOG' | 'ALERT' | 'WEBHOOK';
export type Operator = '>' | '<' | '=' | '!=' | '>=' | '<=';

export type HomeEntryType =
  | 'member_persona'
  | 'member_health'
  | 'member_routine'
  | 'member_entertain'
  | 'member_preference'
  | 'family'
  | 'space'
  | 'device';

export type HomeEntrySource = 'observed' | 'user_told';

export interface HomeEntry {
  id: string;
  type: HomeEntryType;
  subjectId?: string | null;
  subjectName?: string | null;
  content: string;
  confidence: number;
  evidenceCount: number;
  firstSeen: string;
  lastSeen: string;
  source: HomeEntrySource;
  evidenceLog?: string[];
  archived?: boolean;
}

export interface HomeEntries {
  profile: HomeEntry[];
  candidates: HomeEntry[];
  readyToPromote: string[];
}

export type TaskStatus = 'active' | 'paused';
export type TaskRecordKind = 'progress' | 'duration' | 'event';

export interface TaskRecordSummary {
  kind: TaskRecordKind;
  completed: boolean;
  activeSession: { startedAt: string; elapsedMinutes: number } | null;
  derived: Record<string, unknown>;
}

export interface Task {
  task_id: string;
  description: string;
  status: TaskStatus;
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

export interface SensorData {
  did: string;
  name: string;
  sensor_type: SensorType;
  status: SensorStatus;
  value: number;
  unit: string;
  timestamp: string;
  room_id?: string;
  room_name?: string;
  home_id?: string;
  icon?: string;
  battery?: number | null;
  rssi?: number | null;
  tamperState?: number | null;
  sensorLifeStatus?: number | null;
  alarmState?: number | null;
  smokeState?: number | null;
  gasState?: number | null;
  waterState?: number | null;
  motionState?: number | null;
  switchState?: number | null;
  temperature?: number | null;
  humidity?: number | null;
  co2?: number | null;
  pm25?: number | null;
  hcho?: number | null;
}

export interface SensorEvent {
  event_id: string;
  did: string;
  device_name?: string;
  sensor_type: string;
  event_type: EventType;
  level: EventLevel;
  message: string;
  description?: string;
  timestamp: string;
  acknowledged: boolean;
  home_id?: string;
}

export interface RuleCondition {
  did?: string;
  sensor_type?: SensorType;
  operator: Operator;
  threshold: number;
  window_seconds?: number | null;
}

export interface RuleAction {
  action_id?: string | null;
  action_type: 'alert' | 'log' | 'webhook' | 'notification';
  payload?: {
    title?: string;
    message?: string;
  };
}

export interface Rule {
  rule_id: string;
  name: string;
  description: string;
  enabled: boolean;
  conditions: RuleCondition[];
  actions: RuleAction[];
  cooldown_minutes: number;
  home_id?: string;
  created_at: string;
  updated_at: string;
}

export interface SensorHistoryData {
  timestamp: string;
  value: number;
}
