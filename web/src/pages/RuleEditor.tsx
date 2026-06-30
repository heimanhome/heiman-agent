import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, Save } from 'lucide-react';
import { useAppStore } from '../store';
import { useTranslation } from 'react-i18next';
import type { Rule, RuleCondition, RuleAction, SensorType, Operator } from '../types';

const sensorTypes: SensorType[] = ['smoke', 'temperature', 'humidity', 'co', 'water'];
const operators: Operator[] = ['>', '<', '=', '!=', '>=', '<='];
const actionTypes = ['alert', 'log', 'webhook', 'notification'] as const;
type ActionType = typeof actionTypes[number];

export function RuleEditor() {
  const { rule_id } = useParams<{ rule_id: string }>();
  const navigate = useNavigate();
  const { rules, createRule, updateRule, fetchRules } = useAppStore();
  const { t } = useTranslation('app');
  const isEdit = !!rule_id;

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [conditions, setConditions] = useState<RuleCondition[]>([
    { sensor_type: undefined, operator: '>', threshold: 0, window_seconds: undefined },
  ]);
  const [actions, setActions] = useState<RuleAction[]>([{ action_type: 'alert', payload: { title: '', message: '' } }]);
  const [cooldownMinutes, setCooldownMinutes] = useState(5);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  useEffect(() => {
    if (isEdit && rule_id) {
      const rule = rules.find((r) => r.rule_id === rule_id);
      if (rule) {
        setName(rule.name);
        setDescription(rule.description);
        setEnabled(rule.enabled);
        setConditions(rule.conditions.length > 0 ? rule.conditions : [{ sensor_type: undefined, operator: '>', threshold: 0, window_seconds: undefined }]);
        setActions(rule.actions.length > 0 ? rule.actions : [{ action_type: 'alert', payload: { title: '', message: '' } }]);
        setCooldownMinutes(rule.cooldown_minutes);
      }
    }
  }, [isEdit, rule_id, rules]);

  const handleAddCondition = () => {
    setConditions([...conditions, { sensor_type: undefined, operator: '>', threshold: 0, window_seconds: undefined }]);
  };

  const handleRemoveCondition = (index: number) => {
    if (conditions.length > 1) {
      setConditions(conditions.filter((_, i) => i !== index));
    }
  };

  const handleUpdateCondition = (index: number, updates: Partial<RuleCondition>) => {
    setConditions(
      conditions.map((c, i) => (i === index ? { ...c, ...updates } : c))
    );
  };

  const handleAddAction = () => {
    setActions([...actions, { action_type: 'alert', payload: { title: '', message: '' } }]);
  };

  const handleRemoveAction = (index: number) => {
    if (actions.length > 1) {
      setActions(actions.filter((_, i) => i !== index));
    }
  };

  const handleUpdateAction = (index: number, updates: Partial<RuleAction>) => {
    setActions(
      actions.map((a, i) => (i === index ? { ...a, ...updates } : a))
    );
  };

  const handleSubmit = async () => {
    const ruleData = {
      name,
      description,
      enabled,
      conditions,
      actions,
      cooldown_minutes: cooldownMinutes,
    };

    if (isEdit && rule_id) {
      await updateRule(rule_id, ruleData);
    } else {
      await createRule(ruleData);
    }

    navigate('/rules');
  };

  const operatorLabels: Record<string, string> = {
    '>': t('greaterThan'),
    '<': t('lessThan'),
    '=': t('equalTo'),
    '!=': t('notEqualTo'),
    '>=': t('greaterThanOrEqual'),
    '<=': t('lessThanOrEqual'),
  };

  const actionLabels: Record<ActionType, string> = {
    alert: t('alertAction'),
    log: t('logAction'),
    webhook: t('webhookAction'),
    notification: t('notificationAction'),
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/rules')}
          className="flex items-center gap-2 text-[#00d4ff] hover:underline"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('back')}
        </button>
        <button
          onClick={handleSubmit}
          className="flex items-center gap-2 px-4 py-2 bg-[#00d4ff] text-[#0a1628] font-medium rounded-xl hover:bg-[#00d4ff]/90 transition-colors"
        >
          <Save className="w-5 h-5" />
          {t('saveRule')}
        </button>
      </div>

      <h1 className="text-2xl font-bold text-white">
        {isEdit ? t('editRule') : t('createRule')}
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
            <h2 className="text-lg font-semibold text-white mb-4">{t('basicInfo')}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-[#6b7a9a] mb-2">{t('ruleName')}</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t('enterRuleName')}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm text-[#6b7a9a] mb-2">{t('description')}</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t('enterRuleDescription')}
                  rows={3}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors resize-none"
                />
              </div>
              <div className="flex items-center justify-between">
                <label className="text-sm text-[#6b7a9a]">{t('ruleEnabled')}</label>
                <button
                  onClick={() => setEnabled(!enabled)}
                  className={`w-12 h-6 rounded-full transition-colors ${
                    enabled ? 'bg-[#00d4ff]' : 'bg-[#6b7a9a]'
                  }`}
                >
                  <div
                    className={`w-5 h-5 bg-white rounded-full transition-transform ${
                      enabled ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
              <div>
                <label className="block text-sm text-[#6b7a9a] mb-2">{t('cooldownMinutes')}</label>
                <input
                  type="number"
                  value={cooldownMinutes}
                  onChange={(e) => setCooldownMinutes(parseInt(e.target.value) || 0)}
                  min={0}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                />
              </div>
            </div>
          </div>

          <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{t('ruleConditions')}</h2>
              <button
                onClick={handleAddCondition}
                className="flex items-center gap-1 text-sm text-[#00d4ff] hover:underline"
              >
                <Plus className="w-4 h-4" />
                {t('addCondition')}
              </button>
            </div>
            <div className="space-y-4">
              {conditions.map((condition, index) => (
                <div key={index} className="bg-white/5 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm text-[#6b7a9a]">{t('condition')} {index + 1}</span>
                    {conditions.length > 1 && (
                      <button
                        onClick={() => handleRemoveCondition(index)}
                        className="text-sm text-[#ff4757] hover:underline"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs text-[#6b7a9a] mb-1">{t('sensorType')}</label>
                      <select
                        value={condition.sensor_type || ''}
                        onChange={(e) => handleUpdateCondition(index, { sensor_type: e.target.value as SensorType | undefined })}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
                      >
                        <option value="">{t('allTypes')}</option>
                        {sensorTypes.map((type) => (
                          <option key={type} value={type}>{t(`sensorLabels.${type}`)}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-[#6b7a9a] mb-1">{t('operator')}</label>
                      <select
                        value={condition.operator}
                        onChange={(e) => handleUpdateCondition(index, { operator: e.target.value as Operator })}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
                      >
                        {operators.map((op) => (
                          <option key={op} value={op}>{operatorLabels[op]}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-[#6b7a9a] mb-1">{t('threshold')}</label>
                      <input
                        type="number"
                        value={condition.threshold}
                        onChange={(e) => handleUpdateCondition(index, { threshold: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                      />
                    </div>
                  </div>
                  <div className="mt-3">
                    <label className="block text-xs text-[#6b7a9a] mb-1">{t('duration')} ({t('seconds')}, {t('optional')})</label>
                    <input
                      type="number"
                      value={condition.window_seconds || ''}
                      onChange={(e) => handleUpdateCondition(index, { window_seconds: e.target.value ? parseInt(e.target.value) : undefined })}
                      placeholder={t('durationPlaceholder')}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">{t('ruleActions')}</h2>
            <button
              onClick={handleAddAction}
              className="flex items-center gap-1 text-sm text-[#00d4ff] hover:underline"
            >
              <Plus className="w-4 h-4" />
              {t('addAction')}
            </button>
          </div>
          <div className="space-y-4">
            {actions.map((action, index) => (
              <div key={index} className="bg-white/5 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-[#6b7a9a]">{t('action')} {index + 1}</span>
                  {actions.length > 1 && (
                    <button
                      onClick={() => handleRemoveAction(index)}
                      className="text-sm text-[#ff4757] hover:underline"
                      >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-[#6b7a9a] mb-1">{t('actionType')}</label>
                    <select
                      value={action.action_type}
                      onChange={(e) => handleUpdateAction(index, { action_type: e.target.value as ActionType })}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
                    >
                      {actionTypes.map((type) => (
                        <option key={type} value={type}>{actionLabels[type]}</option>
                      ))}
                    </select>
                  </div>
                  {action.action_type === 'webhook' && (
                    <div>
                      <label className="block text-xs text-[#6b7a9a] mb-1">{t('webhookUrl')}</label>
                      <input
                        type="text"
                        value={action.payload?.title || ''}
                        onChange={(e) => handleUpdateAction(index, { payload: { ...action.payload, title: e.target.value } })}
                        placeholder={t('enterWebhookUrl')}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                      />
                    </div>
                  )}
                  {action.action_type !== 'log' && (
                    <div>
                      <label className="block text-xs text-[#6b7a9a] mb-1">{t('messageContent')}</label>
                      <input
                        type="text"
                        value={action.payload?.message || ''}
                        onChange={(e) => handleUpdateAction(index, { payload: { ...action.payload, message: e.target.value } })}
                        placeholder={t('enterMessageContent')}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 p-4 bg-[#00d4ff]/10 rounded-xl">
            <h3 className="text-sm font-medium text-[#00d4ff] mb-2">{t('rulePreview')}</h3>
            <p className="text-sm text-white">
              {t('when')} {conditions.map((c) => `${c.sensor_type ? t(`sensorLabels.${c.sensor_type}`) : t('allSensors')}${t('value')} ${operatorLabels[c.operator]} ${c.threshold}`).join(' ' + t('and') + ' ')}
              {cooldownMinutes > 0 && `，${t('cooldown')} ${cooldownMinutes} ${t('minutes')}`}
              {t('then')}：{actions.map((a) => actionLabels[a.action_type]).join('、')}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}