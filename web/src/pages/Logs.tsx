import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, RefreshCw, AlertTriangle, Info, XCircle, CheckCircle, Clock, Download, Server, Smartphone, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, X } from 'lucide-react';
import { logApi, DeviceLogEntry, PaginatedResponse } from '../api/client';

interface LogEntry {
  id: string;
  time: string;
  level: 'info' | 'warning' | 'error' | 'success';
  action: string;
  user: string;
  message: string;
}

interface DeviceLogProperty {
  log_id: number;
  property_id: string;
  property_name: string;
  value: string;
  value_type: string;
  unit?: string;
}

const levelConfig: Record<string, { icon: typeof Info; color: string; bgColor: string; label: string }> = {
  info: { icon: Info, color: 'text-[#00d4ff]', bgColor: 'bg-[#00d4ff]/10', label: 'info' },
  warning: { icon: AlertTriangle, color: 'text-[#ffa502]', bgColor: 'bg-[#ffa502]/10', label: 'warning' },
  error: { icon: XCircle, color: 'text-[#ff4757]', bgColor: 'bg-[#ff4757]/10', label: 'error' },
  success: { icon: CheckCircle, color: 'text-[#00ff88]', bgColor: 'bg-[#00ff88]/10', label: 'success' },
};

const sensorTypeMap: Record<string, string> = {
  temperature: '温度传感器',
  humidity: '湿度传感器',
  co: '一氧化碳传感器',
  water: '水浸传感器',
  smoke: '烟雾传感器',
  contact: '门磁传感器',
  motion: '移动传感器',
  plug: '智能插座',
  siren: '警笛',
  button: '按钮',
  gateway: '网关',
  remote: '遥控器',
};

const pageSizeOptions = [10, 20, 50, 100];

const convertValue = (sensorType: string, value: number | string | null | undefined, valueLabel?: string): string => {
  if (valueLabel) {
    return valueLabel;
  }
  
  if (value === null || value === undefined) return '-';
  
  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  
  switch (sensorType) {
    case 'contact':
      return numValue === 0 ? '关闭' : numValue === 1 ? '打开' : String(value);
    case 'plug':
      return numValue === 0 ? '关闭' : numValue === 1 ? '打开' : numValue === 2 ? '异常' : numValue === 3 ? '正常' : String(value);
    case 'motion':
      return numValue === 0 ? '无移动' : numValue === 1 ? '检测到移动' : String(value);
    case 'smoke':
      return numValue === 0 ? '正常' : numValue === 1 ? '烟雾告警' : String(value);
    case 'co':
      return numValue === 0 ? '正常' : numValue === 1 ? '气体告警' : `${value} ppm`;
    case 'water':
      return numValue === 0 ? '正常' : numValue === 1 ? '水浸告警' : String(value);
    case 'siren':
      return numValue === 0 ? '关闭' : numValue === 1 ? '鸣响中' : String(value);
    case 'button':
      return numValue === 0 ? '未按下' : numValue === 1 ? '已按下' : String(value);
    default:
      return String(value);
  }
};

const Pagination = ({ current, pageSize, total, onChange, onPageSizeChange }: { current: number; pageSize: number; total: number; onChange: (page: number) => void; onPageSizeChange: (size: number) => void }) => {
  const totalPages = Math.ceil(total / pageSize);
  const startIndex = (current - 1) * pageSize + 1;
  const endIndex = Math.min(current * pageSize, total);

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      if (current <= 3) {
        pages.push(1, 2, 3, 4, '...', totalPages);
      } else if (current >= totalPages - 2) {
        pages.push(1, '...', totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
      } else {
        pages.push(1, '...', current - 1, current, current + 1, '...', totalPages);
      }
    }
    return pages;
  };

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-5 py-4 bg-white/5">
      <div className="text-sm text-gray-500 dark:text-[#6b7a9a]">
        共 <span className="text-gray-900 dark:text-white font-medium">{total}</span> 条记录，
        显示第 <span className="text-gray-900 dark:text-white font-medium">{startIndex}</span> - <span className="text-gray-900 dark:text-white font-medium">{endIndex}</span> 条
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">每页</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50"
          >
            {pageSizeOptions.map(size => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
          <span className="text-sm text-gray-500 dark:text-[#6b7a9a]">条</span>
        </div>
        <div className="flex items-center gap-1 ml-4">
          <button
            onClick={() => onChange(1)}
            disabled={current === 1}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronsLeft className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          <button
            onClick={() => onChange(current - 1)}
            disabled={current === 1}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          {getPageNumbers().map((page, index) => (
            typeof page === 'number' ? (
              <button
                key={index}
                onClick={() => onChange(page)}
                className={`w-8 h-8 rounded text-sm font-medium transition-colors ${
                  page === current
                    ? 'bg-[#00d4ff] text-[#0a1628]'
                    : 'text-gray-500 dark:text-[#6b7a9a] hover:bg-white/10'
                }`}
              >
                {page}
              </button>
            ) : (
              <span key={index} className="px-2 text-gray-500 dark:text-[#6b7a9a]">...</span>
            )
          ))}
          <button
            onClick={() => onChange(current + 1)}
            disabled={current === totalPages}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
          <button
            onClick={() => onChange(totalPages)}
            disabled={current === totalPages}
            className="p-1.5 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronsRight className="w-4 h-4 text-gray-500 dark:text-[#6b7a9a]" />
          </button>
        </div>
      </div>
    </div>
  );
};

export function Logs() {
  const { t } = useTranslation('app');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'system' | 'device'>('system');
  const [logs, setLogs] = useState<LogEntry[] | DeviceLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [showPropertyModal, setShowPropertyModal] = useState(false);
  const [selectedProperties, setSelectedProperties] = useState<DeviceLogProperty[]>([]);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');

  useEffect(() => {
    setPage(1);
    fetchLogs();
  }, [activeTab]);

  useEffect(() => {
    fetchLogs();
  }, [page, pageSize, searchTerm, filterLevel]);

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    try {
      if (activeTab === 'device') {
        const response = await logApi.getDeviceLogs({ 
          search: searchTerm || undefined,
          page,
          page_size: pageSize,
        });
        const data = response.data;
        if (data.success) {
          setLogs(data.data || []);
          setTotal(data.total || 0);
        } else {
          setError(data.message || '获取设备日志失败');
          setLogs([]);
          setTotal(0);
        }
      } else {
        const response = await logApi.getAll({ 
          search: searchTerm || undefined,
          level: filterLevel === 'all' ? undefined : filterLevel,
          page,
          page_size: pageSize,
        });
        const data = response.data;
        if (data.success) {
          setLogs(data.data || []);
          setTotal(data.total || 0);
        } else {
          setError(data.message || '获取系统日志失败');
          setLogs([]);
          setTotal(0);
        }
      }
    } catch (error: any) {
      console.error('Failed to fetch logs:', error);
      setError(error.message || '网络错误，无法获取日志');
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    setPage(1);
    fetchLogs();
  };

  const handleSearch = () => {
    setPage(1);
    fetchLogs();
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="max-w-[1200px] w-full mx-auto px-4 md:px-8 pt-5 pb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{t('logSystem')}</h1>
          <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">
            {activeTab === 'system' ? t('operationLogs') : '设备日志'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
                    onClick={handleRefresh}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  >
            <RefreshCw className="w-4 h-4" />
            <span>{t('refresh')}</span>
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-semibold rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
            <Download className="w-4 h-4" />
            <span>{t('export')}</span>
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#0f2137] rounded-xl p-4 border border-gray-200 dark:border-white/5 mb-6">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1 relative w-full">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={activeTab === 'device' ? '搜索设备ID、房间或传感器类型...' : t('searchLogs')}
              className="w-full pl-12 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-900 dark:text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50"
            />
          </div>
          {activeTab === 'system' && (
            <div className="flex items-center gap-2">
              <select
                value={filterLevel}
                onChange={(e) => {
                  setFilterLevel(e.target.value);
                  setPage(1);
                }}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-900 dark:text-white focus:outline-none focus:border-[#00d4ff]/50"
              >
                <option value="all">{t('allLevels')}</option>
                <option value="info">{t('info')}</option>
                <option value="warning">{t('warning')}</option>
                <option value="error">{t('error')}</option>
                <option value="success">{t('success')}</option>
              </select>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('system')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'system'
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
        >
          <Server className="w-4 h-4" />
          <span>{t('operationLogs')}</span>
        </button>
        <button
          onClick={() => setActiveTab('device')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'device'
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
        >
          <Smartphone className="w-4 h-4" />
          <span>设备日志</span>
        </button>
      </div>

      <div className="bg-white dark:bg-[#0f2137] rounded-xl border border-gray-200 dark:border-white/5 overflow-hidden">
        {activeTab === 'system' ? (
          <>
            <div className="grid grid-cols-12 gap-4 px-5 py-3 bg-white/5 text-sm font-medium text-gray-500 dark:text-[#6b7a9a]">
              <div className="col-span-3">{t('logTime')}</div>
              <div className="col-span-1">{t('logLevel')}</div>
              <div className="col-span-2">{t('logAction')}</div>
              <div className="col-span-2">{t('logUser')}</div>
              <div className="col-span-4">{t('logMessage')}</div>
            </div>
            <div className="divide-y divide-white/5">
              {loading ? (
                <div className="px-5 py-10 text-center">
                  <span className="inline-block w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
                  {t('loading')}
                </div>
              ) : error ? (
                <div className="px-5 py-10 text-center">
                  <XCircle className="w-10 h-10 text-[#ff4757] mx-auto mb-3" />
                  <p className="text-[#ff4757] text-sm mb-1">{error}</p>
                  <button
                    onClick={handleRefresh}
                    className="mt-3 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  >
                    重试
                  </button>
                </div>
              ) : logs.length > 0 ? (
                logs.map((log) => {
                  const systemLog = log as LogEntry;
                  const config = levelConfig[systemLog.level];
                  const Icon = config.icon;
                  return (
                    <div key={systemLog.id} className="grid grid-cols-12 gap-4 px-5 py-3 hover:bg-white/5 transition-colors">
                      <div className="col-span-3 flex items-center gap-2 text-sm text-gray-500 dark:text-[#6b7a9a]">
                        <Clock className="w-4 h-4" />
                        <span>{systemLog.time}</span>
                      </div>
                      <div className="col-span-1">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${config.bgColor} ${config.color}`}>
                          <Icon className="w-3 h-3" />
                          {t(config.label)}
                        </span>
                      </div>
                      <div className="col-span-2 text-sm text-gray-900 dark:text-white">{systemLog.action}</div>
                      <div className="col-span-2 text-sm text-gray-500 dark:text-[#6b7a9a]">{systemLog.user}</div>
                      <div className="col-span-4 text-sm text-gray-900 dark:text-white truncate">{systemLog.message}</div>
                    </div>
                  );
                })
              ) : (
                <div className="px-5 py-10 text-center">
                  <Info className="w-10 h-10 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-3" />
                  <p className="text-gray-900 dark:text-white text-sm mb-1">{t('noData')}</p>
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a]">{t('adjustFilter')}</p>
                </div>
              )}
            </div>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              onChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </>
        ) : (
          <>
            <div className="grid grid-cols-12 gap-4 px-5 py-3 bg-white/5 text-sm font-medium text-gray-500 dark:text-[#6b7a9a]">
              <div className="col-span-2">时间</div>
              <div className="col-span-2">设备名称</div>
              <div className="col-span-2">设备类型</div>
              <div className="col-span-2">属性名称</div>
              <div className="col-span-2">数值</div>
              <div className="col-span-2">房间</div>
            </div>
            <div className="divide-y divide-white/5">
              {loading ? (
                <div className="px-5 py-10 text-center">
                  <span className="inline-block w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
                  {t('loading')}
                </div>
              ) : error ? (
                <div className="px-5 py-10 text-center">
                  <XCircle className="w-10 h-10 text-[#ff4757] mx-auto mb-3" />
                  <p className="text-[#ff4757] text-sm mb-1">{error}</p>
                  <button
                    onClick={handleRefresh}
                    className="mt-3 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  >
                    重试
                  </button>
                </div>
              ) : logs.length > 0 ? (
                logs.map((log) => {
                  const deviceLog = log as DeviceLogEntry;
                  const sensorTypeName = sensorTypeMap[deviceLog.sensor_type] || deviceLog.sensor_type;
                  const deviceName = (deviceLog as any).device_name || deviceLog.did;
                  const properties = (deviceLog as any).properties || [];
                  return (
                    <div key={deviceLog.id} className="grid grid-cols-12 gap-4 px-5 py-3 hover:bg-white/5 transition-colors">
                      <div className="col-span-2 flex items-center gap-2 text-sm text-gray-500 dark:text-[#6b7a9a]">
                        <Clock className="w-4 h-4" />
                        <span>{formatTime(deviceLog.timestamp)}</span>
                      </div>
                      <div className="col-span-2 text-sm text-gray-900 dark:text-white">
                        {deviceName}
                      </div>
                      <div className="col-span-2 text-sm text-gray-900 dark:text-white">
                        {sensorTypeName}
                      </div>
                      <div className="col-span-2 text-sm">
                        <button
                          onClick={() => {
                            setSelectedProperties(properties);
                            setSelectedDeviceName(deviceName);
                            setShowPropertyModal(true);
                          }}
                          className="text-[#00d4ff] hover:text-[#00d4ff]/80 underline underline-offset-2 transition-colors"
                        >
                          {deviceLog.property_name}
                          {properties.length > 0 && (
                            <span className="ml-1 text-xs text-gray-500 dark:text-[#6b7a9a]">
                              (+{properties.length})
                            </span>
                          )}
                        </button>
                      </div>
                      <div className="col-span-2 text-sm text-[#00d4ff] font-medium">
                        {convertValue(deviceLog.sensor_type, deviceLog.value, (deviceLog as any).value_label)}
                      </div>
                      <div className="col-span-2 text-sm text-gray-500 dark:text-[#6b7a9a]">
                        {deviceLog.room_name || '-'}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="px-5 py-10 text-center">
                  <Info className="w-10 h-10 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-3" />
                  <p className="text-gray-900 dark:text-white text-sm mb-1">暂无设备日志数据</p>
                  <p className="text-xs text-gray-500 dark:text-[#6b7a9a]">检查设备连接状态或调整搜索条件</p>
                </div>
              )}
            </div>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              onChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </>
        )}
      </div>

      {showPropertyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowPropertyModal(false)} />
          <div className="relative bg-white dark:bg-[#0f2137] rounded-xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-white/10">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-white/10">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {selectedDeviceName} - 属性详情
              </h3>
              <button
                onClick={() => setShowPropertyModal(false)}
                className="p-1 rounded-lg hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto">
              {selectedProperties.length > 0 ? (
                <div className="space-y-3">
                  {selectedProperties.map((prop, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{prop.property_name}</p>
                        <p className="text-xs text-gray-500 dark:text-[#6b7a9a]">
                          ID: {prop.property_id} | Type: {prop.value_type}
                        </p>
                      </div>
                      <span className="text-lg font-semibold text-[#00d4ff]">
                        {prop.value}{prop.unit ? ` ${prop.unit}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Info className="w-10 h-10 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-3" />
                  <p className="text-gray-500 dark:text-[#6b7a9a]">暂无属性数据</p>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-white/10">
              <button
                onClick={() => setShowPropertyModal(false)}
                className="w-full px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-medium rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}