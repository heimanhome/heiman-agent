import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Users, UserPlus, Edit, Trash2, Loader2, FileText, CheckSquare, Plus, X, AlertCircle, CheckCircle, RefreshCw, User, Crown, Shield } from 'lucide-react';
import { personApi, type Person } from '../api/client';
import { useAppStore } from '../store';
import type { HomeEntry, HomeEntryType, Task, ProgressRecord, DurationRecord, EventRecord } from '../types';

const entryTypeLabels: Record<HomeEntryType, string> = {
  member_persona: '成员画像',
  member_health: '健康信息',
  member_routine: '生活习惯',
  member_entertain: '兴趣爱好',
  member_preference: '偏好设置',
  family: '家庭信息',
  space: '空间信息',
  device: '设备信息',
};

export function Persons() {
  const { t } = useTranslation('app');
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({ name: '', role: '' });

  const {
    homeEntries,
    tasks,
    fetchHomeEntries,
    fetchTasks,
    addHomeEntry,
    updateHomeEntry,
    deleteHomeEntry,
    confirmCandidate,
    ignoreCandidate,
    setTaskEnabled,
    deleteTask,
    fetchHomes,
    currentHomeId,
  } = useAppStore();

  const [showEntryForm, setShowEntryForm] = useState(false);
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);
  const [entryFormData, setEntryFormData] = useState({
    type: 'family' as HomeEntryType,
    content: '',
    subjectId: null as string | null,
    subjectName: null as string | null,
  });

  useEffect(() => {
    fetchHomes();
  }, [fetchHomes]);

  useEffect(() => {
    if (currentHomeId) {
      fetchHomeEntries();
      fetchTasks();
    }
  }, [currentHomeId, fetchHomeEntries, fetchTasks]);

  const loadPersons = async () => {
    setLoading(true);
    try {
      const r = await personApi.getAll(currentHomeId || undefined);
      setPersons(r.data.data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentHomeId) {
      loadPersons();
    }
  }, [currentHomeId]);

  const handleCreatePerson = async () => {
    if (!formData.name.trim()) return;
    await personApi.create({ name: formData.name, role: formData.role });
    setFormData({ name: '', role: '' });
    await loadPersons();
  };

  const handleUpdatePerson = async (id: string) => {
    if (!formData.name.trim()) return;
    await personApi.update(id, { name: formData.name, role: formData.role });
    setEditingId(null);
    setFormData({ name: '', role: '' });
    await loadPersons();
  };

  const handleDeletePerson = async (id: string) => {
    if (!confirm(t('confirmDelete'))) return;
    await personApi.delete(id);
    await loadPersons();
  };

  const startEditPerson = (p: Person) => {
    setEditingId(p.id);
    setFormData({ name: p.name, role: p.role || '' });
  };

  const handleSyncMembers = async () => {
    if (!currentHomeId) return;
    setSyncing(true);
    try {
      const r = await personApi.sync(currentHomeId);
      if (r.data.data?.members) {
        setPersons(r.data.data.members);
      }
    } catch (e) {
      console.error('Sync failed:', e);
    } finally {
      setSyncing(false);
    }
  };

  const handleSaveEntry = async () => {
    if (!entryFormData.content.trim()) return;
    if (editingEntryId) {
      await updateHomeEntry(editingEntryId, entryFormData);
    } else {
      await addHomeEntry(entryFormData);
    }
    setShowEntryForm(false);
    setEditingEntryId(null);
    setEntryFormData({ type: 'family', content: '', subjectId: null, subjectName: null });
  };

  const startEditEntry = (entry: HomeEntry) => {
    setEditingEntryId(entry.id);
    setEntryFormData({
      type: entry.type,
      content: entry.content,
      subjectId: entry.subjectId,
      subjectName: entry.subjectName,
    });
    setShowEntryForm(true);
  };

  const getRoleIcon = (role?: string | null, isHomeRoot?: number | null) => {
    if (role === 'owner' || isHomeRoot === 1) return <Crown className="w-4 h-4 text-yellow-400" />;
    if (role === 'admin') return <Shield className="w-4 h-4 text-[#00d4ff]" />;
    return <User className="w-4 h-4 text-[#6b7a9a]" />;
  };

  const getRoleLabel = (role?: string | null, isHomeRoot?: number | null) => {
    if (role === 'owner' || isHomeRoot === 1) return t('roleOwner');
    if (role === 'admin') return t('roleAdmin');
    if (role === 'member') return t('roleMember');
    return t('roleMember');
  };

  const renderTaskRecord = (task: Task) => {
    if (!task.record) {
      return <p className="text-xs text-[#6b7a9a] mt-2">{t('noRecord')}</p>;
    }
    const r = task.record;
    if (r.kind === 'progress') {
      const rec = r as ProgressRecord;
      const pct = Math.min(100, Math.round((rec.current / Math.max(1, rec.target)) * 100));
      return (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-[#6b7a9a] mb-1">
            <span>{rec.current} / {rec.target} {rec.unit}</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 bg-[#0f1419] rounded overflow-hidden">
            <div className="h-full bg-[#00d4ff]" style={{ width: `${pct}%` }} />
          </div>
        </div>
      );
    }
    if (r.kind === 'duration') {
      const rec = r as DurationRecord;
      return (
        <div className="mt-3">
          <p className="text-xs text-[#6b7a9a]">
            {rec.accumulated_minutes} / {rec.target_minutes} {t('minutes')}
            {rec.active_session_start_at && <span className="ml-2 text-[#00ff88]">● {t('active')}</span>}
          </p>
        </div>
      );
    }
    const rec = r as EventRecord;
    return (
      <div className="mt-3">
        <p className="text-xs text-[#6b7a9a]">
          {t('total')}: {rec.total_count} | {t('today')}: {rec.today_count}
        </p>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6" />
            {t('persons')}
          </h1>
          <p className="text-sm text-[#6b7a9a]">{t('personsDescription')}</p>
        </div>
        <button
          onClick={handleSyncMembers}
          disabled={syncing || !currentHomeId}
          className="flex items-center gap-2 px-4 py-2 bg-[#00d4ff] text-[#0a1628] font-medium rounded-xl hover:bg-[#00d4ff]/90 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? t('syncingMembers') : t('syncMembers')}
        </button>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-4 border border-white/5">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <UserPlus className="w-5 h-5" />
          {editingId ? t('editPerson') : t('addPerson')}
        </h2>
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder={t('namePlaceholder')}
            className="flex-1 min-w-[200px] bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#00d4ff]/50"
          />
          <input
            type="text"
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            placeholder={t('rolePlaceholder')}
            className="flex-1 min-w-[200px] bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#00d4ff]/50"
          />
          {editingId ? (
            <>
              <button
                onClick={() => handleUpdatePerson(editingId)}
                className="px-4 py-2 bg-[#00d4ff] text-[#0a0e1a] rounded-xl font-semibold hover:bg-[#00b8e6]"
              >
                {t('save')}
              </button>
              <button
                onClick={() => {
                  setEditingId(null);
                  setFormData({ name: '', role: '' });
                }}
                className="px-4 py-2 bg-white/5 text-white rounded-xl hover:bg-white/10"
              >
                {t('cancel')}
              </button>
            </>
          ) : (
            <button
              onClick={handleCreatePerson}
              className="px-4 py-2 bg-[#00d4ff] text-[#0a0e1a] rounded-xl font-semibold hover:bg-[#00b8e6]"
            >
              {t('add')}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-[#00d4ff]" />
        </div>
      ) : persons.length === 0 ? (
        <div className="bg-[#0f2137] rounded-xl p-12 text-center border border-white/5">
          <Users className="w-12 h-12 mx-auto mb-4 text-[#6b7a9a]" />
          <p className="text-white mb-2">{t('noPersons')}</p>
          <p className="text-sm text-[#6b7a9a]">{t('syncMembersHint')}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {persons.map((p) => (
            <div key={p.id} className="bg-[#0f2137] rounded-2xl p-5 border border-white/5 hover:border-[#00d4ff]/30 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#00d4ff]/20 to-[#00d4ff]/5 flex items-center justify-center">
                    <User className="w-6 h-6 text-[#00d4ff]" />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold flex items-center gap-2">
                      {p.alias_name || p.name}
                      {getRoleIcon(p.role, p.is_home_root)}
                    </h3>
                    <p className="text-xs text-[#6b7a9a]">{getRoleLabel(p.role, p.is_home_root)}</p>
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => startEditPerson(p)}
                    className="p-1.5 hover:bg-white/5 rounded-lg"
                    aria-label={t('edit')}
                  >
                    <Edit className="w-4 h-4 text-[#00d4ff]" />
                  </button>
                  <button
                    onClick={() => handleDeletePerson(p.id)}
                    className="p-1.5 hover:bg-white/5 rounded-lg"
                    aria-label={t('delete')}
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </button>
                </div>
              </div>
              {p.user_account && (
                <p className="text-xs text-[#6b7a9a]">账号：{p.user_account}</p>
              )}
              {p.remark && (
                <p className="text-xs text-[#4a5568] mt-1">{p.remark}</p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <FileText className="w-5 h-5" />
              {t('homeProfile')}
            </h2>
            <p className="text-xs text-[#6b7a9a]">{t('homeProfileDescription')}</p>
          </div>
          <button
            onClick={() => setShowEntryForm(true)}
            className="flex items-center gap-1 text-sm text-[#00d4ff] hover:underline"
          >
            <Plus className="w-4 h-4" />
            {t('addEntry')}
          </button>
        </div>

        {homeEntries?.profile && homeEntries.profile.length > 0 ? (
          <div className="space-y-3">
            {homeEntries.profile.map((entry) => (
              <div key={entry.id} className="bg-white/5 rounded-xl p-4 flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 bg-[#00d4ff]/20 text-[#00d4ff] rounded-full">
                      {t(`entryTypeLabels.${entry.type}`)}
                    </span>
                    {entry.subjectName && (
                      <span className="text-xs text-[#6b7a9a]">{entry.subjectName}</span>
                    )}
                  </div>
                  <p className="text-sm text-white">{entry.content}</p>
                  <p className="text-xs text-[#4a5568] mt-1">
                    {t('lastUpdate')}: {new Date(entry.lastSeen).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex gap-1 ml-4">
                  <button
                    onClick={() => startEditEntry(entry)}
                    className="p-1.5 hover:bg-white/5 rounded-lg"
                    aria-label={t('edit')}
                  >
                    <Edit className="w-4 h-4 text-[#00d4ff]" />
                  </button>
                  <button
                    onClick={() => deleteHomeEntry(entry.id)}
                    className="p-1.5 hover:bg-white/5 rounded-lg"
                    aria-label={t('delete')}
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <FileText className="w-10 h-10 mx-auto mb-3 text-[#6b7a9a]" />
            <p className="text-[#6b7a9a]">{t('noHomeProfile')}</p>
            <p className="text-xs text-[#4a5568]">{t('homeProfileHint')}</p>
          </div>
        )}

        {homeEntries?.candidates && homeEntries.candidates.length > 0 && (
          <div className="mt-6 pt-6 border-t border-white/5">
            <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[#ffa502]" />
              {t('pendingCandidates')} ({homeEntries.candidates.length})
            </h3>
            <div className="space-y-3">
              {homeEntries.candidates.map((candidate) => (
                <div key={candidate.id} className="bg-[#ffa502]/10 rounded-xl p-4 flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 bg-[#ffa502]/20 text-[#ffa502] rounded-full">
                        {t(`entryTypeLabels.${candidate.type}`)}
                      </span>
                    </div>
                    <p className="text-sm text-white">{candidate.content}</p>
                    <p className="text-xs text-[#4a5568] mt-1">
                      {t('confidence')}: {Math.round(candidate.confidence * 100)}%
                    </p>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => confirmCandidate(candidate.id)}
                      className="px-3 py-1.5 bg-[#00ff88] text-[#0a0e1a] text-xs rounded-lg font-medium hover:bg-[#00e078]"
                    >
                      {t('confirm')}
                    </button>
                    <button
                      onClick={() => ignoreCandidate(candidate.id)}
                      className="px-3 py-1.5 bg-white/5 text-white text-xs rounded-lg hover:bg-white/10"
                    >
                      {t('ignore')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <CheckSquare className="w-5 h-5" />
              {t('tasks')}
            </h2>
            <p className="text-xs text-[#6b7a9a]">{t('tasksDescription')}</p>
          </div>
        </div>

        {tasks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tasks.map((task) => (
              <div key={task.task_id} className="bg-white/5 rounded-xl p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="text-white font-semibold">{task.description}</h3>
                    {task.status === 'paused' && (
                      <span className="text-xs text-yellow-400">● {t('paused')}</span>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setTaskEnabled(task.task_id, task.status === 'paused')}
                      className="p-1.5 hover:bg-white/5 rounded-lg"
                      aria-label={task.status === 'active' ? t('disable') : t('enable')}
                    >
                      {task.status === 'active' ? (
                        <CheckCircle className="w-4 h-4 text-[#00ff88]" />
                      ) : (
                        <X className="w-4 h-4 text-[#6b7a9a]" />
                      )}
                    </button>
                    <button
                      onClick={() => deleteTask(task.task_id)}
                      className="p-1.5 hover:bg-white/5 rounded-lg"
                      aria-label={t('delete')}
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
                {renderTaskRecord(task)}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <CheckSquare className="w-10 h-10 mx-auto mb-3 text-[#6b7a9a]" />
            <p className="text-[#6b7a9a]">{t('noTasks')}</p>
            <p className="text-xs text-[#4a5568]">{t('tasksHint')}</p>
          </div>
        )}
      </div>

      {showEntryForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0f2137] border border-white/5 rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">
                {editingEntryId ? t('editEntry') : t('addEntry')}
              </h3>
              <button
                onClick={() => {
                  setShowEntryForm(false);
                  setEditingEntryId(null);
                  setEntryFormData({ type: 'family', content: '', subjectId: null, subjectName: null });
                }}
                className="p-1.5 hover:bg-white/5 rounded-lg"
              >
                <X className="w-5 h-5 text-[#6b7a9a]" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-[#6b7a9a] mb-2">{t('entryType')}</label>
                <select
                  value={entryFormData.type}
                  onChange={(e) => setEntryFormData({ ...entryFormData, type: e.target.value as HomeEntryType })}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#00d4ff]/50 appearance-none cursor-pointer"
                >
                  {Object.entries(entryTypeLabels).map(([type, label]) => (
                    <option key={type} value={type}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[#6b7a9a] mb-2">{t('content')}</label>
                <textarea
                  value={entryFormData.content}
                  onChange={(e) => setEntryFormData({ ...entryFormData, content: e.target.value })}
                  placeholder={t('entryContentPlaceholder')}
                  rows={4}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 resize-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setShowEntryForm(false);
                    setEditingEntryId(null);
                    setEntryFormData({ type: 'family', content: '', subjectId: null, subjectName: null });
                  }}
                  className="flex-1 px-4 py-2 bg-white/5 text-white rounded-xl font-medium hover:bg-white/10"
                >
                  {t('cancel')}
                </button>
                <button
                  onClick={handleSaveEntry}
                  className="flex-1 px-4 py-2 bg-[#00d4ff] text-[#0a0e1a] rounded-xl font-medium hover:bg-[#00b8e6]"
                >
                  {t('save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Persons;