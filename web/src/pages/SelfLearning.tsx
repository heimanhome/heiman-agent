import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Brain, Play, Square, RefreshCw, TrendingUp, Clock, Ruler,
  AlertTriangle, Send, Activity, Zap, CheckCircle,
  AlertCircle, XCircle, Cpu, BarChart3, GitBranch, Layers,
} from 'lucide-react';
import {
  aiApi, mlApi,
  type LearningStatus, type LearningCycle, type LearningRule,
  type PerformanceMetric, type ProblematicPattern,
  type MlModelInfo, type FeatureImportanceItem,
  type AbExperiment, type OnlineLearningStatus,
} from '../api/client';

/* ──────── 子组件：特征重要性条形图 ──────── */
function FeatureBar({ items }: { items: FeatureImportanceItem[] }) {
  const max = Math.max(...items.map((i) => i.importance), 0.01);
  return (
    <div className="space-y-2">
      {items.slice(0, 10).map((item) => (
        <div key={item.feature}>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-gray-600 truncate max-w-[60%]">{item.feature}</span>
            <span className="text-gray-500">{(item.importance * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-300"
              style={{ width: `${(item.importance / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SelfLearning() {
  const { t } = useTranslation('app');

  /* ──────── 主 Tab ──────── */
  const [mainTab, setMainTab] = useState<'selfLearning' | 'mlModels'>('selfLearning');

  /* ──────── 自学习监控状态 ──────── */
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [cycles, setCycles] = useState<LearningCycle[]>([]);
  const [rules, setRules] = useState<LearningRule[]>([]);
  const [performance, setPerformance] = useState<Record<string, PerformanceMetric>>({});
  const [patterns, setPatterns] = useState<ProblematicPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'status' | 'performance' | 'cycles' | 'rules' | 'patterns'>('status');
  const [feedbackModel, setFeedbackModel] = useState('');
  const [feedbackType, setFeedbackType] = useState('uncertain');
  const [feedbackConfidence, setFeedbackConfidence] = useState(0.5);
  const [selectedModelForPatterns, setSelectedModelForPatterns] = useState('');
  const [triggerModel, setTriggerModel] = useState('');
  const [operationMessage, setOperationMessage] = useState('');

  /* ──────── ML 模型状态 ──────── */
  const [mlModels, setMlModels] = useState<MlModelInfo[]>([]);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlSubTab, setMlSubTab] = useState<'list' | 'importance' | 'ab' | 'online'>('list');
  const [trainingModel, setTrainingModel] = useState<string | null>(null);
  const [featureImportance, setFeatureImportance] = useState<Record<string, FeatureImportanceItem[]>>({});
  const [selectedFeatureModel, setSelectedFeatureModel] = useState('');
  const [abExperiments, setAbExperiments] = useState<AbExperiment[]>([]);
  const [onlineStatus, setOnlineStatus] = useState<OnlineLearningStatus | null>(null);
  const [mlMessage, setMlMessage] = useState('');
  const [showAbForm, setShowAbForm] = useState(false);
  const [abForm, setAbForm] = useState({ name: '', model_name: '', ml_ratio: 0.5, shadow_mode: false, min_sample_size: 100 });

  /* ──────── 通用 ──────── */
  const modelNames = Object.keys(performance);

  const showMlMessage = (msg: string) => {
    setMlMessage(msg);
    setTimeout(() => setMlMessage(''), 3000);
  };

  /* ──────── 自学习监控方法 ──────── */
  const loadStatus = async () => {
    try {
      const r = await aiApi.getLearningStatus();
      setStatus(r.data.data || null);
    } catch (e) {
      console.error('Failed to load learning status:', e);
    }
  };

  const loadCycles = async () => {
    try {
      const r = await aiApi.getLearningCycles({ limit: 20 });
      setCycles(Array.isArray(r.data.data) ? r.data.data : []);
    } catch (e) {
      console.error('Failed to load learning cycles:', e);
    }
  };

  const loadRules = async () => {
    try {
      const r = await aiApi.getLearningRules();
      setRules(Array.isArray(r.data.data) ? r.data.data : []);
    } catch (e) {
      console.error('Failed to load learning rules:', e);
    }
  };

  const loadPerformance = async () => {
    try {
      const r = await aiApi.getLearningPerformance({ window_hours: 24 });
      setPerformance(typeof r.data.data === 'object' ? r.data.data : {});
    } catch (e) {
      console.error('Failed to load performance:', e);
    }
  };

  const loadPatterns = async (modelName: string) => {
    if (!modelName) return;
    try {
      const r = await aiApi.getProblematicPatterns(modelName);
      setPatterns(Array.isArray(r.data.data) ? r.data.data : []);
    } catch (e) {
      console.error('Failed to load patterns:', e);
    }
  };

  const handleStartLearning = async () => {
    try {
      await aiApi.startLearning();
      setOperationMessage(t('selfLearning.startSuccess'));
      loadStatus();
    } catch (e) {
      setOperationMessage(t('selfLearning.startFailed'));
    }
  };

  const handleStopLearning = async () => {
    try {
      await aiApi.stopLearning();
      setOperationMessage(t('selfLearning.stopSuccess'));
      loadStatus();
    } catch (e) {
      setOperationMessage(t('selfLearning.stopFailed'));
    }
  };

  const handleTriggerCycle = async () => {
    if (!triggerModel) return;
    try {
      await aiApi.triggerLearningCycle(triggerModel);
      setOperationMessage(t('selfLearning.triggerSuccess'));
      loadCycles();
    } catch (e) {
      setOperationMessage(t('selfLearning.triggerFailed'));
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackModel) return;
    try {
      await aiApi.submitLearningFeedback({
        model_name: feedbackModel,
        input_features: {},
        predicted_output: {},
        feedback_type: feedbackType,
        confidence: feedbackConfidence,
      });
      setOperationMessage(t('selfLearning.feedbackSuccess'));
      loadStatus();
    } catch (e) {
      setOperationMessage(t('selfLearning.feedbackFailed'));
    }
  };

  /* ──────── ML 模型方法 ──────── */
  const loadMlModels = async () => {
    setMlLoading(true);
    try {
      const r = await mlApi.getModels();
      setMlModels(r.data.data?.models || []);
    } catch (e) {
      console.error('Failed to load ML models:', e);
    }
    setMlLoading(false);
  };

  const loadAbExperiments = async () => {
    try {
      const r = await mlApi.getExperimentStatus();
      setAbExperiments(r.data.data?.experiments || []);
    } catch (e) {
      console.error('Failed to load AB experiments:', e);
    }
  };

  const loadOnlineStatus = async () => {
    try {
      const r = await mlApi.getOnlineStatus();
      setOnlineStatus(r.data.data || null);
    } catch (e) {
      console.error('Failed to load online status:', e);
    }
  };

  const loadFeatureImportance = async (name: string) => {
    if (!name) return;
    try {
      const r = await mlApi.getFeatureImportance(name);
      const data = r.data.data?.feature_importance || [];
      setFeatureImportance((prev) => ({ ...prev, [name]: data }));
    } catch (e) {
      console.error('Failed to load feature importance:', e);
    }
  };

  const handleTrainModel = async (name: string) => {
    setTrainingModel(name);
    try {
      const res = await mlApi.trainModel(name);
      const source = res.data?.data?.training_source;
      const bootstrapMsg = source === 'bootstrap' ? ` (${t('mlModels.bootstrap')})` : '';
      showMlMessage(t('mlModels.trainSuccess') + bootstrapMsg);
      loadMlModels();
    } catch (e) {
      showMlMessage(t('mlModels.trainFailed'));
    }
    setTrainingModel(null);
  };

  const handleTrainAll = async () => {
    setMlLoading(true);
    try {
      await mlApi.trainAllModels();
      showMlMessage(t('mlModels.trainAllSuccess'));
      loadMlModels();
    } catch (e) {
      showMlMessage(t('mlModels.trainFailed'));
    }
    setMlLoading(false);
  };

  const handleRetrain = async (name: string) => {
    setTrainingModel(name);
    try {
      await mlApi.retrainOnline(name);
      showMlMessage(t('mlModels.retrainSuccess'));
      loadMlModels();
      loadOnlineStatus();
    } catch (e) {
      showMlMessage(t('mlModels.trainFailed'));
    }
    setTrainingModel(null);
  };

  const handleStartExperiment = async () => {
    try {
      await mlApi.startExperiment(abForm);
      showMlMessage(t('mlModels.experimentStarted'));
      setShowAbForm(false);
      loadAbExperiments();
    } catch (e) {
      showMlMessage(t('mlModels.trainFailed'));
    }
  };

  const handlePromote = async (name: string) => {
    try {
      await mlApi.promoteExperiment(name);
      showMlMessage(t('mlModels.experimentPromoted'));
      loadAbExperiments();
    } catch (e) {
      showMlMessage(t('mlModels.analyzeFailed'));
    }
  };

  /* ──────── 生命周期 ──────── */
  useEffect(() => {
    loadStatus();
    loadCycles();
    loadRules();
    loadPerformance();
    setLoading(false);
  }, []);

  useEffect(() => {
    loadPatterns(selectedModelForPatterns);
  }, [selectedModelForPatterns]);

  useEffect(() => {
    if (operationMessage) {
      const timer = setTimeout(() => setOperationMessage(''), 3000);
      return () => clearTimeout(timer);
    }
  }, [operationMessage]);

  /* ──────── 辅助函数 ──────── */
  const formatDuration = (ms: number | null) => {
    if (!ms) return '-';
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return '-';
    return new Date(timeStr).toLocaleString();
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'text-red-500 bg-red-50';
      case 'medium': return 'text-orange-500 bg-orange-50';
      case 'low': return 'text-yellow-500 bg-yellow-50';
      default: return 'text-gray-500 bg-gray-50';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high': return <XCircle className="w-5 h-5" />;
      case 'medium': return <AlertCircle className="w-5 h-5" />;
      case 'low': return <AlertTriangle className="w-5 h-5" />;
      default: return <AlertTriangle className="w-5 h-5" />;
    }
  };

  const mlStatusLabel = (status: string) => {
    const m: Record<string, string> = {
      ready: t('mlModels.ready'), not_trained: t('mlModels.notTrained'),
      training: t('mlModels.training'), error: t('mlModels.error'),
    };
    return m[status] || status;
  };

  const mlStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'bg-green-100 text-green-600';
      case 'not_trained': return 'bg-gray-100 text-gray-500';
      case 'training': return 'bg-blue-100 text-blue-600';
      case 'error': return 'bg-red-100 text-red-600';
      default: return 'bg-gray-100 text-gray-500';
    }
  };

  /* ──────── 自学习监控 Tabs ──────── */
  const tabs = [
    { key: 'status', label: t('selfLearning.status'), icon: Activity },
    { key: 'performance', label: t('selfLearning.performance'), icon: TrendingUp },
    { key: 'cycles', label: t('selfLearning.cycles'), icon: Clock },
    { key: 'rules', label: t('selfLearning.rules'), icon: Ruler },
    { key: 'patterns', label: t('selfLearning.patterns'), icon: AlertTriangle },
  ] as const;

  /* ──────── ML 模型 Sub-Tabs ──────── */
  const mlSubTabs = [
    { key: 'list', label: t('mlModels.modelList'), icon: Layers },
    { key: 'importance', label: t('mlModels.featureImportance'), icon: BarChart3 },
    { key: 'ab', label: t('mlModels.abTesting'), icon: GitBranch },
    { key: 'online', label: t('mlModels.onlineLearning'), icon: Cpu },
  ] as const;

  /* ══════════════════════════════════════
     RENDER
     ══════════════════════════════════════ */
  return (
    <div className="p-6">
      {/* ──────── 头部 ──────── */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {mainTab === 'mlModels' ? t('mlModels.title') : t('selfLearning.title')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {mainTab === 'mlModels' ? t('mlModels.description') : t('selfLearning.description')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* 顶层 Tab 切换 */}
          <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1">
            <button
              onClick={() => setMainTab('selfLearning')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mainTab === 'selfLearning'
                  ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Brain className="w-4 h-4 inline mr-1.5" />
              {t('selfLearning.tabSelfLearning')}
            </button>
            <button
              onClick={() => { setMainTab('mlModels'); loadMlModels(); loadAbExperiments(); loadOnlineStatus(); }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mainTab === 'mlModels'
                  ? 'bg-white dark:bg-gray-700 text-indigo-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Cpu className="w-4 h-4 inline mr-1.5" />
              {t('selfLearning.tabMlModels')}
            </button>
          </div>

          {/* 自学习控制按钮 */}
          {mainTab === 'selfLearning' && (
            <>
              {status?.is_running ? (
                <button
                  onClick={handleStopLearning}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                >
                  <Square className="w-4 h-4" />
                  <span>{t('selfLearning.stop')}</span>
                </button>
              ) : (
                <button
                  onClick={handleStartLearning}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-50 text-green-600 hover:bg-green-100 transition-colors"
                >
                  <Play className="w-4 h-4" />
                  <span>{t('selfLearning.start')}</span>
                </button>
              )}
            </>
          )}

          {mainTab === 'mlModels' && (
            <button
              onClick={() => { loadMlModels(); loadAbExperiments(); loadOnlineStatus(); }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>{t('refresh')}</span>
            </button>
          )}

          {mainTab === 'selfLearning' && (
            <button
              onClick={() => {
                setLoading(true);
                loadStatus(); loadCycles(); loadRules(); loadPerformance();
                setLoading(false);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>{t('refresh')}</span>
            </button>
          )}
        </div>
      </div>

      {/* ──────── 操作消息 ──────── */}
      {operationMessage && (
        <div className={`mb-4 px-4 py-3 rounded-lg ${operationMessage.includes('成功') ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
          {operationMessage}
        </div>
      )}

      {mlMessage && (
        <div className={`mb-4 px-4 py-3 rounded-lg ${mlMessage.includes('成功') || mlMessage.includes('Success') ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
          {mlMessage}
        </div>
      )}

      {/* ══════════════════════════════════════
         TAB: 自学习监控
         ══════════════════════════════════════ */}
      {mainTab === 'selfLearning' && (
        <>
          {/* 统计卡片 */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${status?.is_running ? 'bg-green-100' : 'bg-gray-100'}`}>
                  {status?.is_running ? (
                    <Zap className="w-5 h-5 text-green-600" />
                  ) : (
                    <Brain className="w-5 h-5 text-gray-600" />
                  )}
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('selfLearning.systemStatus')}</p>
                  <p className={`text-lg font-semibold ${status?.is_running ? 'text-green-600' : 'text-gray-600'}`}>
                    {status?.is_running ? t('selfLearning.running') : t('selfLearning.stopped')}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('selfLearning.feedbackCount')}</p>
                  <p className="text-lg font-semibold text-gray-900">{status?.total_feedback_count ?? 0}</p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('selfLearning.lastCycle')}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {status?.last_cycle_time ? formatTime(status.last_cycle_time) : '-'}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                  <Ruler className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('selfLearning.activeRules')}</p>
                  <p className="text-lg font-semibold text-gray-900">{rules.filter(r => r.enabled).length}</p>
                </div>
              </div>
            </div>
          </div>

          {/* 自学习子 Tabs */}
          <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* 自学习内容 */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : (
            <>
              {activeTab === 'status' && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-sm font-semibold text-gray-900">{t('selfLearning.models')}</h2>
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {status?.models.map((model) => (
                      <div key={model.name} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${model.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}`} />
                          <div>
                            <p className="font-medium text-gray-900">{model.name}</p>
                            <p className="text-sm text-gray-500">
                              {t('selfLearning.lastLearning')}: {model.last_learning_time ? formatTime(model.last_learning_time) : '-'}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-gray-500">{t('selfLearning.feedback')}</p>
                          <p className="font-semibold text-gray-900">{model.feedback_count}</p>
                        </div>
                      </div>
                    ))}
                    {!status?.models.length && (
                      <div className="p-8 text-center text-gray-500">{t('noData')}</div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'performance' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Object.entries(performance).map(([modelName, metric]) => (
                    <div key={modelName} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-gray-900">{modelName}</h3>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          metric.accuracy >= 0.8 ? 'bg-green-100 text-green-600' :
                          metric.accuracy >= 0.6 ? 'bg-yellow-100 text-yellow-600' :
                          'bg-red-100 text-red-600'
                        }`}>
                          {(metric.accuracy * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="space-y-3">
                        {(['precision', 'recall', 'f1_score'] as const).map((key) => (
                          <div key={key}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-500">{t(`selfLearning.${key === 'f1_score' ? 'f1Score' : key}`)}</span>
                              <span className="font-medium">{(metric[key] * 100).toFixed(1)}%</span>
                            </div>
                            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${key === 'precision' ? 'bg-blue-500' : key === 'recall' ? 'bg-green-500' : 'bg-purple-500'}`}
                                style={{ width: `${metric[key] * 100}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-between text-sm">
                        <span className="text-gray-500">{t('selfLearning.feedbackCount')}: {metric.feedback_count}</span>
                        <span className="text-gray-500">{t('selfLearning.cycleCount')}: {metric.learning_cycles}</span>
                      </div>
                    </div>
                  ))}
                  {Object.keys(performance).length === 0 && (
                    <div className="col-span-full p-8 text-center text-gray-500">{t('noData')}</div>
                  )}
                </div>
              )}

              {activeTab === 'cycles' && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-gray-900">{t('selfLearning.learningCycles')}</h2>
                    <div className="flex items-center gap-2">
                      <select
                        value={triggerModel}
                        onChange={(e) => setTriggerModel(e.target.value)}
                        className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm bg-white dark:bg-gray-700"
                      >
                        <option value="">{t('selfLearning.selectModel')}</option>
                        {modelNames.map((name) => (
                          <option key={name} value={name}>{name}</option>
                        ))}
                      </select>
                      <button
                        onClick={handleTriggerCycle}
                        disabled={!triggerModel}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                      >
                        <Zap className="w-4 h-4" />{t('selfLearning.trigger')}
                      </button>
                    </div>
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {cycles.map((cycle) => (
                      <div key={cycle.cycle_id} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${cycle.status === 'completed' ? 'bg-green-500' : cycle.status === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-400'}`} />
                          <div>
                            <p className="font-medium text-gray-900">{cycle.model_name}</p>
                            <p className="text-sm text-gray-500">{t('selfLearning.started')}: {formatTime(cycle.started_at)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          <div className="text-center"><p className="text-xs text-gray-500">{t('selfLearning.feedbackUsed')}</p><p className="font-semibold text-gray-900">{cycle.feedback_used}</p></div>
                          <div className="text-center"><p className="text-xs text-gray-500">{t('selfLearning.rulesGenerated')}</p><p className="font-semibold text-gray-900">{cycle.rules_generated}</p></div>
                          <div className="text-center"><p className="text-xs text-gray-500">{t('selfLearning.duration')}</p><p className="font-semibold text-gray-900">{formatDuration(cycle.duration_ms)}</p></div>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            cycle.status === 'completed' ? 'bg-green-100 text-green-600' : cycle.status === 'running' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
                          }`}>{cycle.status}</span>
                        </div>
                      </div>
                    ))}
                    {cycles.length === 0 && <div className="p-8 text-center text-gray-500">{t('noData')}</div>}
                  </div>
                </div>
              )}

              {activeTab === 'rules' && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-sm font-semibold text-gray-900">{t('selfLearning.generatedRules')}</h2>
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {rules.map((rule) => (
                      <div key={rule.rule_id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-medium text-gray-900">{rule.model_name}</span>
                              <span className={`px-2 py-0.5 rounded text-xs ${rule.enabled ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                                {rule.enabled ? t('enabled') : t('disabled')}
                              </span>
                              <span className="text-sm text-gray-500">{rule.rule_type}</span>
                            </div>
                            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{t('selfLearning.condition')}:</span> {rule.condition}</p>
                            <p className="text-sm text-gray-600 mb-2"><span className="font-medium">{t('selfLearning.action')}:</span> {rule.action}</p>
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span>{t('selfLearning.confidence')}: {(rule.confidence * 100).toFixed(1)}%</span>
                              <span>{t('selfLearning.applied')}: {rule.applied_count}</span>
                              <span>{t('selfLearning.created')}: {formatTime(rule.created_at)}</span>
                            </div>
                          </div>
                          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${rule.enabled ? 'bg-green-50' : 'bg-gray-50'}`}>
                            {rule.enabled ? <CheckCircle className="w-6 h-6 text-green-600" /> : <XCircle className="w-6 h-6 text-gray-400" />}
                          </div>
                        </div>
                      </div>
                    ))}
                    {rules.length === 0 && <div className="p-8 text-center text-gray-500">{t('noData')}</div>}
                  </div>
                </div>
              )}

              {activeTab === 'patterns' && (
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-gray-900">{t('selfLearning.problematicPatterns')}</h2>
                    <select
                      value={selectedModelForPatterns}
                      onChange={(e) => setSelectedModelForPatterns(e.target.value)}
                      className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm bg-white dark:bg-gray-700"
                    >
                      <option value="">{t('selfLearning.selectModel')}</option>
                      {modelNames.map((name) => (<option key={name} value={name}>{name}</option>))}
                    </select>
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {patterns.map((pattern) => (
                      <div key={pattern.pattern_id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <div className="flex items-start gap-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${getSeverityColor(pattern.severity)}`}>
                            {getSeverityIcon(pattern.severity)}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-gray-900">{pattern.pattern_type}</span>
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityColor(pattern.severity)}`}>{pattern.severity}</span>
                            </div>
                            <p className="text-sm text-gray-600 mb-2">{pattern.description}</p>
                            <p className="text-sm text-green-600 mb-2"><span className="font-medium">{t('selfLearning.suggestedFix')}:</span> {pattern.suggested_fix}</p>
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span>{t('selfLearning.affected')}: {pattern.affected_count}</span>
                              <span>{t('selfLearning.detected')}: {formatTime(pattern.detected_at)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    {!selectedModelForPatterns && <div className="p-8 text-center text-gray-500">{t('selfLearning.selectModelHint')}</div>}
                    {selectedModelForPatterns && patterns.length === 0 && <div className="p-8 text-center text-gray-500">{t('selfLearning.noPatterns')}</div>}
                  </div>
                </div>
              )}
            </>
          )}

          {/* 反馈卡片 */}
          <div className="mt-6 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">{t('selfLearning.submitFeedback')}</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">{t('selfLearning.model')}</label>
                <select
                  value={feedbackModel}
                  onChange={(e) => setFeedbackModel(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                >
                  <option value="">{t('selfLearning.selectModel')}</option>
                  {modelNames.map((name) => (<option key={name} value={name}>{name}</option>))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">{t('selfLearning.feedbackType')}</label>
                <select
                  value={feedbackType}
                  onChange={(e) => setFeedbackType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                >
                  <option value="correct">{t('selfLearning.correct')}</option>
                  <option value="incorrect">{t('selfLearning.incorrect')}</option>
                  <option value="uncertain">{t('selfLearning.uncertain')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  {t('selfLearning.confidence')}: {(feedbackConfidence * 100).toFixed(0)}%
                </label>
                <input
                  type="range" min="0" max="1" step="0.1"
                  value={feedbackConfidence}
                  onChange={(e) => setFeedbackConfidence(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleSubmitFeedback}
                  disabled={!feedbackModel}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />{t('submit')}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ══════════════════════════════════════
         TAB: ML 模型
         ══════════════════════════════════════ */}
      {mainTab === 'mlModels' && (
        <>
          {/* ML 统计卡片 */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                  <Layers className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">{t('mlModels.ready')}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {mlModels.filter((m) => m.status === 'ready').length} / {mlModels.length}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">{t('mlModels.accuracy')}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {mlModels.filter((m) => m.accuracy != null).length > 0
                      ? `${(mlModels.filter((m) => m.accuracy != null).reduce((s, m) => s + (m.accuracy ?? 0), 0) / mlModels.filter((m) => m.accuracy != null).length * 100).toFixed(1)}%`
                      : '-'}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <GitBranch className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">{t('mlModels.experimentRunning')}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {abExperiments.filter((e) => e.status === 'running').length}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">{t('mlModels.feedbackAccumulated')}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {onlineStatus?.models?.reduce((s, m) => s + m.feedback_since_last_train, 0) ?? 0}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* ML 子 Tabs */}
          <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
            {mlSubTabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => {
                  setMlSubTab(tab.key);
                  if (tab.key === 'importance' && selectedFeatureModel) loadFeatureImportance(selectedFeatureModel);
                  if (tab.key === 'ab') loadAbExperiments();
                  if (tab.key === 'online') loadOnlineStatus();
                }}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  mlSubTab === tab.key
                    ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* ──────── ML Sub: 模型列表 ──────── */}
          {mlSubTab === 'list' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">{t('mlModels.modelList')}</h2>
                <button
                  onClick={handleTrainAll}
                  disabled={mlLoading || mlModels.length === 0}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 text-sm font-medium"
                >
                  <Zap className="w-4 h-4" />{t('mlModels.trainAll')}
                </button>
              </div>
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {mlModels.map((model) => (
                  <div key={model.name} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${mlStatusColor(model.status)}`}>
                        {mlStatusLabel(model.status)}
                      </span>
                      {model.training_source === 'bootstrap' && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" title={t('mlModels.bootstrapTip')}>
                          {t('mlModels.bootstrap')}
                        </span>
                      )}
                      {model.training_source === 'real_feedback' && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" title={t('mlModels.realFeedbackTip')}>
                          {t('mlModels.realFeedback')}
                        </span>
                      )}
                      <div>
                        <p className="font-medium text-gray-900">{model.name}</p>
                        <p className="text-xs text-gray-500">
                          {t('mlModels.modelType')}: {model.type} · {t('mlModels.features')}: {model.feature_count} · {t('mlModels.samples')}: {model.samples}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {model.accuracy != null && (
                        <span className={`text-sm font-medium ${model.training_source === 'bootstrap' ? 'text-amber-600' : 'text-green-600'}`} title={model.training_source === 'bootstrap' ? t('mlModels.bootstrapTip') : ''}>
                          {(model.accuracy * 100).toFixed(1)}%
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{model.last_trained ? formatTime(model.last_trained) : t('mlModels.notTrained')}</span>
                      {model.trainable !== false && (
                        <button
                          onClick={() => handleTrainModel(model.name)}
                          disabled={trainingModel === model.name}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 text-sm"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${trainingModel === model.name ? 'animate-spin' : ''}`} />
                          {trainingModel === model.name ? t('mlModels.training') : t('mlModels.train')}
                        </button>
                      )}
                      {model.trainable === false && (
                        <span className="text-xs text-gray-400 italic">{t('mlModels.notTrainable')}</span>
                      )}
                    </div>
                  </div>
                ))}
                {mlModels.length === 0 && (
                  <div className="p-8 text-center text-gray-500">{t('noData')}</div>
                )}
              </div>
            </div>
          )}

          {/* ──────── ML Sub: 特征重要性 ──────── */}
          {mlSubTab === 'importance' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">{t('mlModels.featureImportance')}</h2>
                <div className="flex items-center gap-2">
                  <select
                    value={selectedFeatureModel}
                    onChange={(e) => { setSelectedFeatureModel(e.target.value); loadFeatureImportance(e.target.value); }}
                    className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm bg-white dark:bg-gray-700"
                  >
                    <option value="">{t('selfLearning.selectModel')}</option>
                    {mlModels.filter((m) => m.trainable !== false).map((m) => (<option key={m.name} value={m.name}>{m.name}</option>))}
                  </select>
                </div>
              </div>
              <div className="p-6">
                {selectedFeatureModel && featureImportance[selectedFeatureModel] ? (
                  <FeatureBar items={featureImportance[selectedFeatureModel]} />
                ) : (
                  <div className="p-8 text-center text-gray-500">{t('mlModels.noFeatureData')}</div>
                )}
              </div>
            </div>
          )}

          {/* ──────── ML Sub: A/B 测试 ──────── */}
          {mlSubTab === 'ab' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">{t('mlModels.abTesting')}</h2>
                <button
                  onClick={() => setShowAbForm(!showAbForm)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 text-sm font-medium"
                >
                  <GitBranch className="w-4 h-4" />{t('mlModels.startExperiment')}
                </button>
              </div>

              {showAbForm && (
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <input
                      placeholder={t('mlModels.experimentName')}
                      value={abForm.name}
                      onChange={(e) => setAbForm({ ...abForm, name: e.target.value })}
                      className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm"
                    />
                    <select
                      value={abForm.model_name}
                      onChange={(e) => setAbForm({ ...abForm, model_name: e.target.value })}
                      className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm"
                    >
                      <option value="">{t('selfLearning.selectModel')}</option>
                      {mlModels.filter((m) => m.status === 'ready' && m.trainable !== false).map((m) => (
                        <option key={m.name} value={m.name}>{m.name}</option>
                      ))}
                    </select>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-500">{t('mlModels.mlRatio')}</label>
                      <input
                        type="number" min="0" max="1" step="0.1"
                        value={abForm.ml_ratio}
                        onChange={(e) => setAbForm({ ...abForm, ml_ratio: parseFloat(e.target.value) || 0.5 })}
                        className="w-20 px-2 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm"
                      />
                    </div>
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={abForm.shadow_mode}
                        onChange={(e) => setAbForm({ ...abForm, shadow_mode: e.target.checked })}
                      />
                      {t('mlModels.shadowMode')}
                    </label>
                    <button
                      onClick={handleStartExperiment}
                      disabled={!abForm.name || !abForm.model_name}
                      className="px-4 py-2 rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-50 text-sm"
                    >
                      {t('mlModels.startExperiment')}
                    </button>
                  </div>
                </div>
              )}

              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {abExperiments.map((exp) => (
                  <div key={exp.name} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        exp.status === 'running' ? 'bg-green-100 text-green-600' :
                        exp.status === 'completed' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {exp.status === 'running' ? t('mlModels.experimentRunning') :
                         exp.status === 'completed' ? t('mlModels.experimentCompleted') :
                         t('mlModels.experimentStopped')}
                      </span>
                      <div>
                        <p className="font-medium text-gray-900">{exp.name}</p>
                        <p className="text-xs text-gray-500">
                          {exp.model_name} · ML {t('mlModels.mlRatio')}: {exp.ml_ratio}
                          {exp.shadow_mode ? ` · ${t('mlModels.shadowMode')}` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-center">
                        <p className="text-xs text-gray-400">A ({t('mlModels.variantA')})</p>
                        <p className="font-semibold text-sm">{exp.variant_a_samples}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-gray-400">B (ML)</p>
                        <p className="font-semibold text-sm">{exp.variant_b_samples}</p>
                      </div>
                      {exp.status === 'running' && (
                        <button
                          onClick={() => handlePromote(exp.name)}
                          className="px-3 py-1.5 rounded-lg bg-green-50 text-green-600 hover:bg-green-100 text-sm"
                        >
                          <CheckCircle className="w-3.5 h-3.5 inline mr-1" />
                          {t('mlModels.promote')}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {abExperiments.length === 0 && (
                  <div className="p-8 text-center text-gray-500">{t('mlModels.noExperiments')}</div>
                )}
              </div>
            </div>
          )}

          {/* ──────── ML Sub: 在线学习 ──────── */}
          {mlSubTab === 'online' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-sm font-semibold text-gray-900">{t('mlModels.onlineStatus')}</h2>
              </div>
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {onlineStatus?.models?.map((m) => (
                  <div key={m.name} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-center gap-4">
                      <p className="font-medium text-gray-900 min-w-[120px]">{m.name}</p>
                      <div className="flex gap-4 text-sm">
                        <div>
                          <span className="text-gray-400">{t('mlModels.feedbackAccumulated')}: </span>
                          <span className={`font-medium ${m.feedback_since_last_train >= m.retrain_threshold ? 'text-orange-500' : 'text-gray-700'}`}>
                            {m.feedback_since_last_train} / {m.retrain_threshold}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-400">{t('mlModels.lastRetrain')}: </span>
                          <span className="text-gray-700">{m.last_retrain ? formatTime(m.last_retrain) : '-'}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {/* 准确率趋势迷你条 */}
                      {m.accuracy_trend && m.accuracy_trend.length > 0 && (
                        <div className="flex items-end gap-0.5 h-8">
                          {m.accuracy_trend.map((v, i) => (
                            <div
                              key={i}
                              className="w-2 bg-indigo-400 rounded-t"
                              style={{ height: `${Math.max(v * 100, 4)}%` }}
                              title={`${(v * 100).toFixed(1)}%`}
                            />
                          ))}
                        </div>
                      )}
                      <button
                        onClick={() => handleRetrain(m.name)}
                        disabled={trainingModel === m.name}
                        className="px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 text-sm"
                      >
                        {trainingModel === m.name ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin inline mr-1" />
                        ) : null}
                        {t('mlModels.retrain')}
                      </button>
                    </div>
                  </div>
                ))}
                {(!onlineStatus?.models || onlineStatus.models.length === 0) && (
                  <div className="p-8 text-center text-gray-500">{t('noData')}</div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
