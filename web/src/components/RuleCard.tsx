import { Settings, ToggleLeft, ToggleRight, Trash2, Edit3 } from 'lucide-react';
import type { Rule } from '../types';

interface RuleCardProps {
  rule: Rule;
  onToggle?: (enabled: boolean) => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

const operatorLabels: Record<string, string> = {
  '>': '大于',
  '<': '小于',
  '=': '等于',
  '!=': '不等于',
  '>=': '大于等于',
  '<=': '小于等于',
};

const actionLabels: Record<string, string> = {
  log: '记录日志',
  alert: '发送告警',
  webhook: '调用Webhook',
  notification: '发送通知',
};

export function RuleCard({ rule, onToggle, onEdit, onDelete }: RuleCardProps) {
  const conditionText = rule.conditions
    .map((c) => {
      const sensorType = c.sensor_type ? `${c.sensor_type} ` : '';
      return `${sensorType}值 ${operatorLabels[c.operator] || c.operator} ${c.threshold}`;
    })
    .join(' 且 ');

  const actionText = rule.actions
    .map((a) => actionLabels[a.action_type] || a.action_type)
    .join('、');

  return (
    <div className="bg-white dark:bg-[#0f2137] rounded-xl p-5 border border-gray-200 dark:border-white/5 transition-all duration-300 hover:border-[#00d4ff]/30 hover:shadow-lg hover:shadow-[#00d4ff]/10">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-gray-100 dark:bg-gray-800">
            <Settings className="w-5 h-5 text-gray-900 dark:text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{rule.name}</h3>
            <p className="text-xs text-gray-500 dark:text-[#6b7a9a]">{rule.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle?.(!rule.enabled)}
            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            {rule.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          </button>
          <button
            onClick={onEdit}
            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Edit3 className="w-5 h-5" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-start gap-2">
          <span className="text-xs text-gray-500 dark:text-[#6b7a9a] flex-shrink-0 w-20">条件:</span>
          <span className="text-sm text-gray-900 dark:text-white">{conditionText}</span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-xs text-gray-500 dark:text-[#6b7a9a] flex-shrink-0 w-20">动作:</span>
          <span className="text-sm text-gray-900 dark:text-white">{actionText}</span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-xs text-gray-500 dark:text-[#6b7a9a] flex-shrink-0 w-20">冷却时间:</span>
          <span className="text-sm text-gray-900 dark:text-white">{rule.cooldown_minutes} 分钟</span>
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
        <span className="text-xs font-medium text-gray-900 dark:text-white">
          {rule.enabled ? '已启用' : '已禁用'}
        </span>
        <span className="text-xs text-[#4a5568]">
          更新于 {new Date(rule.updated_at).toLocaleDateString('zh-CN')}
        </span>
      </div>
    </div>
  );
}
