import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckSquare, Plus, Pause, Play, Trash2, Loader2, Clock, BarChart3, ListChecks } from 'lucide-react';
import { taskApi, type Task, type ProgressRecord, type DurationRecord, type EventRecord } from '../api/client';

export function Tasks() {
  const { t } = useTranslation('app');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    description: '',
    kind: 'progress' as 'progress' | 'duration' | 'event',
    target: '',
    unit: '',
    window: 'day' as 'day' | 'week' | 'month' | 'longterm',
    target_minutes: '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const r = await taskApi.getAll();
      setTasks(r.data.data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!formData.description.trim()) return;
    const body: Record<string, unknown> = {
      description: formData.description,
      kind: formData.kind,
    };
    if (formData.kind === 'progress') {
      body.target = Number(formData.target);
      body.unit = formData.unit;
      body.window = formData.window;
    } else if (formData.kind === 'duration') {
      body.target_minutes = Number(formData.target_minutes);
    }
    await taskApi.create(body as Parameters<typeof taskApi.create>[0]);
    setShowForm(false);
    setFormData({ description: '', kind: 'progress', target: '', unit: '', window: 'day', target_minutes: '' });
    await load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('confirmDelete'))) return;
    await taskApi.delete(id);
    await load();
  };

  const handlePause = async (id: string) => {
    await taskApi.pause(id);
    await load();
  };

  const handleResume = async (id: string) => {
    await taskApi.resume(id);
    await load();
  };

  const handleIncrement = async (id: string, delta: number) => {
    await taskApi.incrementProgress(id, delta);
    await load();
  };

  const handleStartSession = async (id: string) => {
    await taskApi.startSession(id);
    await load();
  };

  const handleEndSession = async (id: string) => {
    await taskApi.endSession(id);
    await load();
  };

  const handleAppendEvent = async (id: string) => {
    const desc = prompt(t('eventDescriptionPrompt'));
    if (!desc) return;
    await taskApi.appendEvent(id, desc);
    await load();
  };

  const renderRecord = (task: Task) => {
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
            <span>
              {rec.current} / {rec.target} {rec.unit}
            </span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 bg-[#0f1419] rounded overflow-hidden">
            <div className="h-full bg-[#00d4ff]" style={{ width: `${pct}%` }} />
          </div>
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => handleIncrement(task.task_id, 1)}
              className="text-xs px-2 py-1 bg-[#2a3142] text-white rounded hover:bg-[#3a4152]"
            >
              +1
            </button>
            <button
              onClick={() => handleIncrement(task.task_id, 10)}
              className="text-xs px-2 py-1 bg-[#2a3142] text-white rounded hover:bg-[#3a4152]"
            >
              +10
            </button>
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
          <div className="flex gap-2 mt-2">
            {rec.active_session_start_at ? (
              <button
                onClick={() => handleEndSession(task.task_id)}
                className="text-xs px-2 py-1 bg-[#ff6b6b] text-white rounded hover:bg-[#ff5252]"
              >
                {t('endSession')}
              </button>
            ) : (
              <button
                onClick={() => handleStartSession(task.task_id)}
                className="text-xs px-2 py-1 bg-[#00ff88] text-[#0a0e1a] rounded hover:bg-[#00e078]"
              >
                {t('startSession')}
              </button>
            )}
          </div>
        </div>
      );
    }
    const rec = r as EventRecord;
    return (
      <div className="mt-3">
        <p className="text-xs text-[#6b7a9a]">
          {t('total')}: {rec.total_count} | {t('today')}: {rec.today_count}
        </p>
        <button
          onClick={() => handleAppendEvent(task.task_id)}
          className="text-xs px-2 py-1 mt-2 bg-[#2a3142] text-white rounded hover:bg-[#3a4152]"
        >
          + {t('appendEvent')}
        </button>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <CheckSquare className="w-6 h-6" />
            {t('tasks')}
          </h1>
          <p className="text-sm text-[#6b7a9a]">{t('tasksDescription')}</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-[#00d4ff] text-[#0a0e1a] rounded font-semibold hover:bg-[#00b8e6] flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          {t('newTask')}
        </button>
      </div>

      {showForm && (
        <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4 space-y-3">
          <input
            type="text"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder={t('taskDescriptionPlaceholder')}
            className="w-full bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
          />
          <div className="flex flex-wrap gap-2">
            <select
              value={formData.kind}
              onChange={(e) =>
                setFormData({ ...formData, kind: e.target.value as 'progress' | 'duration' | 'event' })
              }
              className="bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
            >
              <option value="progress">{t('progressType')}</option>
              <option value="duration">{t('durationType')}</option>
              <option value="event">{t('eventType')}</option>
            </select>
            {formData.kind === 'progress' && (
              <>
                <input
                  type="number"
                  value={formData.target}
                  onChange={(e) => setFormData({ ...formData, target: e.target.value })}
                  placeholder={t('target')}
                  className="bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
                />
                <input
                  type="text"
                  value={formData.unit}
                  onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  placeholder={t('unit')}
                  className="bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
                />
                <select
                  value={formData.window}
                  onChange={(e) =>
                    setFormData({ ...formData, window: e.target.value as 'day' | 'week' | 'month' | 'longterm' })
                  }
                  className="bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
                >
                  <option value="day">{t('day')}</option>
                  <option value="week">{t('week')}</option>
                  <option value="month">{t('month')}</option>
                  <option value="longterm">{t('longterm')}</option>
                </select>
              </>
            )}
            {formData.kind === 'duration' && (
              <input
                type="number"
                value={formData.target_minutes}
                onChange={(e) => setFormData({ ...formData, target_minutes: e.target.value })}
                placeholder={t('targetMinutes')}
                className="bg-[#0f1419] border border-[#2a3142] rounded px-3 py-2 text-white"
              />
            )}
            <button
              onClick={handleCreate}
              className="px-4 py-2 bg-[#00d4ff] text-[#0a0e1a] rounded font-semibold hover:bg-[#00b8e6]"
            >
              {t('create')}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-[#00d4ff]" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-12 text-center">
          <CheckSquare className="w-12 h-12 mx-auto mb-3 text-[#6b7a9a]" />
          <p className="text-[#6b7a9a]">{t('noTasks')}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tasks.map((task) => (
            <div
              key={task.task_id}
              className="bg-[#1a2030] border border-[#2a3142] rounded-lg p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  {task.record?.kind === 'progress' && <BarChart3 className="w-4 h-4 text-[#00d4ff]" />}
                  {task.record?.kind === 'duration' && <Clock className="w-4 h-4 text-[#00d4ff]" />}
                  {task.record?.kind === 'event' && <ListChecks className="w-4 h-4 text-[#00d4ff]" />}
                  <h3 className="text-white font-semibold">{task.description}</h3>
                </div>
                <div className="flex gap-1">
                  {task.status === 'active' ? (
                    <button
                      onClick={() => handlePause(task.task_id)}
                      className="p-1.5 hover:bg-[#2a3142] rounded"
                      aria-label={t('pause')}
                    >
                      <Pause className="w-4 h-4 text-yellow-400" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleResume(task.task_id)}
                      className="p-1.5 hover:bg-[#2a3142] rounded"
                      aria-label={t('resume')}
                    >
                      <Play className="w-4 h-4 text-[#00ff88]" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(task.task_id)}
                    className="p-1.5 hover:bg-[#2a3142] rounded"
                    aria-label={t('delete')}
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </button>
                </div>
              </div>
              {task.status === 'paused' && (
                <span className="text-xs text-yellow-400">● {t('paused')}</span>
              )}
              {renderRecord(task)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Tasks;
