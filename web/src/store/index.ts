import { create } from 'zustand';
import type { SensorData, SensorEvent, Rule, HomeEntry, HomeEntries, HomeEntryType, Task } from '../types';
import type { HomeData, Member } from '../api/client';
import { sensorApi, eventApi, ruleApi, homeApi, authApi, homeProfileApi, taskApi } from '../api/client';
import { statusChecker } from '../api/status-checker';

interface UserProfile {
  username: string;
  nickName?: string;
  email: string;
  phone: string;
  bindStatus: boolean;
  userId?: string;
  avatar?: string;
}

interface AppState {
  sensors: SensorData[];
  events: SensorEvent[];
  rules: Rule[];
  homes: HomeData[];
  homeEntries: HomeEntries | null;
  tasks: Task[];
  currentHomeId: string | null;
  profile: UserProfile | null;
  loading: {
    sensors: boolean;
    events: boolean;
    rules: boolean;
    homes: boolean;
    profile: boolean;
    homeEntries: boolean;
    tasks: boolean;
  };
  fetchSensors: (force?: boolean) => Promise<void>;
  fetchEvents: (force?: boolean) => Promise<void>;
  fetchRules: (force?: boolean) => Promise<void>;
  fetchHomes: (force?: boolean) => Promise<void>;
  fetchProfile: (force?: boolean) => Promise<UserProfile | null>;
  fetchHomeEntries: (force?: boolean) => Promise<void>;
  fetchTasks: (force?: boolean) => Promise<void>;
  switchHome: (homeId: string) => Promise<void>;
  acknowledgeEvent: (eventId: string) => Promise<void>;
  batchAcknowledgeEvents: (eventIds: string[]) => Promise<void>;
  createRule: (data: Omit<Rule, 'rule_id' | 'created_at' | 'updated_at'>) => Promise<void>;
  updateRule: (ruleId: string, data: Partial<Rule>) => Promise<void>;
  deleteRule: (ruleId: string) => Promise<void>;
  addMember: (homeId: string, data: { name: string; role?: string }) => Promise<void>;
  removeMember: (homeId: string, memberId: string) => Promise<void>;
  updateMember: (homeId: string, memberId: string, data: { name?: string; role?: string }) => Promise<void>;
  addHomeEntry: (data: { type: HomeEntryType; content: string; subjectId?: string | null; subjectName?: string | null }) => Promise<void>;
  updateHomeEntry: (id: string, data: { type?: HomeEntryType; content?: string; subjectId?: string | null; subjectName?: string | null }) => Promise<void>;
  deleteHomeEntry: (id: string) => Promise<void>;
  confirmCandidate: (candidateId: string) => Promise<void>;
  ignoreCandidate: (candidateId: string) => Promise<void>;
  setTaskEnabled: (taskId: string, enabled: boolean) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  runStatusCheck: () => Promise<void>;
}

const CACHE_TTL = 60 * 1000;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  promise?: Promise<T>;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractData<T>(response: any): T[] {
  if (response.data !== undefined) {
    if (response.data.data !== undefined && Array.isArray(response.data.data)) {
      return response.data.data as T[];
    }
    if (Array.isArray(response.data)) {
      return response.data as T[];
    }
  }
  return [];
}

const _pendingFetches: Record<string, Promise<any> | undefined> = {};
const _cache: Record<string, { data: any; timestamp: number }> = {};

function withDeduplication<T>(key: string, fetcher: () => Promise<T>, ttl: number = CACHE_TTL): Promise<T> {
  const now = Date.now();
  const cached = _cache[key];
  if (cached && now - cached.timestamp < ttl) {
    return Promise.resolve(cached.data);
  }
  if (_pendingFetches[key]) {
    return _pendingFetches[key] as Promise<T>;
  }
  const promise = fetcher().then((data) => {
    _cache[key] = { data, timestamp: Date.now() };
    _pendingFetches[key] = undefined;
    return data;
  }).catch((error) => {
    _pendingFetches[key] = undefined;
    throw error;
  });
  _pendingFetches[key] = promise;
  return promise;
}

export const useAppStore = create<AppState>((set, get) => ({
  sensors: [],
  events: [],
  rules: [],
  homes: [],
  homeEntries: null,
  tasks: [],
  currentHomeId: null,
  profile: null,
  loading: {
    sensors: false,
    events: false,
    rules: false,
    homes: false,
    profile: false,
    homeEntries: false,
    tasks: false,
  },
  fetchSensors: async (force = false) => {
    const currentHomeId = get().currentHomeId;
    const cacheKey = `sensors_${currentHomeId || 'all'}`;
    if (!force && get().sensors.length > 0 && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.sensors) {
      return;
    }
    set({ loading: { ...get().loading, sensors: true } });
    try {
      const data = await withDeduplication(cacheKey, async () => {
        const response = await sensorApi.getAll(currentHomeId);
        return extractData<SensorData>(response);
      });
      set({ sensors: data, loading: { ...get().loading, sensors: false } });
    } catch (error) {
      console.error('Failed to fetch sensors:', error);
      set({ loading: { ...get().loading, sensors: false } });
    }
  },
  fetchEvents: async (force = false) => {
    const currentHomeId = get().currentHomeId;
    const cacheKey = `events_${currentHomeId || 'all'}`;
    if (!force && get().events.length > 0 && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.events) {
      return;
    }
    set({ loading: { ...get().loading, events: true } });
    try {
      const data = await withDeduplication(cacheKey, async () => {
        const response = await eventApi.getAll({ home_id: currentHomeId });
        return extractData<SensorEvent>(response);
      });
      set({ events: data, loading: { ...get().loading, events: false } });
    } catch (error) {
      console.error('Failed to fetch events:', error);
      set({ loading: { ...get().loading, events: false } });
    }
  },
  fetchRules: async (force = false) => {
    const cacheKey = 'rules';
    if (!force && get().rules.length > 0 && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.rules) {
      return;
    }
    set({ loading: { ...get().loading, rules: true } });
    try {
      const data = await withDeduplication(cacheKey, async () => {
        const response = await ruleApi.getAll();
        return extractData<Rule>(response);
      });
      set({ rules: data, loading: { ...get().loading, rules: false } });
    } catch (error) {
      console.error('Failed to fetch rules:', error);
      set({ loading: { ...get().loading, rules: false } });
    }
  },
  fetchHomes: async (force = false) => {
    const cacheKey = 'homes';
    if (!force && get().homes.length > 0 && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.homes) {
      return;
    }
    set({ loading: { ...get().loading, homes: true } });
    try {
      const data = await withDeduplication(cacheKey, async () => {
        const response = await homeApi.getAll();
        return extractData<HomeData>(response);
      });
      set({ homes: data, loading: { ...get().loading, homes: false } });
      
      if (data.length > 0) {
        if (!get().currentHomeId) {
          try {
            const lastHomeResponse = await authApi.getLastHome();
            const lastHomeId = lastHomeResponse.data?.data?.home_id;
            if (lastHomeId && data.some(h => h.id === lastHomeId)) {
              set({ currentHomeId: lastHomeId });
              console.log('[Store] Restored last home:', lastHomeId);
            } else {
              set({ currentHomeId: data[0].id });
            }
          } catch (error) {
            console.warn('[Store] Failed to get last home, using first home:', error);
            set({ currentHomeId: data[0].id });
          }
        }
      }
    } catch (error) {
      console.error('Failed to fetch homes:', error);
      set({ loading: { ...get().loading, homes: false } });
    }
  },
  fetchProfile: async (force = false): Promise<UserProfile | null> => {
    const cacheKey = 'profile';
    if (!force && get().profile && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return get().profile;
    }
    if (get().loading.profile) {
      return get().profile;
    }
    set({ loading: { ...get().loading, profile: true } });
    try {
      const profile = await withDeduplication(cacheKey, async () => {
        const response = await authApi.getProfile();
        const data = response.data?.data;
        if (data) {
          const username = data.nickName || data.username || '';
          if (username) {
            localStorage.setItem('heiman_username', username);
          }
          return data as UserProfile;
        }
        return null;
      });
      set({ profile, loading: { ...get().loading, profile: false } });
      return profile;
    } catch (error) {
      console.error('Failed to fetch profile:', error);
      set({ loading: { ...get().loading, profile: false } });
      return null;
    }
  },
  switchHome: async (homeId: string) => {
    set({ currentHomeId: homeId });
    await Promise.all([
      get().fetchSensors(true),
      get().fetchEvents(true),
      get().fetchRules(true),
    ]);
    try {
      await authApi.saveHomeSelection(homeId);
      console.log('[Store] Home selection saved:', homeId);
    } catch (error) {
      console.error('[Store] Failed to save home selection:', error);
    }
  },
  acknowledgeEvent: async (eventId) => {
    try {
      await eventApi.acknowledge(eventId);
      set({
        events: get()
          .events.map((event) =>
            event.event_id === eventId ? { ...event, acknowledged: true } : event
          ),
      });
    } catch (error) {
      console.error('Failed to acknowledge event:', error);
    }
  },
  batchAcknowledgeEvents: async (eventIds) => {
    try {
      await eventApi.batchAcknowledge(eventIds);
      const idSet = new Set(eventIds);
      set({
        events: get().events.map((event) =>
          idSet.has(event.event_id) ? { ...event, acknowledged: true } : event
        ),
      });
    } catch (error) {
      console.error('Failed to batch acknowledge events:', error);
    }
  },
  createRule: async (data) => {
    try {
      const response = await ruleApi.create(data);
      const newRule = response.data?.data || response.data;
      if (newRule && typeof newRule === 'object' && 'rule_id' in newRule) {
        set({ rules: [...get().rules, newRule as Rule] });
      }
    } catch (error) {
      console.error('Failed to create rule:', error);
    }
  },
  updateRule: async (ruleId, data) => {
    try {
      const response = await ruleApi.update(ruleId, data);
      const updatedRule = response.data?.data || response.data;
      if (updatedRule && typeof updatedRule === 'object' && 'rule_id' in updatedRule) {
        set({
          rules: get()
            .rules.map((rule) => (rule.rule_id === ruleId ? updatedRule as Rule : rule)),
        });
      }
    } catch (error) {
      console.error('Failed to update rule:', error);
    }
  },
  deleteRule: async (ruleId) => {
    try {
      await ruleApi.delete(ruleId);
      set({ rules: get().rules.filter((rule) => rule.rule_id !== ruleId) });
    } catch (error) {
      console.error('Failed to delete rule:', error);
    }
  },
  addMember: async (homeId, data) => {
    try {
      const response = await homeApi.addMember(homeId, data);
      const newMember = response.data?.data || response.data;
      if (newMember && typeof newMember === 'object') {
        set({
          homes: get().homes.map((home) =>
            home.id === homeId
              ? { ...home, members: [...home.members, newMember as Member] }
              : home
          ),
        });
      }
    } catch (error) {
      console.error('Failed to add member:', error);
    }
  },
  removeMember: async (homeId, memberId) => {
    try {
      await homeApi.removeMember(homeId, memberId);
      set({
        homes: get().homes.map((home) =>
          home.id === homeId
            ? { ...home, members: home.members.filter((m) => m.id !== memberId) }
            : home
        ),
      });
    } catch (error) {
      console.error('Failed to remove member:', error);
    }
  },
  updateMember: async (homeId, memberId, data) => {
    try {
      const response = await homeApi.updateMember(homeId, memberId, data);
      const updatedMember = response.data?.data || response.data;
      if (updatedMember && typeof updatedMember === 'object') {
        set({
          homes: get().homes.map((home) =>
            home.id === homeId
              ? {
                  ...home,
                  members: home.members.map((m) =>
                    m.id === memberId ? updatedMember as Member : m
                  ),
                }
              : home
          ),
        });
      }
    } catch (error) {
      console.error('Failed to update member:', error);
    }
  },
  fetchHomeEntries: async (force = false) => {
    const currentHomeId = get().currentHomeId;
    const cacheKey = `home_entries_${currentHomeId || 'all'}`;
    if (!force && get().homeEntries && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.homeEntries) {
      return;
    }
    set({ loading: { ...get().loading, homeEntries: true } });
    try {
      const response = await homeProfileApi.listEntries(currentHomeId);
      const data = response.data?.data || null;
      if (data) {
        _cache[cacheKey] = { data, timestamp: Date.now() };
      }
      set({ homeEntries: data, loading: { ...get().loading, homeEntries: false } });
    } catch (error) {
      console.error('Failed to fetch home entries:', error);
      set({ loading: { ...get().loading, homeEntries: false } });
    }
  },
  fetchTasks: async (force = false) => {
    const currentHomeId = get().currentHomeId;
    const cacheKey = `tasks_${currentHomeId || 'all'}`;
    if (!force && get().tasks.length > 0 && _cache[cacheKey] && Date.now() - _cache[cacheKey].timestamp < CACHE_TTL) {
      return;
    }
    if (get().loading.tasks) {
      return;
    }
    set({ loading: { ...get().loading, tasks: true } });
    try {
      const data = await withDeduplication(cacheKey, async () => {
        const response = await taskApi.getAll(currentHomeId);
        return extractData<Task>(response);
      });
      set({ tasks: data, loading: { ...get().loading, tasks: false } });
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
      set({ loading: { ...get().loading, tasks: false } });
    }
  },
  addHomeEntry: async (data) => {
    try {
      await homeProfileApi.addEntry(data);
      await get().fetchHomeEntries(true);
    } catch (error) {
      console.error('Failed to add home entry:', error);
    }
  },
  updateHomeEntry: async (id, data) => {
    try {
      await homeProfileApi.updateEntry(id, data);
      await get().fetchHomeEntries(true);
    } catch (error) {
      console.error('Failed to update home entry:', error);
    }
  },
  deleteHomeEntry: async (id) => {
    try {
      await homeProfileApi.deleteEntry(id);
      await get().fetchHomeEntries(true);
    } catch (error) {
      console.error('Failed to delete home entry:', error);
    }
  },
  confirmCandidate: async (candidateId) => {
    try {
      await homeProfileApi.confirmCandidate(candidateId);
      await get().fetchHomeEntries(true);
    } catch (error) {
      console.error('Failed to confirm candidate:', error);
    }
  },
  ignoreCandidate: async (candidateId) => {
    try {
      await homeProfileApi.ignoreCandidate(candidateId);
      await get().fetchHomeEntries(true);
    } catch (error) {
      console.error('Failed to ignore candidate:', error);
    }
  },
  setTaskEnabled: async (taskId, enabled) => {
    try {
      await taskApi.setEnabled(taskId, enabled);
      await get().fetchTasks(true);
    } catch (error) {
      console.error('Failed to set task enabled:', error);
    }
  },
  deleteTask: async (taskId) => {
    try {
      await taskApi.delete(taskId);
      await get().fetchTasks(true);
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  },
  runStatusCheck: async () => {
    console.log('[AppStore] Running status check...');
    await statusChecker.runFullCheck();
  },
}));