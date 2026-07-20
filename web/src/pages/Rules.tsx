import { useEffect } from 'react';
import { Plus, Settings, CheckCircle } from 'lucide-react';
import { RuleCard } from '../components/RuleCard';
import { useAppStore } from '../store';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export function Rules() {
  const { t } = useTranslation('app');
  const { rules, loading, fetchRules, updateRule, deleteRule } = useAppStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const enabledCount = rules.filter((r) => r.enabled).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('ruleManagement')}</h1>
          <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('configureRules')}</p>
        </div>
        <button
          onClick={() => navigate('/rules/new')}
          className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-medium rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          {t('createRule')}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-[#0f2137] rounded-xl p-5 border border-gray-200 dark:border-white/5">
          <div className="flex items-center gap-3 mb-2">
            <Settings className="w-6 h-6 text-[#00d4ff]" />
            <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('totalRules')}</span>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{rules.length}</p>
        </div>
        <div className="bg-white dark:bg-[#0f2137] rounded-xl p-5 border border-gray-200 dark:border-white/5">
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle className="w-6 h-6 text-[#00ff88]" />
            <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('enabled')}</span>
          </div>
          <p className="text-3xl font-bold text-[#00ff88]">{enabledCount}</p>
        </div>
        <div className="bg-white dark:bg-[#0f2137] rounded-xl p-5 border border-gray-200 dark:border-white/5">
          <div className="flex items-center gap-3 mb-2">
            <Settings className="w-6 h-6 text-gray-500 dark:text-[#6b7a9a]" />
            <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('disabled')}</span>
          </div>
          <p className="text-3xl font-bold text-gray-500 dark:text-[#6b7a9a]">{rules.length - enabledCount}</p>
        </div>
      </div>

      {loading.rules ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white dark:bg-[#0f2137] rounded-xl p-5 border border-gray-200 dark:border-white/5 animate-pulse" />
          ))}
        </div>
      ) : rules.length === 0 ? (
        <div className="bg-white dark:bg-[#0f2137] rounded-xl p-12 text-center border border-gray-200 dark:border-white/5">
          <Settings className="w-12 h-12 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-4" />
          <p className="text-gray-900 dark:text-white mb-2">{t('noRules')}</p>
          <button
            onClick={() => navigate('/rules/new')}
            className="mt-4 px-6 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-medium rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            {t('createFirstRule')}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => (
            <RuleCard
              key={rule.rule_id}
              rule={rule}
              onToggle={(enabled) => updateRule(rule.rule_id, { enabled })}
              onEdit={() => navigate(`/rules/${rule.rule_id}`)}
              onDelete={() => deleteRule(rule.rule_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
